from __future__ import annotations

import hashlib
import inspect
from collections.abc import Iterator, Mapping
from contextlib import contextmanager
from copy import deepcopy
from dataclasses import dataclass
from pathlib import Path
from typing import Any

import pytest

from kg_mnp_demo.activation import artifact_verifier
from kg_mnp_demo.activation.artifact_verifier import (
    FILES,
    Phase06ArtifactVerificationError,
    verify_application_phase06_artifact,
)
from kg_mnp_demo.activation.attestation import publication_tree_sha256
from kg_mnp_demo.activation.errors import ActivationError, ActivationErrorCode
from kg_mnp_demo.activation.registry import new_activation_registry
from kg_mnp_demo.activation.reporting import (
    ATTACK_COUNTER_FIELDS,
    build_probe_record,
)
from kg_mnp_demo.activation.validator import (
    validate_activation_registry_against_authorities,
)
from kg_mnp_demo.modeling.canonical_json import canonical_json_bytes, semantic_hash
from scripts.activation_controlled_fixture import run_controlled_activation_workflow
from scripts.activation_integration import _artifact_documents

COMMIT_SHA = "a" * 40

_EXPECTED_CODE = {
    "activation_review": "APPROVE_FOR_ACTIVATION",
    "unverified_target": "UNVERIFIED_ACTIVATION_TARGET",
    "fixture_laundering": ("TEST_FIXTURE_NOT_ALLOWED_AS_PRODUCTION_ACTIVATION_TARGET"),
    "pointer_tamper": "POINTER_TAMPERED",
    "event_rehash": "AUTHORITY_MISMATCH",
    "stale_pointer": "ACTIVATION_CONCURRENCY_CONFLICT",
    "concurrency": "ACTIVATION_CONCURRENCY_CONFLICT",
    "replay": "REPLAY_DETECTED",
    "missing_repository": "TARGET_REPOSITORY_UNAVAILABLE",
    "repository_mismatch": "TARGET_REPOSITORY_HASH_MISMATCH",
    "direct_graph_mutation": "DIRECT_GRAPH_MUTATION_BLOCKED",
    "semantic_escalation": "SEMANTIC_AUTHORITY_ESCALATION_BLOCKED",
    "auto_activation": "HUMAN_ACTIVATION_APPROVAL_REQUIRED",
    "unknown_rollback": "UNKNOWN_ROLLBACK_TARGET",
}


@dataclass(frozen=True)
class _Target:
    publication_id: str
    publication_semantic_hash: str
    repository_id: str
    repository_semantic_hash: str
    publication_attestation_sha256: str
    lineage_source_type: str
    lineage_source_attestation_sha256: str
    package_directory: Path
    attestation_path: Path
    publication_tree_sha256: str
    test_only: bool
    production_authority: bool

    @property
    def descriptor(self) -> dict[str, str]:
        return {
            "publication_id": self.publication_id,
            "publication_semantic_hash": self.publication_semantic_hash,
            "repository_id": self.repository_id,
            "repository_semantic_hash": self.repository_semantic_hash,
            "publication_attestation_sha256": self.publication_attestation_sha256,
            "lineage_source_type": self.lineage_source_type,
            "lineage_source_attestation_sha256": (
                self.lineage_source_attestation_sha256
            ),
        }


