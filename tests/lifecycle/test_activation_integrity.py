"""Current lifecycle replacements for retired controller safety assurances."""
import json
import shutil
from pathlib import Path

import pytest

from kg_mnp.lifecycle import environment
from kg_mnp.lifecycle.errors import LifecycleError
from kg_mnp.lifecycle.guards import package_record
from kg_mnp.lifecycle.registry.import_package import import_package
from kg_mnp.lifecycle.registry.manifest import init_registry
from kg_mnp.lifecycle.store import bind_identity
from tests.lifecycle.test_prompt07_e2e import _approved_candidate, _head


@pytest.fixture(scope="module")
def activated_base(prompt05_case, tmp_path_factory):
    root = tmp_path_factory.mktemp("current-activation-base")
    init_registry(root)
    record = import_package(root, prompt05_case["result"].package_directory)
    release, _ = _approved_candidate(root, record["package_id"], "integrity")
    env = environment.init_environment(root, environment_name="integrity")
    proposal = environment.propose_activation(root, environment_id=env["environment_id"], release_id=release["release_id"], rationale="explicit target")
    decision = environment.review_activation(root, proposal_id=proposal["activation_proposal_id"], decision="APPROVE", reviewer_id="human", reviewer_roles=["RELEASE_MANAGER"], breaking_change_acknowledged=True)
    return root, record, release, env, proposal, decision


@pytest.fixture
def activation(activated_base, tmp_path):
    original, *values = activated_base
    root = tmp_path / "registry"
    shutil.copytree(original, root)
    record, release, env, proposal, decision = values
    request = {"proposal_id": proposal["activation_proposal_id"], "decision_id": decision["decision_id"],
               "expected_generation": 0, "expected_pointer_hash": proposal["base_pointer_hash"],
               "expected_registry_head_hash": _head(root)["head_hash"]}
    return root, record, release, env, request


@pytest.mark.parametrize("field", ["expected_generation", "expected_pointer_hash", "expected_registry_head_hash"])
def test_current_environment_cas_preserves_pointer_and_receipts(activation, field):
    root, _record, _release, _env, request = activation
    before = {p.name: p.read_bytes() for p in (root / "state").glob("*.json")}
    request[field] = 100 if field == "expected_generation" else "f" * 64
    with pytest.raises(LifecycleError, match="changed"):
        environment.execute_activation(root, **request)
    assert before == {p.name: p.read_bytes() for p in (root / "state").glob("*.json")}
    assert not list((root / "records/activation-receipts").glob("*.json"))


@pytest.mark.parametrize("change", ["removed-package", "changed-package", "changed-attestation"])
def test_approved_target_drift_never_selects_or_repairs(activation, change):
    root, record, _release, _env, request = activation
    pointer = next((root / "state").glob("environment-pointer-*.json"))
    before = pointer.read_bytes()
    if change == "changed-attestation":
        path = next((root / "records/attestations").glob("*.json"))
        value = json.loads(path.read_bytes()); value["package_archive_sha256"] = "f" * 64
        path.write_text(json.dumps(value), encoding="utf-8")
    else:
        artifact = root / package_record(root, record["package_id"])["package_storage_ref"] / "data/abox.nt"
        if change == "removed-package": artifact.rename(artifact.with_suffix(".removed"))
        else: artifact.write_bytes(artifact.read_bytes() + b"\n# changed\n")
    with pytest.raises(ValueError):
        environment.execute_activation(root, **request)
    assert pointer.read_bytes() == before
    assert not list((root / "records/activation-receipts").glob("*.json"))


def test_replayed_approval_does_not_increment_generation(activation):
    root, _record, release, env, request = activation
    receipt = environment.execute_activation(root, **request)
    assert receipt["target_release_id"] == release["release_id"]
    path, pointer = environment._pointer(root, env["environment_id"])
    before = path.read_bytes()
    for update in ({}, {"expected_generation": 1, "expected_pointer_hash": pointer["pointer_hash"], "expected_registry_head_hash": _head(root)["head_hash"]}):
        with pytest.raises(LifecycleError):
            environment.execute_activation(root, **{**request, **update})
    assert path.read_bytes() == before and pointer["generation"] == 1
    assert len(list((root / "records/activation-receipts").glob("*.json"))) == 1


def test_selected_package_loss_does_not_fallback_or_repair_pointer(activation):
    root, record, _release, env, request = activation
    environment.execute_activation(root, **request)
    pointer_path, _pointer = environment._pointer(root, env["environment_id"])
    before = pointer_path.read_bytes()
    artifact = root / package_record(root, record["package_id"])["package_storage_ref"] / "data/abox.nt"
    artifact.rename(artifact.with_suffix(".removed"))
    with pytest.raises(ValueError):
        environment._pointer(root, env["environment_id"])
    assert pointer_path.read_bytes() == before


def test_rollback_to_never_selected_target_is_rejected(activation):
    root, _record, release, env, _request = activation
    with pytest.raises(LifecycleError, match="never successfully activated"):
        environment.propose_activation(root, environment_id=env["environment_id"], release_id=release["release_id"], rationale="unknown history", activation_kind="ROLLBACK")
    assert environment._pointer(root, env["environment_id"])[1]["generation"] == 0


@pytest.mark.parametrize("rehash", [False, True])
def test_pointer_tampering_cannot_manufacture_selection_without_event(tmp_path, rehash):
    init_registry(tmp_path)
    env = environment.init_environment(tmp_path, environment_name="pointer-boundary")
    path, value = environment._pointer(tmp_path, env["environment_id"])
    value["generation"] = 1
    if rehash:
        bind_identity(value, "pointer_id", "environment-pointer")
        value["pointer_hash"] = value["content_digest"]
    path.write_text(json.dumps(value), encoding="utf-8")
    before = path.read_bytes()
    with pytest.raises(LifecycleError):
        environment._pointer(tmp_path, env["environment_id"])
    assert path.read_bytes() == before


def test_import_without_external_project_lock_is_explicit_and_schema_valid(activated_base):
    root, record, *_ = activated_base
    stored = package_record(root, record["package_id"])
    from kg_mnp.lifecycle.contracts import verify

    verify(stored, contract="registered-package-record")
    assert stored["source_project_lock_ref"] == {"availability": "NOT_PROVIDED"}
    assert stored["source_project_lock_file_sha256"] == "0" * 64


@pytest.mark.parametrize("identifier", ["../../secret", "C:/secret", "\\\\external.invalid\\share", "urn:kg-mnp:environment-manifest:../bad"])
def test_environment_id_is_rejected_before_filesystem_probe(tmp_path, monkeypatch, identifier):
    def forbidden(path):
        raise AssertionError("malformed identifier must never become a filesystem probe")
    monkeypatch.setattr(Path, "is_file", forbidden)
    with pytest.raises(LifecycleError) as rejected:
        environment._pointer(tmp_path, identifier)
    assert rejected.value.code == "LIFECYCLE_CONTRACT_INVALID"
