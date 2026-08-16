from __future__ import annotations

import inspect
from dataclasses import FrozenInstanceError
from pathlib import Path
from types import SimpleNamespace

import pytest

import kg_mnp_demo.activation.authority_binding as authority_binding_module
from kg_mnp_demo.activation.authority_binding import (
    BASE_LINEAGE_SOURCE_TYPE,
    PRODUCTION_AUTHORITY_TYPE,
    ControlledPhase06Authority,
    ProductionPhase06Authority,
    VerifiedPublicationTarget,
    load_production_phase06_authority,
    require_production_phase06_authority,
)
from kg_mnp_demo.activation.errors import ActivationError, ActivationErrorCode
from kg_mnp_demo.modeling.canonical_json import canonical_json_bytes

COMMIT = "a" * 40
P0_HASH = "b" * 64
P1_HASH = "c" * 64
REPOSITORY_HASH = "d" * 64
P1_REPOSITORY_HASH = "e" * 64
FIXTURE_HASH = "f" * 64


def _write_json(path: Path, value: dict) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_bytes(canonical_json_bytes(value) + b"\n")


def _production_sources(tmp_path: Path) -> dict[str, Path]:
    roots = {
        "publication_package_directory": tmp_path / "stage08",
        "phase01_artifact_directory": tmp_path / "phase01",
        "phase02_artifact_directory": tmp_path / "phase02",
        "phase03_artifact_directory": tmp_path / "phase03",
        "phase04_artifact_directory": tmp_path / "phase04",
        "phase05_artifact_directory": tmp_path / "phase05",
    }
    for name, root in roots.items():
        root.mkdir(parents=True)
        _write_json(root / "tree-marker.json", {"source": name})
    report = tmp_path / "stage08-report"
    report.mkdir()
    attestation = report / "publication-attestation.json"
    _write_json(attestation, {"status": "PUBLICATION_VERIFIED"})
    roots["publication_attestation_path"] = attestation
    for phase in ("phase02", "phase03", "phase04"):
        filename = {
            "phase02": "application-phase02-attestation.json",
            "phase03": "application-phase03-attestation.json",
            "phase04": "application-phase04-attestation.json",
        }[phase]
        _write_json(
            roots[f"{phase}_artifact_directory"] / filename, {"commit_sha": COMMIT}
        )
    _write_json(
        roots["phase05_artifact_directory"] / "application-phase05-attestation.json",
        {
            "commit_sha": COMMIT,
            "production_reentry_cycles": 0,
            "production_new_publications": 0,
            "status": "APPLICATION_AMENDMENT_REPUBLICATION_VERIFIED",
        },
    )
    return roots


def _patch_production_reconstruction(
    monkeypatch: pytest.MonkeyPatch,
    *,
    mutate_during_publication_verification: Path | None = None,
) -> dict[str, int]:
    calls = {"phase05_loader": 0, "phase05_verifier": 0, "publication": 0}

    def phase05_loader(**_kwargs):
        calls["phase05_loader"] += 1
        return SimpleNamespace(
            commit_sha=COMMIT,
            publication_id=f"urn:kg-mnp:e2e-publication:{P0_HASH}",
            publication_semantic_hash=P0_HASH,
            repository_semantic_hash=REPOSITORY_HASH,
            production_pending_amendments=0,
        )

    def phase05_verifier(*_args, **_kwargs):
        calls["phase05_verifier"] += 1
        return {
            "commit_sha": COMMIT,
            "production_pending_amendments": 0,
            "status": "APPLICATION_AMENDMENT_REPUBLICATION_VERIFIED",
        }

    def publication_verifier(*_args, **_kwargs):
        calls["publication"] += 1
        if mutate_during_publication_verification is not None:
            mutate_during_publication_verification.write_bytes(b"changed")
        return SimpleNamespace(
            publication_id=f"urn:kg-mnp:e2e-publication:{P0_HASH}",
            publication_semantic_hash=P0_HASH,
            repository_id="kg-mnp-production-p0",
            graphdb_semantic_hash=REPOSITORY_HASH,
        )

    monkeypatch.setattr(
        authority_binding_module,
        "load_production_phase05_authority",
        phase05_loader,
    )
    monkeypatch.setattr(
        authority_binding_module,
        "verify_application_phase05_artifact",
        phase05_verifier,
    )
    monkeypatch.setattr(
        authority_binding_module.PublicationBinding,
        "verify",
        publication_verifier,
    )
    return calls