class _Authority:
    def __init__(
        self,
        *,
        base: object,
        candidates: tuple[object, ...],
        test_only: bool,
        fixture_hash: str | None = None,
    ) -> None:
        self.base_publication = base
        self.activation_candidates = candidates
        self.test_only = test_only
        self.production_authority = not test_only
        self.authority_type = (
            "CONTROLLED_PHASE06_TEST_HARNESS"
            if test_only
            else "PRODUCTION_EXACT_PHASE05"
        )
        self.controlled_fixture_hash = fixture_hash
        self.fixture_id = (
            "urn:kg-mnp:test-fixture:phase06:authority:"
            + semantic_hash(
                {
                    "base": self._descriptor(base),
                    "candidates": [self._descriptor(item) for item in candidates],
                }
            )
            if test_only
            else None
        )
        for field in (
            "stage08_artifact_tree_sha256",
            "publication_attestation_tree_sha256",
            "phase01_artifact_tree_sha256",
            "phase02_artifact_tree_sha256",
            "phase03_artifact_tree_sha256",
            "phase04_artifact_tree_sha256",
            "phase05_artifact_tree_sha256",
            "phase05_attestation_sha256",
        ):
            setattr(self, field, semantic_hash({"physical_identity": field}))

    @staticmethod
    def _descriptor(target: object) -> dict[str, str]:
        return deepcopy(target.descriptor)  # type: ignore[attr-defined]

    @property
    def production_activation_candidate_count(self) -> int:
        return len(self.activation_candidates)

    @property
    def binding(self) -> dict[str, Any]:
        if self.test_only:
            return {
                "authority_type": self.authority_type,
                "fixture_id": self.fixture_id,
                "controlled_fixture_hash": self.controlled_fixture_hash,
                "base_publication": self._descriptor(self.base_publication),
                "activation_candidates": [
                    self._descriptor(item) for item in self.activation_candidates
                ],
                "test_only": True,
                "production_authority": False,
            }
        return {
            "authority_type": self.authority_type,
            "commit_sha": COMMIT_SHA,
            "stage08_artifact_tree_sha256": self.stage08_artifact_tree_sha256,
            "publication_attestation_tree_sha256": (
                self.publication_attestation_tree_sha256
            ),
            "phase01_artifact_tree_sha256": self.phase01_artifact_tree_sha256,
            "phase02_artifact_tree_sha256": self.phase02_artifact_tree_sha256,
            "phase03_artifact_tree_sha256": self.phase03_artifact_tree_sha256,
            "phase04_artifact_tree_sha256": self.phase04_artifact_tree_sha256,
            "phase05_artifact_tree_sha256": self.phase05_artifact_tree_sha256,
            "phase05_attestation_sha256": self.phase05_attestation_sha256,
            "base_publication": self._descriptor(self.base_publication),
            "production_activation_candidates": [],
            "test_only": False,
            "production_authority": True,
        }

    @property
    def binding_hash(self) -> str:
        return semantic_hash(self.binding)

    def resolve_target(self, publication_id: str) -> object:
        for target in (self.base_publication, *self.activation_candidates):
            if self._descriptor(target)["publication_id"] == publication_id:
                return target
        raise ActivationError(ActivationErrorCode.UNVERIFIED_ACTIVATION_TARGET)

    def target_binding_hash(self, publication_id: str) -> str:
        return semantic_hash(
            {
                "authority_binding_hash": self.binding_hash,
                "target": self._descriptor(self.resolve_target(publication_id)),
            }
        )


class _DescriptorVerifier:
    def verify(self, target: object) -> Mapping[str, str]:
        descriptor = target.descriptor  # type: ignore[attr-defined]
        return {
            "publication_tree_sha256": target.publication_tree_sha256,
            "publication_attestation_sha256": descriptor[
                "publication_attestation_sha256"
            ],
            "expected_repository_semantic_hash": descriptor["repository_semantic_hash"],
            "live_repository_semantic_hash": descriptor["repository_semantic_hash"],
        }


def _production_target(controlled_target: object) -> _Target:
    descriptor = controlled_target.descriptor  # type: ignore[attr-defined]
    digest = descriptor["publication_semantic_hash"]
    return _Target(
        publication_id="urn:kg-mnp:publication:" + digest,
        publication_semantic_hash=digest,
        repository_id="kg-mnp-production-bootstrap",
        repository_semantic_hash=descriptor["repository_semantic_hash"],
        publication_attestation_sha256=descriptor["publication_attestation_sha256"],
        lineage_source_type="BOOTSTRAP_CURRENT_REFERENCE",
        lineage_source_attestation_sha256=descriptor[
            "lineage_source_attestation_sha256"
        ],
        package_directory=controlled_target.package_directory,  # type: ignore[attr-defined]
        attestation_path=controlled_target.attestation_path,  # type: ignore[attr-defined]
        publication_tree_sha256=controlled_target.publication_tree_sha256,  # type: ignore[attr-defined]
        test_only=False,
        production_authority=True,
    )


