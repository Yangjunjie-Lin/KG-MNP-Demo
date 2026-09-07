from __future__ import annotations

import json
from pathlib import Path

from kg_mnp.lifecycle.environment import (
    execute_activation,
    init_environment,
    propose_activation,
    review_activation,
)
from kg_mnp.lifecycle.registry.import_package import import_package
from kg_mnp.lifecycle.registry.manifest import init_registry
from kg_mnp.lifecycle.release import (
    attest_release,
    create_release_candidate,
    publish_release,
    record_review,
)


def _head(root: Path) -> dict:
    return json.loads((root / "state" / "registry-head.json").read_bytes())


def _approved_candidate(root: Path, package_id: str, variant: str):
    candidate = create_release_candidate(root, candidate_package_id=package_id, release_candidate_kind="INITIAL", variant=variant)
    review = record_review(root, candidate["release_candidate_id"], reviewer_id="release-manager", reviewer_roles=["RELEASE_MANAGER"], rationale=f"approved {variant}")
    release = publish_release(root, candidate, review, expected_registry_head_hash=_head(root)["head_hash"])
    attestation = attest_release(root, release)
    return release, attestation


def test_real_package_release_activation_and_explicit_historical_rollback(tmp_path: Path, prompt05_case: dict) -> None:
    package = prompt05_case["result"].package_directory
    manifest = json.loads((package / "ontology-package.json").read_bytes())
    before = {path.relative_to(package): path.read_bytes() for path in package.rglob("*") if path.is_file()}
    root = tmp_path / "registry"
    init_registry(root)
    imported = import_package(root, package)
    assert imported["status"] == "IMPORTED_VERIFIED"

    first_release, first_attestation = _approved_candidate(root, manifest["package_id"], "first")
    second_release, _second_attestation = _approved_candidate(root, manifest["package_id"], "second")
    environment = init_environment(root, environment_name="test")

    first_proposal = propose_activation(root, environment_id=environment["environment_id"], release_id=first_release["release_id"], rationale="select first")
    first_decision = review_activation(root, proposal_id=first_proposal["activation_proposal_id"], decision="APPROVE_ACTIVATION", reviewer_id="release-manager", reviewer_roles=["RELEASE_MANAGER"], breaking_change_acknowledged=True)
    first_receipt = execute_activation(root, proposal_id=first_proposal["activation_proposal_id"], decision_id=first_decision["decision_id"], expected_generation=0, expected_pointer_hash=first_proposal["base_pointer_hash"], expected_registry_head_hash=_head(root)["head_hash"], breaking_change_acknowledged=True)
    assert first_receipt["target_release_id"] == first_release["release_id"]

    second_proposal = propose_activation(root, environment_id=environment["environment_id"], release_id=second_release["release_id"], rationale="select second")
    second_decision = review_activation(root, proposal_id=second_proposal["activation_proposal_id"], decision="APPROVE_ACTIVATION", reviewer_id="release-manager", reviewer_roles=["RELEASE_MANAGER"], breaking_change_acknowledged=True)
    execute_activation(root, proposal_id=second_proposal["activation_proposal_id"], decision_id=second_decision["decision_id"], expected_generation=1, expected_pointer_hash=second_proposal["base_pointer_hash"], expected_registry_head_hash=_head(root)["head_hash"], breaking_change_acknowledged=True)

    rollback_proposal = propose_activation(root, environment_id=environment["environment_id"], release_id=first_release["release_id"], rationale="restore known good first release", activation_kind="ROLLBACK")
    rollback_decision = review_activation(root, proposal_id=rollback_proposal["activation_proposal_id"], decision="APPROVE_ROLLBACK", reviewer_id="release-manager", reviewer_roles=["RELEASE_MANAGER"])
    rollback_receipt = execute_activation(root, proposal_id=rollback_proposal["activation_proposal_id"], decision_id=rollback_decision["decision_id"], expected_generation=2, expected_pointer_hash=rollback_proposal["base_pointer_hash"], expected_registry_head_hash=_head(root)["head_hash"], breaking_change_acknowledged=True)
    pointer = json.loads(next((root / "state").glob("environment-pointer-*.json")).read_bytes())
    assert rollback_receipt["execution_status"] == "ROLLED_BACK"
    assert pointer["active_release_id"] == first_release["release_id"]
    assert pointer["active_package_id"] == manifest["package_id"]
    assert {path.relative_to(package): path.read_bytes() for path in package.rglob("*") if path.is_file()} == before
    assert first_attestation["package_archive_sha256"]