def _load(sources: dict[str, Path]) -> ProductionPhase06Authority:
    return load_production_phase06_authority(
        **sources,
        expected_commit_sha=COMMIT,
    )


def test_production_loader_signature_has_only_physical_trust_roots() -> None:
    parameters = inspect.signature(load_production_phase06_authority).parameters
    assert tuple(parameters) == (
        "publication_package_directory",
        "publication_attestation_path",
        "phase01_artifact_directory",
        "phase02_artifact_directory",
        "phase03_artifact_directory",
        "phase04_artifact_directory",
        "phase05_artifact_directory",
        "expected_commit_sha",
        "publication_scenario",
    )
    assert all(
        parameter.kind is inspect.Parameter.KEYWORD_ONLY
        for parameter in parameters.values()
    )
    assert not {
        "authority",
        "phase05_authority",
        "republication_result",
        "target_publication",
        "repository_hash",
        "current_pointer",
        "registry",
        "activation_candidates",
    } & set(parameters)


def test_production_loader_reconstructs_p0_and_empty_candidates(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    sources = _production_sources(tmp_path)
    calls = _patch_production_reconstruction(monkeypatch)

    authority = _load(sources)

    assert authority.authority_type == PRODUCTION_AUTHORITY_TYPE
    assert authority.test_only is False
    assert authority.production_authority is True
    assert authority.commit_sha == COMMIT
    assert authority.activation_candidates == ()
    assert authority.production_activation_candidate_count == 0
    assert authority.base_publication.lineage_source_type == BASE_LINEAGE_SOURCE_TYPE
    assert authority.base_publication.repository_id == "kg-mnp-production-p0"
    assert (
        authority.base_publication.package_directory
        == sources["publication_package_directory"].resolve()
    )
    assert authority.resolve_target(authority.base_publication.publication_id) is (
        authority.base_publication
    )
    assert (
        len(authority.target_binding_hash(authority.base_publication.publication_id))
        == 64
    )
    assert calls == {"phase05_loader": 1, "phase05_verifier": 1, "publication": 1}
    assert authority.binding["production_activation_candidates"] == []
    assert "controlled_fixture_hash" not in authority.binding


def test_production_authority_is_reverified_and_rebuilt_on_require(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    sources = _production_sources(tmp_path)
    calls = _patch_production_reconstruction(monkeypatch)
    authority = _load(sources)

    verified = require_production_phase06_authority(authority)

    assert verified is not authority
    assert verified.binding == authority.binding
    assert calls == {"phase05_loader": 2, "phase05_verifier": 2, "publication": 2}

    (sources["phase03_artifact_directory"] / "tree-marker.json").write_bytes(
        b'{"changed":true}\n'
    )
    with pytest.raises(ActivationError) as caught:
        require_production_phase06_authority(authority)
    assert caught.value.code == ActivationErrorCode.AUTHORITY_MISMATCH


def test_upstream_tree_change_during_reconstruction_is_rejected(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    sources = _production_sources(tmp_path)
    marker = sources["phase01_artifact_directory"] / "tree-marker.json"
    _patch_production_reconstruction(
        monkeypatch,
        mutate_during_publication_verification=marker,
    )

    with pytest.raises(ActivationError) as caught:
        _load(sources)
    assert caught.value.code == ActivationErrorCode.AUTHORITY_MISMATCH


def test_production_types_cannot_be_directly_minted() -> None:
    with pytest.raises(TypeError):
        ProductionPhase06Authority()
    with pytest.raises(TypeError):
        VerifiedPublicationTarget()
    forged = object.__new__(ProductionPhase06Authority)
    object.__setattr__(forged, "test_only", False)
    object.__setattr__(forged, "production_authority", True)
    object.__setattr__(forged, "_production_source", None)
    with pytest.raises(ActivationError) as caught:
        require_production_phase06_authority(forged)
    assert caught.value.code == ActivationErrorCode.AUTHORITY_MISMATCH


def _controlled_package(
    root: Path,
    *,
    publication_hash: str,
    repository_id: str,
    repository_hash: str,
    role: str,
) -> tuple[Path, dict, Path]:
    package = root / role.casefold()
    publication_id = f"urn:kg-mnp:e2e-publication:{publication_hash}"
    manifest = {
        "publication_id": publication_id,
        "publication_semantic_hash": publication_hash,
    }
    graphdb = {
        "repository_id": repository_id,
        "assembled_dataset_semantic_hash": repository_hash,
    }
    _write_json(package / "publication-manifest.json", manifest)
    _write_json(package / "source/graphdb-import-manifest.json", graphdb)
    attestation = root / f"{role.casefold()}-controlled-attestation.json"
    _write_json(
        attestation,
        {
            "contract_version": "1.0",
            "fixture_type": "PHASE06_CONTROLLED_ACTIVATION_FIXTURE",
            "test_only": True,
            "production_authority": False,
            "controlled_fixture_hash": FIXTURE_HASH,
            "publication_role": role,
            "publication_id": publication_id,
            "publication_semantic_hash": publication_hash,
            "repository_id": repository_id,
            "repository_semantic_hash": repository_hash,
            "phase05_publication_status": (
                "VERIFIED_IMMUTABLE_BASE_PUBLICATION"
                if role == "P0"
                else "VERIFIED_NEW_PUBLICATION_NOT_ACTIVATED"
            ),
            "semantic_authority": False,
            "deployment_governance_only": True,
            "status": "CONTROLLED_PHASE05_PUBLICATION_VERIFIED",
        },
    )
    return package, manifest, attestation


def test_controlled_authority_is_namespaced_immutable_and_never_production(
    tmp_path: Path,
) -> None:
    p0_package, p0_manifest, p0_attestation = _controlled_package(
        tmp_path,
        publication_hash=P0_HASH,
        repository_id="kg-mnp-controlled-p0",
        repository_hash=REPOSITORY_HASH,
        role="P0",
    )
    p1_package, p1_manifest, p1_attestation = _controlled_package(
        tmp_path,
        publication_hash=P1_HASH,
        repository_id="kg-mnp-controlled-p1",
        repository_hash=P1_REPOSITORY_HASH,
        role="P1",
    )

    authority = ControlledPhase06Authority.create(
        p0_package_directory=p0_package,
        p0_manifest=p0_manifest,
        p0_attestation_path=p0_attestation,
        p1_package_directory=p1_package,
        p1_manifest=p1_manifest,
        p1_attestation_path=p1_attestation,
    )

    assert authority.fixture_id.startswith("urn:kg-mnp:test-fixture:phase06:")
    assert authority.controlled_fixture_hash == FIXTURE_HASH
    assert authority.test_only is True
    assert authority.production_authority is False
    assert len(authority.activation_candidates) == 1
    assert authority.base_publication.test_only is True
    assert (
        authority.base_publication.lineage_source_type == "CONTROLLED_PHASE06_BOOTSTRAP"
    )
    assert (
        authority.activation_candidates[0].lineage_source_type
        == "CONTROLLED_PHASE05_VERIFIED_PUBLICATION"
    )
    assert authority.activation_candidates[0].controlled_fixture_hash == FIXTURE_HASH
    assert set(authority.base_publication.descriptor) == {
        "publication_id",
        "publication_semantic_hash",
        "repository_id",
        "repository_semantic_hash",
        "publication_attestation_sha256",
        "lineage_source_type",
        "lineage_source_attestation_sha256",
    }
    projected = authority.base_publication.descriptor
    projected["repository_id"] = "attacker"
    assert authority.base_publication.repository_id == "kg-mnp-controlled-p0"
    with pytest.raises(FrozenInstanceError):
        authority.base_publication.repository_id = "attacker"  # type: ignore[misc]

    with pytest.raises(ActivationError) as caught:
        require_production_phase06_authority(authority)
    assert (
        caught.value.code
        == ActivationErrorCode.TEST_FIXTURE_NOT_ALLOWED_AS_PRODUCTION_ACTIVATION_TARGET
    )


def test_production_loader_rejects_fixture_paths_before_upstream_calls(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    sources = _production_sources(tmp_path / "test-fixture-laundering")
    calls = _patch_production_reconstruction(monkeypatch)

    with pytest.raises(ActivationError) as caught:
        _load(sources)
    assert (
        caught.value.code
        == ActivationErrorCode.TEST_FIXTURE_NOT_ALLOWED_AS_PRODUCTION_ACTIVATION_TARGET
    )
    assert calls == {"phase05_loader": 0, "phase05_verifier": 0, "publication": 0}