def _probes() -> list[dict[str, Any]]:
    records = []
    assert set(_EXPECTED_CODE) == set(ATTACK_COUNTER_FIELDS)
    for attack, expected_code in _EXPECTED_CODE.items():
        records.append(
            build_probe_record(
                attack=attack,
                expected_code=expected_code,
                observed_code=expected_code,
                blocked=attack != "activation_review",
                details=f"Executed deterministic {attack.replace('_', ' ')} probe.",
            )
        )
    return records


def _supplemental_probe(attack: str, details: str) -> dict[str, Any]:
    content = {
        "attack": attack,
        "expected_code": "PATH_REJECTED",
        "observed_code": "PATH_REJECTED",
        "blocked": True,
        "details": details,
    }
    return {
        "probe_id": "urn:kg-mnp:test-fixture:phase06:supplemental-probe:"
        + semantic_hash(content),
        **content,
    }


def _repository_hashes(authority: object) -> dict[str, str]:
    p0 = authority.base_publication  # type: ignore[attr-defined]
    p1 = authority.activation_candidates[0]  # type: ignore[attr-defined]
    return {
        "p0_before": p0.repository_semantic_hash,
        "p1_before": p1.repository_semantic_hash,
        "p0_after_activation": p0.repository_semantic_hash,
        "p1_after_activation": p1.repository_semantic_hash,
        "p0_after_rollback": p0.repository_semantic_hash,
        "p1_after_rollback": p1.repository_semantic_hash,
    }


def _publication_hashes(authority: object) -> dict[str, str]:
    p0 = authority.base_publication  # type: ignore[attr-defined]
    p1 = authority.activation_candidates[0]  # type: ignore[attr-defined]
    return {
        "p0_before": publication_tree_sha256(p0.package_directory),
        "p1_before": publication_tree_sha256(p1.package_directory),
        "p0_after": publication_tree_sha256(p0.package_directory),
        "p1_after": publication_tree_sha256(p1.package_directory),
    }


def _documents(
    production: _Authority,
    production_registry: dict[str, Any],
    production_pointer: dict[str, Any],
    fixture: dict[str, Any],
    workflow: dict[str, Any],
) -> dict[str, dict[str, Any]]:
    production_state = validate_activation_registry_against_authorities(
        production_registry,
        production,
        current_pointer=production_pointer,
    )
    return _artifact_documents(
        commit_sha=COMMIT_SHA,
        authority=production,
        production_initial_registry=production_registry,
        production_initial_pointer=production_pointer,
        production_final_registry=production_registry,
        production_final_pointer=production_pointer,
        production_final_state=production_state,
        fixture=fixture,
        workflow=workflow,
        probes=_probes(),
        supplemental_probes=[
            _supplemental_probe(
                "double_encoded_path", "Rejected encoded traversal input."
            ),
            _supplemental_probe("symlink_escape", "Rejected symbolic indirection."),
        ],
        race={
            "processes": 2,
            "success": 1,
            "blocked": 1,
            "outcomes": [
                "ACTIVATION_APPLIED",
                "ACTIVATION_CONCURRENCY_CONFLICT",
            ],
            "final_generation": 1,
            "status": "CONTROLLED_PROCESS_RACE_VERIFIED",
        },
        repository_hashes=_repository_hashes(fixture["authority"]),
        publication_hashes=_publication_hashes(fixture["authority"]),
        cleanup={
            "controlled_repository_count": 2,
            "cleanup_failures": 0,
            "status": "PASS",
        },
        determinism_runs=2,
        determinism_passed=2,
    )


