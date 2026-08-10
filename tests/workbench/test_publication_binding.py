from __future__ import annotations

import json

import pytest

from kg_mnp_demo.workbench.binding import WorkbenchBinding
from kg_mnp_demo.workbench.errors import WorkbenchError

from ._helpers import health, write_phase01_artifact


def test_verified_phase01_artifact_binds_every_authority_identity(tmp_path) -> None:
    artifact = write_phase01_artifact(tmp_path / "phase01")
    binding = WorkbenchBinding.load(artifact)
    binding.verify_health(health())
    status = binding.public_status()
    assert status["phase01_attestation_status"] == "APPLICATION_READONLY_VERIFIED"
    assert len(status["phase01_attestation_hash"]) == 64
    assert len(status["publication_semantic_hash"]) == 64
    assert len(status["repository_semantic_hash"]) == 64
    assert len(status["query_registry_hash"]) == 64


@pytest.mark.parametrize(
    ("field", "value"),
    [
        ("publication_id", "urn:kg-mnp:e2e-publication:" + "1" * 64),
        ("publication_semantic_hash", "1" * 64),
        ("repository_id", "kg-mnp-attacker"),
        ("expected_graphdb_semantic_hash", "1" * 64),
        ("live_graphdb_semantic_hash", "1" * 64),
        ("status", "APPLICATION_NOT_READY"),
    ],
)
def test_runtime_identity_tampering_fails_closed(tmp_path, field, value) -> None:
    binding = WorkbenchBinding.load(write_phase01_artifact(tmp_path / "phase01"))
    attacked = health()
    attacked[field] = value
    with pytest.raises(WorkbenchError, match="WORKBENCH_NOT_READY"):
        binding.verify_health(attacked)


def test_rehashed_or_stale_phase01_attestation_fails_closed(tmp_path) -> None:
    artifact = write_phase01_artifact(tmp_path / "phase01")
    attestation_path = artifact / "application-attestation.json"
    attestation = json.loads(attestation_path.read_text(encoding="utf-8"))
    attestation["query_registry_hash"] = "1" * 64
    attestation_path.write_text(json.dumps(attestation), encoding="utf-8")
    with pytest.raises(WorkbenchError, match="WORKBENCH_NOT_READY"):
        WorkbenchBinding.load(artifact)
