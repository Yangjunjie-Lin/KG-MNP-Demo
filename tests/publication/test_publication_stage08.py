from __future__ import annotations

import copy
import json
from pathlib import Path

import pytest

from kg_mnp_demo.publication.contracts import (
    PublicationContractError,
    load_publication_schema,
    validate_publication_contract,
)
from kg_mnp_demo.publication.package_builder import build_end_to_end_publication_package
from kg_mnp_demo.publication.package_validator import (
    validate_end_to_end_publication_package_against_authorities,
)

SCENARIOS = (
    "full-confirmation",
    "modified-confirmation",
    "rejection",
    "issue-resolution",
)


def test_publication_contracts_are_closed() -> None:
    assert (
        load_publication_schema("end-to-end-publication-manifest")[
            "additionalProperties"
        ]
        is False
    )
    assert (
        load_publication_schema("publication-attestation")["additionalProperties"]
        is False
    )
    attestation_required = set(
        load_publication_schema("publication-attestation")["required"]
    )
    assert {
        "publication_semantic_hash",
        "visualization_id",
        "visualization_semantic_hash",
    } <= attestation_required


def test_four_scenarios_preserve_one_tbox_projection() -> None:
    packages = [
        build_end_to_end_publication_package(scenario=scenario)
        for scenario in SCENARIOS
    ]
    vowl_hashes = {p["manifest"]["visualization_semantic_hash"] for p in packages}
    publication_ids = {p["manifest"]["publication_id"] for p in packages}
    assert len(vowl_hashes) == 1
    assert len(publication_ids) == len(SCENARIOS)
    for package in packages:
        assert package["manifest"]["publication_status"] == "READY_FOR_PRESENTATION"
        assert package["visualization"]["coverage"]["abox_leakage_hits"] == []
        review = json.loads(
            package["files"]["source/review-decision-log.json"].decode("utf-8")
        )
        assert package["manifest"]["review_decision_log_hash"] == review["log_hash"]
        assert (
            json.loads(
                package["files"]["verification/tbox-equivalence.json"].decode("utf-8")
            )["status"]
            == "PASS"
        )


def test_publication_validator_rebuilds_closed_artifact_set(tmp_path: Path) -> None:
    out = tmp_path / "publication"
    build_end_to_end_publication_package(scenario="full-confirmation", output_dir=out)
    assert (
        validate_end_to_end_publication_package_against_authorities(
            out, scenario="full-confirmation"
        )["valid"]
        is True
    )
    (out / "unexpected.txt").write_text("forged", encoding="utf-8")
    with pytest.raises(ValueError, match="closed artifact set"):
        validate_end_to_end_publication_package_against_authorities(
            out, scenario="full-confirmation"
        )


def test_tracked_publication_goldens_reconstruct() -> None:
    hashes = set()
    for scenario in SCENARIOS:
        package = Path("examples/publication/expected") / scenario
        result = validate_end_to_end_publication_package_against_authorities(
            package, scenario=scenario
        )
        assert result["valid"] is True
        import json

        hashes.add(
            json.loads(
                (package / "publication-manifest.json").read_text(encoding="utf-8")
            )["visualization_semantic_hash"]
        )
    assert len(hashes) == 1


def test_publication_builder_rejects_unvalidated_authority_overrides() -> None:
    proposal = json.loads(
        Path(
            "examples/modeling/expected-proposals/partial-basic.proposal.json"
        ).read_text(encoding="utf-8")
    )
    forged = copy.deepcopy(proposal)
    forged["attacker_field"] = "kept old self-hash"
    with pytest.raises(ValueError, match="Stage 04/05 authority validation"):
        build_end_to_end_publication_package(proposal=forged)
    with pytest.raises(ValueError, match="supplied compilation manifest"):
        build_end_to_end_publication_package(compilation_manifest={})
    with pytest.raises(ValueError, match="supplied GraphDB manifest"):
        build_end_to_end_publication_package(graphdb_manifest={})


def test_verified_attestation_is_semantically_fail_closed() -> None:
    payload = {
        "contract_version": "1.0",
        "status": "PUBLICATION_VERIFIED",
        "publication_id": "urn:kg-mnp:e2e-publication:" + "a" * 64,
        "graphdb_tbox_semantic_hash": "a" * 64,
        "stage03_tbox_semantic_hash": "b" * 64,
        "raw_vowl_hash": "c" * 64,
        "normalized_vowl_hash": "d" * 64,
        "coverage_status": "FAILED",
        "browser_status": "NOT_RUN",
        "graphdb_version": "11.4.2",
        "graphdb_license_state": "ACCEPTED",
        "graphdb_oci_image_digest": "sha256:" + "e" * 64,
        "webvowl_upstream_commit": "f" * 40,
        "owl2vowl_upstream_commit": "1" * 40,
        "runtime_image_digest": "sha256:" + "2" * 64,
        "browser_name": "chromium",
        "browser_version": "131.0.6778.33",
        "browser_revision": "1148",
        "playwright_version": "1.49.1",
    }
    with pytest.raises(
        PublicationContractError, match="coverage_status|TBox|required"
    ):
        validate_publication_contract("publication-attestation", payload)