@pytest.fixture(scope="module")
def corpus(tmp_path_factory: pytest.TempPathFactory) -> dict[str, Any]:
    root = tmp_path_factory.mktemp("phase06-artifact-corpus")
    p0_directory = root / "trusted-fixture" / "p0"
    p1_directory = root / "trusted-fixture" / "p1"
    p0_directory.mkdir(parents=True)
    p1_directory.mkdir(parents=True)
    (p0_directory / "immutable-publication.txt").write_text(
        "controlled P0\n", encoding="utf-8"
    )
    (p1_directory / "immutable-publication.txt").write_text(
        "controlled P1\n", encoding="utf-8"
    )
    p0_attestation_path = root / "trusted-fixture" / "p0-attestation.json"
    p1_attestation_path = root / "trusted-fixture" / "p1-attestation.json"
    p0_attestation_path.write_bytes(b'{"controlled_publication":"P0"}\n')
    p1_attestation_path.write_bytes(b'{"controlled_publication":"P1"}\n')
    p0_semantic_hash = semantic_hash({"controlled_publication": "P0"})
    p1_semantic_hash = semantic_hash({"controlled_publication": "P1"})
    p0 = _Target(
        publication_id=(
            "urn:kg-mnp:test-fixture:phase06:publication:" + p0_semantic_hash
        ),
        publication_semantic_hash=p0_semantic_hash,
        repository_id="kg-mnp-controlled-p0",
        repository_semantic_hash=semantic_hash({"controlled_repository": "P0"}),
        publication_attestation_sha256=hashlib.sha256(
            p0_attestation_path.read_bytes()
        ).hexdigest(),
        lineage_source_type="CONTROLLED_PHASE06_BOOTSTRAP",
        lineage_source_attestation_sha256=semantic_hash({"controlled_lineage": "P0"}),
        package_directory=p0_directory,
        attestation_path=p0_attestation_path,
        publication_tree_sha256=publication_tree_sha256(p0_directory),
        test_only=True,
        production_authority=False,
    )
    p1 = _Target(
        publication_id=(
            "urn:kg-mnp:test-fixture:phase06:publication:" + p1_semantic_hash
        ),
        publication_semantic_hash=p1_semantic_hash,
        repository_id="kg-mnp-controlled-p1",
        repository_semantic_hash=semantic_hash({"controlled_repository": "P1"}),
        publication_attestation_sha256=hashlib.sha256(
            p1_attestation_path.read_bytes()
        ).hexdigest(),
        lineage_source_type="CONTROLLED_PHASE05_VERIFIED_PUBLICATION",
        lineage_source_attestation_sha256=semantic_hash({"controlled_lineage": "P1"}),
        package_directory=p1_directory,
        attestation_path=p1_attestation_path,
        publication_tree_sha256=publication_tree_sha256(p1_directory),
        test_only=True,
        production_authority=False,
    )
    controlled_authority = _Authority(
        base=p0,
        candidates=(p1,),
        test_only=True,
        fixture_hash=semantic_hash({"controlled_fixture": "trusted"}),
    )
    fixture = {
        "authority": controlled_authority,
        "offline_verifier": _DescriptorVerifier(),
    }
    workflow = run_controlled_activation_workflow(
        fixture=fixture,
        state_directory=root / "trusted-state",
        verifier=fixture["offline_verifier"],
    )
    production = _Authority(
        base=_production_target(fixture["authority"].base_publication),
        candidates=(),
        test_only=False,
    )
    production_registry, production_pointer = new_activation_registry(production)
    documents = _documents(
        production,
        production_registry,
        production_pointer,
        fixture,
        workflow,
    )
    return {
        "root": root,
        "fixture": fixture,
        "workflow": workflow,
        "production": production,
        "production_registry": production_registry,
        "production_pointer": production_pointer,
        "documents": documents,
    }


def _write_artifact(root: Path, documents: Mapping[str, Mapping[str, Any]]) -> Path:
    artifact = root / "artifact"
    artifact.mkdir(parents=True)
    for name, value in documents.items():
        (artifact / name).write_bytes(canonical_json_bytes(value) + b"\n")
    return artifact


def _patch_reconstruction(
    monkeypatch: pytest.MonkeyPatch,
    corpus: Mapping[str, Any],
    *,
    authority: object | None = None,
) -> None:
    monkeypatch.setattr(
        artifact_verifier,
        "load_production_phase06_authority",
        lambda **_arguments: authority or corpus["production"],
    )

    @contextmanager
    def reconstructed() -> Iterator[tuple[dict[str, Any], dict[str, Any]]]:
        yield corpus["fixture"], corpus["workflow"]

    monkeypatch.setattr(artifact_verifier, "_controlled_reconstruction", reconstructed)


def _verify(
    artifact: Path,
    monkeypatch: pytest.MonkeyPatch,
    corpus: Mapping[str, Any],
    *,
    registry_hash: str | None = None,
    head_event_hash: str | None = None,
    authority: object | None = None,
) -> dict[str, Any]:
    _patch_reconstruction(monkeypatch, corpus, authority=authority)
    state = corpus["workflow"]["final_state"]
    return verify_application_phase06_artifact(
        artifact,
        publication_package_directory=artifact.parent / "upstream-stage08",
        publication_attestation_path=artifact.parent / "publication-attestation.json",
        publication_scenario="full-confirmation",
        phase01_artifact_directory=artifact.parent / "phase01",
        phase02_artifact_directory=artifact.parent / "phase02",
        phase03_artifact_directory=artifact.parent / "phase03",
        phase04_artifact_directory=artifact.parent / "phase04",
        phase05_artifact_directory=artifact.parent / "phase05",
        expected_commit_sha=COMMIT_SHA,
        expected_registry_hash=registry_hash or state["registry_hash"],
        expected_head_event_hash=head_event_hash or state["head_event_hash"],
    )


def test_valid_exact_artifact_is_independently_reconstructed(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch, corpus: Mapping[str, Any]
) -> None:
    artifact = _write_artifact(tmp_path, corpus["documents"])

    result = _verify(artifact, monkeypatch, corpus)

    assert result["artifact_files"] == sorted(FILES)
    assert result["controlled_activation_cycles"] == 1
    assert result["controlled_rollback_cycles"] == 1
    assert result["status"] == "APPLICATION_PUBLICATION_ACTIVATION_VERIFIED"


def test_verifier_signature_has_no_caller_injected_phase06_trust_root() -> None:
    parameters = inspect.signature(verify_application_phase06_artifact).parameters
    forbidden = {
        "authority",
        "phase06_authority",
        "registry",
        "current_pointer",
        "target_publication",
        "eligible_targets",
    }

    assert forbidden.isdisjoint(parameters)
    assert parameters["expected_registry_hash"].default is inspect.Parameter.empty
    assert parameters["expected_head_event_hash"].default is inspect.Parameter.empty


@pytest.mark.parametrize("change", ["missing", "extra"])
def test_exact_five_file_closed_set_is_enforced(
    change: str,
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
    corpus: Mapping[str, Any],
) -> None:
    documents = deepcopy(corpus["documents"])
    if change == "missing":
        documents.pop("rollback-summary.json")
    else:
        documents["unexpected.json"] = {"status": "PASS"}
    artifact = _write_artifact(tmp_path, documents)

    with pytest.raises(Phase06ArtifactVerificationError, match="closed set"):
        _verify(artifact, monkeypatch, corpus)


def test_artifact_directory_symlink_is_rejected(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch, corpus: Mapping[str, Any]
) -> None:
    real = _write_artifact(tmp_path / "real", corpus["documents"])
    linked = tmp_path / "linked-artifact"
    try:
        linked.symlink_to(real, target_is_directory=True)
    except OSError:
        pytest.skip("directory symlinks are unavailable to this test user")

    with pytest.raises(Phase06ArtifactVerificationError, match="unsafe"):
        _verify(linked, monkeypatch, corpus)


def test_artifact_file_symlink_is_rejected(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch, corpus: Mapping[str, Any]
) -> None:
    artifact = _write_artifact(tmp_path, corpus["documents"])
    path = artifact / "security-summary.json"
    outside = tmp_path / "outside-security-summary.json"
    outside.write_bytes(path.read_bytes())
    path.unlink()
    try:
        path.symlink_to(outside)
    except OSError:
        pytest.skip("file symlinks are unavailable to this test user")

    with pytest.raises(Phase06ArtifactVerificationError, match="closed set"):
        _verify(artifact, monkeypatch, corpus)


def test_duplicate_json_key_is_rejected(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch, corpus: Mapping[str, Any]
) -> None:
    artifact = _write_artifact(tmp_path, corpus["documents"])
    (artifact / "authority-binding.json").write_bytes(
        b'{"contract_version":"1.0","contract_version":"1.0"}\n'
    )

    with pytest.raises(Phase06ArtifactVerificationError, match="duplicate-free"):
        _verify(artifact, monkeypatch, corpus)


@pytest.mark.parametrize(
    ("field", "value"),
    [
        ("password", "operator supplied value"),
        ("access_token", "operator supplied value"),
        ("note", "C:\\Users\\operator\\phase06-artifact.json"),
        ("note", "/etc/kg-mnp/phase06-artifact.json"),
    ],
)
def test_secret_or_physical_path_content_is_rejected(
    field: str,
    value: str,
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
    corpus: Mapping[str, Any],
) -> None:
    documents = deepcopy(corpus["documents"])
    documents["authority-binding.json"][field] = value
    artifact = _write_artifact(tmp_path, documents)

    with pytest.raises(
        Phase06ArtifactVerificationError, match="secret|physical|path field"
    ):
        _verify(artifact, monkeypatch, corpus)


def test_bytes_changed_during_read_are_rejected(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch, corpus: Mapping[str, Any]
) -> None:
    artifact = _write_artifact(tmp_path, corpus["documents"])
    target = artifact / "activation-summary.json"
    original_read_bytes = Path.read_bytes
    calls = 0

    def racing_read_bytes(path: Path) -> bytes:
        nonlocal calls
        raw = original_read_bytes(path)
        if path == target:
            calls += 1
            if calls > 1:
                return raw + b" "
        return raw

    monkeypatch.setattr(Path, "read_bytes", racing_read_bytes)

    with pytest.raises(Phase06ArtifactVerificationError, match="changed"):
        _verify(artifact, monkeypatch, corpus)


def test_trusted_anchors_are_required_by_the_public_api(
    tmp_path: Path, corpus: Mapping[str, Any]
) -> None:
    artifact = _write_artifact(tmp_path, corpus["documents"])

    with pytest.raises(TypeError):
        verify_application_phase06_artifact(  # type: ignore[call-arg]
            artifact,
            publication_package_directory=tmp_path,
            publication_attestation_path=tmp_path / "attestation.json",
            publication_scenario="full-confirmation",
            phase01_artifact_directory=tmp_path,
            phase02_artifact_directory=tmp_path,
            phase03_artifact_directory=tmp_path,
            phase04_artifact_directory=tmp_path,
            phase05_artifact_directory=tmp_path,
            expected_commit_sha=COMMIT_SHA,
        )


@pytest.mark.parametrize("anchor", ["registry", "head"])
def test_wrong_trusted_anchor_is_rejected(
    anchor: str,
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
    corpus: Mapping[str, Any],
) -> None:
    artifact = _write_artifact(tmp_path, corpus["documents"])
    arguments = (
        {"registry_hash": "0" * 64}
        if anchor == "registry"
        else {"head_event_hash": "0" * 64}
    )

    with pytest.raises(Phase06ArtifactVerificationError, match="AUTHORITY_MISMATCH"):
        _verify(artifact, monkeypatch, corpus, **arguments)


@pytest.mark.parametrize("tamper", ["counter", "duplicate_probe"])
def test_probe_counters_are_recomputed_and_duplicate_records_are_rejected(
    tamper: str,
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
    corpus: Mapping[str, Any],
) -> None:
    documents = deepcopy(corpus["documents"])
    security = documents["security-summary.json"]
    if tamper == "counter":
        security["counters"]["replay_attempts"] += 1
    else:
        security["probe_records"].append(deepcopy(security["probe_records"][0]))
    artifact = _write_artifact(tmp_path, documents)

    with pytest.raises(Phase06ArtifactVerificationError, match="probe|security"):
        _verify(artifact, monkeypatch, corpus)


def test_rehashed_pointer_tamper_is_rejected(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch, corpus: Mapping[str, Any]
) -> None:
    documents = deepcopy(corpus["documents"])
    pointer = documents["activation-summary.json"]["controlled_activation_summary"][
        "final_pointer"
    ]
    pointer["active_repository_id"] = "attacker-controlled-repository"
    pointer["pointer_hash"] = semantic_hash(
        {key: value for key, value in pointer.items() if key != "pointer_hash"}
    )
    artifact = _write_artifact(tmp_path, documents)

    with pytest.raises(Phase06ArtifactVerificationError, match="AUTHORITY_MISMATCH"):
        _verify(artifact, monkeypatch, corpus)


def test_self_consistent_fake_p2_fails_against_fresh_controlled_authority(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch, corpus: Mapping[str, Any]
) -> None:
    trusted = corpus["fixture"]["authority"]
    real_p1 = trusted.activation_candidates[0]
    fake_hash = semantic_hash({"attacker_target": real_p1.publication_semantic_hash})
    fake_attestation_path = tmp_path / "fake-p2-attestation.json"
    fake_attestation_path.write_bytes(b'{"attacker_target":"P2"}\n')
    fake_p2 = _Target(
        publication_id="urn:kg-mnp:test-fixture:phase06:publication:" + fake_hash,
        publication_semantic_hash=fake_hash,
        repository_id="kg-mnp-controlled-attacker-p2",
        repository_semantic_hash=semantic_hash({"attacker_repository": fake_hash}),
        publication_attestation_sha256=hashlib.sha256(
            fake_attestation_path.read_bytes()
        ).hexdigest(),
        lineage_source_type=real_p1.lineage_source_type,
        lineage_source_attestation_sha256=semantic_hash(
            {"attacker_lineage": fake_hash}
        ),
        package_directory=real_p1.package_directory,
        attestation_path=fake_attestation_path,
        publication_tree_sha256=real_p1.publication_tree_sha256,
        test_only=True,
        production_authority=False,
    )
    fake_authority = _Authority(
        base=trusted.base_publication,
        candidates=(fake_p2,),
        test_only=True,
        fixture_hash=semantic_hash({"attacker_fixture": fake_hash}),
    )
    fake_fixture = {"authority": fake_authority}
    fake_workflow = run_controlled_activation_workflow(
        fixture=fake_fixture,
        state_directory=tmp_path / "fake-state",
        verifier=_DescriptorVerifier(),
    )
    fake_documents = _documents(
        corpus["production"],
        corpus["production_registry"],
        corpus["production_pointer"],
        fake_fixture,
        fake_workflow,
    )
    artifact = _write_artifact(tmp_path / "fake-artifact-root", fake_documents)

    with pytest.raises(Phase06ArtifactVerificationError, match="AUTHORITY_MISMATCH"):
        _verify(
            artifact,
            monkeypatch,
            corpus,
            registry_hash=fake_workflow["final_state"]["registry_hash"],
            head_event_hash=fake_workflow["final_state"]["head_event_hash"],
        )


def test_authority_binding_must_match_physical_reconstruction(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch, corpus: Mapping[str, Any]
) -> None:
    documents = deepcopy(corpus["documents"])
    documents["authority-binding.json"]["phase05_artifact_tree_sha256"] = "f" * 64
    artifact = _write_artifact(tmp_path, documents)

    with pytest.raises(Phase06ArtifactVerificationError, match="AUTHORITY_MISMATCH"):
        _verify(artifact, monkeypatch, corpus)
