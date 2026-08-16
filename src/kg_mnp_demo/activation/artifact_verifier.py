"""Independent exact-five-file Application Phase 06 artifact verifier.

Neither an activation authority nor a publication target can be supplied by the
caller.  Production authority is reconstructed from Stage08--Phase05 physical
artifacts, while controlled state is replayed from a fresh deterministic fixture.
"""

from __future__ import annotations

import os
import re
import stat
from collections.abc import Iterator, Mapping
from contextlib import contextmanager
from copy import deepcopy
from pathlib import Path
from tempfile import TemporaryDirectory
from typing import Any

from kg_mnp_demo._path_security import UnsafePathError, validated_directory
from kg_mnp_demo.modeling.canonical_json import semantic_hash

from .attestation import publication_tree_sha256
from .authority_binding import load_production_phase06_authority
from .contracts import strict_json_bytes, validate_activation_contract
from .errors import ActivationError
from .registry import new_activation_registry
from .reporting import (
    ATTACK_COUNTER_FIELDS,
    aggregate_probe_records,
    build_application_phase06_attestation,
)
from .validator import validate_activation_registry_against_authorities

FILES = frozenset(
    {
        "application-phase06-attestation.json",
        "activation-summary.json",
        "rollback-summary.json",
        "authority-binding.json",
        "security-summary.json",
    }
)
HASH = re.compile(r"^[0-9a-f]{64}$")
COMMIT = re.compile(r"^[0-9a-f]{40}$")
SUPPLEMENTAL_ID = re.compile(
    r"^urn:kg-mnp:test-fixture:phase06:supplemental-probe:[0-9a-f]{64}$"
)
MAX_FILE_BYTES = 8 * 1024 * 1024
MAX_ARTIFACT_BYTES = 24 * 1024 * 1024

_SECRET_KEYS = frozenset(
    {
        "authorization",
        "accesstoken",
        "accesskey",
        "apikey",
        "clientsecret",
        "credential",
        "graphdblicensecontent",
        "graphdblicenseb64",
        "password",
        "privatekey",
        "refreshtoken",
        "secret",
        "secretkey",
        "token",
    }
)
_PATH_KEYS = frozenset(
    {
        "authoritypath",
        "directory",
        "filepath",
        "packagepath",
        "path",
        "pointerpath",
        "registrypath",
    }
)
_SECRET_VALUE = re.compile(
    r"(?i)(?:-----BEGIN [A-Z ]*PRIVATE KEY-----|gh[pousr]_[A-Za-z0-9_]{20,}|"
    r"bearer\s+[A-Za-z0-9._~-]{12,}|sk-[A-Za-z0-9_-]{20,}|AKIA[0-9A-Z]{16})"
)
_ABSOLUTE_PATH = re.compile(
    r"(?i)(?:\bfile://|[a-z]:[\\/]|(?:^|\s)/(?!/)[^\s]*|"
    r"(?:^|\s)\\\\[^\\/\s]+[\\/]|(?:^|\s)(?:runtime_outputs|runtime_reports)[\\/]|"
    r"(?:^|[\\/])\.\.(?:[\\/]|$)|%2e|%2f|%5c)"
)


class Phase06ArtifactVerificationError(ValueError):
    """The Phase 06 artifact cannot be independently established as trusted."""


def _normalized_key(value: str) -> str:
    return re.sub(r"[^a-z0-9]", "", value.casefold())


def _link_like(path: Path) -> bool:
    try:
        if path.is_symlink():
            return True
        is_junction = getattr(path, "is_junction", None)
        if is_junction is not None and is_junction():
            return True
        attributes = getattr(path.lstat(), "st_file_attributes", 0)
    except OSError:
        return True
    flag = getattr(stat, "FILE_ATTRIBUTE_REPARSE_POINT", 0)
    return bool(flag and attributes & flag)


def _scan_artifact_value(value: Any, *, key: str | None = None) -> None:
    """Reject secrets, physical paths, and runtime identity metadata."""

    if key is not None:
        marker = _normalized_key(key)
        is_secret_key = marker in _SECRET_KEYS or marker.endswith(
            ("password", "secret", "token", "credential", "privatekey")
        )
        is_path_key = marker in _PATH_KEYS or marker.endswith(("path", "directory"))
        if is_secret_key or is_path_key:
            raise Phase06ArtifactVerificationError(
                "artifact contains a forbidden secret or path field"
            )
    if isinstance(value, Mapping):
        for child_key, child in value.items():
            _scan_artifact_value(child, key=str(child_key))
    elif isinstance(value, list):
        for child in value:
            _scan_artifact_value(child)
    elif isinstance(value, str) and (
        _SECRET_VALUE.search(value) or _ABSOLUTE_PATH.search(value)
    ):
        raise Phase06ArtifactVerificationError(
            "artifact contains a secret or physical path value"
        )


def _file_identity(path: Path) -> tuple[int, int, int, int]:
    status = path.stat(follow_symlinks=False)
    return (status.st_dev, status.st_ino, status.st_size, status.st_mtime_ns)


def _documents(directory: Path) -> dict[str, dict[str, Any]]:
    """Freeze and parse the exact closed set without following indirection."""

    try:
        root = validated_directory(Path(directory), label="Phase06 artifact")
    except (OSError, UnsafePathError) as exc:
        raise Phase06ArtifactVerificationError("unsafe artifact directory") from exc
    try:
        entries = [Path(entry.path) for entry in os.scandir(root)]
    except OSError as exc:
        raise Phase06ArtifactVerificationError("artifact cannot be scanned") from exc
    if (
        len(entries) != len(FILES)
        or {path.name for path in entries} != FILES
        or any(_link_like(path) or not path.is_file() for path in entries)
    ):
        raise Phase06ArtifactVerificationError(
            "artifact exact five-file closed set mismatch"
        )
    identities = {path.name: _file_identity(path) for path in entries}
    frozen: dict[str, bytes] = {}
    total = 0
    for path in entries:
        raw = path.read_bytes()
        if len(raw) > MAX_FILE_BYTES:
            raise Phase06ArtifactVerificationError("artifact file is too large")
        total += len(raw)
        frozen[path.name] = raw
    if total > MAX_ARTIFACT_BYTES:
        raise Phase06ArtifactVerificationError("artifact is too large")

    documents: dict[str, dict[str, Any]] = {}
    for name, raw in frozen.items():
        try:
            value = strict_json_bytes(raw)
        except Exception as exc:
            raise Phase06ArtifactVerificationError(
                "artifact is not strict duplicate-free JSON"
            ) from exc
        if not isinstance(value, dict):
            raise Phase06ArtifactVerificationError(
                "artifact JSON root must be an object"
            )
        _scan_artifact_value(value)
        documents[name] = value

    try:
        final_entries = [Path(entry.path) for entry in os.scandir(root)]
        if (
            len(final_entries) != len(entries)
            or {path.name for path in final_entries} != FILES
            or any(
                _link_like(path)
                or not path.is_file()
                or _file_identity(path) != identities[path.name]
                or path.read_bytes() != frozen[path.name]
                for path in final_entries
            )
        ):
            raise Phase06ArtifactVerificationError(
                "artifact changed during verification"
            )
    except OSError as exc:
        raise Phase06ArtifactVerificationError(
            "artifact changed during verification"
        ) from exc
    return documents


def _exact(value: Any, fields: set[str] | frozenset[str], label: str) -> dict[str, Any]:
    if not isinstance(value, Mapping) or set(value) != set(fields):
        raise Phase06ArtifactVerificationError(f"{label} field set mismatch")
    return deepcopy(dict(value))


@contextmanager
def _controlled_reconstruction() -> Iterator[tuple[dict[str, Any], dict[str, Any]]]:
    """Rebuild controlled P0/P1 and replay the complete state machine afresh."""

    try:
        from scripts.activation_controlled_fixture import (
            build_controlled_activation_fixture,
            run_controlled_activation_workflow,
        )
    except ModuleNotFoundError:
        from activation_controlled_fixture import (  # type: ignore[import-not-found]
            build_controlled_activation_fixture,
            run_controlled_activation_workflow,
        )
    with TemporaryDirectory(prefix="kg-mnp-phase06-artifact-verifier-") as directory:
        fixture = build_controlled_activation_fixture(Path(directory))
        workflow = run_controlled_activation_workflow(
            fixture=fixture,
            state_directory=Path(directory) / "state",
            verifier=fixture["offline_verifier"],
        )
        yield fixture, workflow


def _verify_production(
    summary: Mapping[str, Any], authority: object
) -> tuple[dict[str, Any], dict[str, Any], dict[str, Any]]:
    expected_fields = {
        "activation_candidates",
        "activation_cycles",
        "rollback_cycles",
        "initial_pointer",
        "final_pointer",
        "pointer_unchanged",
        "bootstrap_registry",
        "status",
    }
    value = _exact(summary, expected_fields, "production activation summary")
    registry, pointer = new_activation_registry(authority)
    reconstructed = validate_activation_registry_against_authorities(
        registry, authority, current_pointer=pointer
    )
    candidate_count = authority.production_activation_candidate_count
    if (
        candidate_count != 0
        or value
        != {
            "activation_candidates": 0,
            "activation_cycles": 0,
            "rollback_cycles": 0,
            "initial_pointer": pointer,
            "final_pointer": pointer,
            "pointer_unchanged": True,
            "bootstrap_registry": registry,
            "status": "PRODUCTION_BOOTSTRAP_CURRENT_REFERENCE_VERIFIED",
        }
        or reconstructed["activation_cycles"] != 0
        or reconstructed["rollback_cycles"] != 0
    ):
        raise Phase06ArtifactVerificationError(
            "production bootstrap authority/state mismatch"
        )
    return registry, pointer, reconstructed


def _controlled_summary_expected(
    fixture: Mapping[str, Any], workflow: Mapping[str, Any]
) -> dict[str, Any]:
    authority = fixture["authority"]
    p0 = authority.base_publication
    p1 = authority.activation_candidates[0]
    return {
        "fixture_id": authority.fixture_id,
        "controlled_fixture_hash": authority.controlled_fixture_hash,
        "test_only": True,
        "production_authority": False,
        "p0": p0.descriptor,
        "p1": p1.descriptor,
        "initial_pointer": workflow["initial_pointer"],
        "activation_proposal": workflow["activation_proposal"],
        "activation_review_decision": workflow["activation_review_decision"],
        "activation_receipt": workflow["activation_receipt"],
        "post_activation_pointer": workflow["post_activation_state"]["current_pointer"],
        "resolved_p1": workflow["resolved_p1"],
        "final_registry": workflow["final_registry"],
        "final_pointer": workflow["final_pointer"],
        "status": "CONTROLLED_ACTIVATION_VERIFIED",
    }


def _verify_rollback(
    supplied: Mapping[str, Any], fixture: Mapping[str, Any], workflow: Mapping[str, Any]
) -> tuple[dict[str, str], dict[str, str]]:
    fields = {
        "contract_version",
        "test_only",
        "production_authority",
        "rollback_is_pointer_selection_only",
        "rdf_reverse_patch_used",
        "repository_mutation_by_controller",
        "from_publication_id",
        "to_publication_id",
        "rollback_proposal",
        "rollback_review_decision",
        "rollback_receipt",
        "generation_sequence",
        "repository_hashes",
        "publication_tree_hashes",
        "final_active_publication_id",
        "status",
    }
    value = _exact(supplied, fields, "rollback summary")
    authority = fixture["authority"]
    p0 = authority.base_publication
    p1 = authority.activation_candidates[0]
    repository_hashes = _exact(
        value["repository_hashes"],
        {
            "p0_before",
            "p1_before",
            "p0_after_activation",
            "p1_after_activation",
            "p0_after_rollback",
            "p1_after_rollback",
        },
        "rollback repository hashes",
    )
    publication_hashes = _exact(
        value["publication_tree_hashes"],
        {"p0_before", "p1_before", "p0_after", "p1_after"},
        "rollback publication hashes",
    )
    p0_tree = publication_tree_sha256(p0.package_directory)
    p1_tree = publication_tree_sha256(p1.package_directory)
    if not (
        value["contract_version"] == "1.0"
        and value["test_only"] is True
        and value["production_authority"] is False
        and value["rollback_is_pointer_selection_only"] is True
        and value["rdf_reverse_patch_used"] is False
        and value["repository_mutation_by_controller"] is False
        and value["from_publication_id"] == p1.publication_id
        and value["to_publication_id"] == p0.publication_id
        and value["rollback_proposal"] == workflow["rollback_proposal"]
        and value["rollback_review_decision"] == workflow["rollback_review_decision"]
        and value["rollback_receipt"] == workflow["rollback_receipt"]
        and value["generation_sequence"] == [0, 1, 2]
        and repository_hashes["p0_before"]
        == repository_hashes["p0_after_activation"]
        == repository_hashes["p0_after_rollback"]
        == p0.repository_semantic_hash
        and repository_hashes["p1_before"]
        == repository_hashes["p1_after_activation"]
        == repository_hashes["p1_after_rollback"]
        == p1.repository_semantic_hash
        and publication_hashes["p0_before"] == publication_hashes["p0_after"] == p0_tree
        and publication_hashes["p1_before"] == publication_hashes["p1_after"] == p1_tree
        and value["final_active_publication_id"] == p0.publication_id
        and value["status"] == "CONTROLLED_ROLLBACK_VERIFIED"
    ):
        raise Phase06ArtifactVerificationError(
            "rollback selection/immutability evidence mismatch"
        )
    return repository_hashes, publication_hashes


def _supplemental_probe(probe: Mapping[str, Any]) -> dict[str, Any]:
    fields = {
        "probe_id",
        "attack",
        "expected_code",
        "observed_code",
        "blocked",
        "details",
    }
    value = _exact(probe, fields, "supplemental probe")
    content = {key: value[key] for key in fields if key != "probe_id"}
    if (
        value["attack"] not in {"double_encoded_path", "symlink_escape"}
        or value["expected_code"] != "PATH_REJECTED"
        or value["observed_code"] != "PATH_REJECTED"
        or value["blocked"] is not True
        or not isinstance(value["details"], str)
        or not value["details"]
        or not isinstance(value["probe_id"], str)
        or not SUPPLEMENTAL_ID.fullmatch(value["probe_id"])
        or value["probe_id"]
        != "urn:kg-mnp:test-fixture:phase06:supplemental-probe:"
        + semantic_hash(content)
    ):
        raise Phase06ArtifactVerificationError(
            "supplemental path-security probe mismatch"
        )
    return value


def _verify_security(
    supplied: Mapping[str, Any], attestation: Mapping[str, Any]
) -> tuple[list[dict[str, Any]], dict[str, int]]:
    fields = {
        "contract_version",
        "test_only",
        "production_authority",
        "probe_records",
        "supplemental_probe_records",
        "counters",
        "concurrency_result",
        "activation_controller_graphdb_access",
        "cleanup",
        "status",
    }
    value = _exact(supplied, fields, "security summary")
    if not isinstance(value["probe_records"], list):
        raise Phase06ArtifactVerificationError("probe records must be an array")
    records = [deepcopy(dict(item)) for item in value["probe_records"]]
    try:
        counters = aggregate_probe_records(records)
    except ActivationError as exc:
        raise Phase06ArtifactVerificationError(
            "probe record verification failed"
        ) from exc
    counter_fields = {
        field for pair in ATTACK_COUNTER_FIELDS.values() for field in pair
    }
    supplemental = value["supplemental_probe_records"]
    if not isinstance(supplemental, list):
        raise Phase06ArtifactVerificationError(
            "supplemental probe records must be an array"
        )
    supplemental_values = [_supplemental_probe(item) for item in supplemental]
    concurrency = _exact(
        value["concurrency_result"],
        {"processes", "success", "blocked", "outcomes", "final_generation", "status"},
        "concurrency result",
    )
    cleanup = _exact(
        value["cleanup"],
        {"controlled_repository_count", "cleanup_failures", "status"},
        "cleanup result",
    )
    if not (
        value["contract_version"] == "1.0"
        and value["test_only"] is True
        and value["production_authority"] is False
        and value["counters"] == counters
        and all(attestation[field] == counters[field] for field in counter_fields)
        and {item["attack"] for item in supplemental_values}
        == {"double_encoded_path", "symlink_escape"}
        and len(supplemental_values) == 2
        and concurrency
        == {
            "processes": 2,
            "success": 1,
            "blocked": 1,
            "outcomes": ["ACTIVATION_APPLIED", "ACTIVATION_CONCURRENCY_CONFLICT"],
            "final_generation": 1,
            "status": "CONTROLLED_PROCESS_RACE_VERIFIED",
        }
        and value["activation_controller_graphdb_access"]
        == ["repository_info", "export_explicit_nquads"]
        and cleanup
        == {
            "controlled_repository_count": 2,
            "cleanup_failures": 0,
            "status": "PASS",
        }
        and value["status"] == "PASS"
    ):
        raise Phase06ArtifactVerificationError(
            "security probes/counters/concurrency/cleanup mismatch"
        )
    return records, counters


def verify_application_phase06_artifact(
    directory: Path,
    *,
    publication_package_directory: Path,
    publication_attestation_path: Path,
    publication_scenario: str,
    phase01_artifact_directory: Path,
    phase02_artifact_directory: Path,
    phase03_artifact_directory: Path,
    phase04_artifact_directory: Path,
    phase05_artifact_directory: Path,
    expected_commit_sha: str,
    expected_registry_hash: str,
    expected_head_event_hash: str,
) -> dict[str, Any]:
    """Reconstruct every authority and state transition from physical inputs."""

    if not isinstance(expected_commit_sha, str) or not COMMIT.fullmatch(
        expected_commit_sha
    ):
        raise Phase06ArtifactVerificationError("invalid expected commit SHA")
    if (
        not isinstance(expected_registry_hash, str)
        or not HASH.fullmatch(expected_registry_hash)
        or not isinstance(expected_head_event_hash, str)
        or not HASH.fullmatch(expected_head_event_hash)
    ):
        raise Phase06ArtifactVerificationError(
            "trusted registry and head anchors are required"
        )
    try:
        authority = load_production_phase06_authority(
            publication_package_directory=publication_package_directory,
            publication_attestation_path=publication_attestation_path,
            phase01_artifact_directory=phase01_artifact_directory,
            phase02_artifact_directory=phase02_artifact_directory,
            phase03_artifact_directory=phase03_artifact_directory,
            phase04_artifact_directory=phase04_artifact_directory,
            phase05_artifact_directory=phase05_artifact_directory,
            expected_commit_sha=expected_commit_sha,
            publication_scenario=publication_scenario,
        )
    except Exception as exc:
        raise Phase06ArtifactVerificationError(
            "AUTHORITY_MISMATCH: Stage08--Phase05 reconstruction failed"
        ) from exc

    documents = _documents(directory)
    attestation = documents["application-phase06-attestation.json"]
    try:
        validate_activation_contract("application-phase06-attestation", attestation)
    except Exception as exc:
        raise Phase06ArtifactVerificationError(
            "application Phase06 attestation schema failed"
        ) from exc
    if (
        attestation["commit_sha"] != expected_commit_sha
        or attestation["status"] != "APPLICATION_PUBLICATION_ACTIVATION_VERIFIED"
    ):
        raise Phase06ArtifactVerificationError("commit/final status mismatch")

    binding = documents["authority-binding.json"]
    expected_binding = {
        "contract_version": "1.0",
        **authority.binding,
        "status": "PASS",
    }
    if binding != expected_binding:
        raise Phase06ArtifactVerificationError(
            "AUTHORITY_MISMATCH: authority-binding.json differs from physical inputs"
        )

    activation = _exact(
        documents["activation-summary.json"],
        {
            "contract_version",
            "production_activation_summary",
            "controlled_activation_summary",
            "controlled_registry_hash",
            "controlled_head_event_hash",
            "status",
        },
        "activation summary",
    )
    if activation["contract_version"] != "1.0" or activation["status"] != "PASS":
        raise Phase06ArtifactVerificationError("activation summary status mismatch")
    _production_registry, production_pointer, _production_state = _verify_production(
        activation["production_activation_summary"], authority
    )

    with _controlled_reconstruction() as (fixture, workflow):
        controlled_expected = _controlled_summary_expected(fixture, workflow)
        controlled_supplied = activation["controlled_activation_summary"]
        if controlled_supplied != controlled_expected:
            raise Phase06ArtifactVerificationError(
                "AUTHORITY_MISMATCH: controlled fixture/state replay differs"
            )
        controlled_authority = fixture["authority"]
        try:
            state = validate_activation_registry_against_authorities(
                controlled_supplied["final_registry"],
                controlled_authority,
                current_pointer=controlled_supplied["final_pointer"],
                expected_registry_hash=expected_registry_hash,
                expected_head_event_hash=expected_head_event_hash,
            )
        except ActivationError as exc:
            raise Phase06ArtifactVerificationError(
                f"AUTHORITY_MISMATCH: controlled registry replay failed: {exc.code.value}"
            ) from exc
        if not (
            activation["controlled_registry_hash"]
            == state["registry_hash"]
            == expected_registry_hash
            and activation["controlled_head_event_hash"]
            == state["head_event_hash"]
            == expected_head_event_hash
        ):
            raise Phase06ArtifactVerificationError(
                "trusted controlled registry/head anchor mismatch"
            )
        repository_hashes, publication_hashes = _verify_rollback(
            documents["rollback-summary.json"], fixture, workflow
        )
        records, counters = _verify_security(
            documents["security-summary.json"], attestation
        )
        p0 = controlled_authority.base_publication
        p1 = controlled_authority.activation_candidates[0]
        physical_identities = {
            "stage08_identity": authority.stage08_artifact_tree_sha256,
            "phase01_identity": authority.phase01_artifact_tree_sha256,
            "phase02_identity": authority.phase02_artifact_tree_sha256,
            "phase03_identity": authority.phase03_artifact_tree_sha256,
            "phase04_identity": authority.phase04_artifact_tree_sha256,
            "phase05_identity": authority.phase05_artifact_tree_sha256,
        }
        production_evidence = {
            "production_base_publication_id": authority.base_publication.publication_id,
            "production_base_publication_hash": (
                authority.base_publication.publication_semantic_hash
            ),
            "production_base_repository_id": authority.base_publication.repository_id,
            "production_base_repository_hash": (
                authority.base_publication.repository_semantic_hash
            ),
            "production_activation_candidates": 0,
            "production_activation_cycles": 0,
            "production_rollback_cycles": 0,
            "production_pointer_initial_hash": production_pointer["pointer_hash"],
            "production_pointer_final_hash": production_pointer["pointer_hash"],
            "production_pointer_unchanged": True,
        }
        controlled_evidence = {
            "controlled_fixture_hash": controlled_authority.controlled_fixture_hash,
            "controlled_p0_publication_hash": p0.publication_semantic_hash,
            "controlled_p1_publication_hash": p1.publication_semantic_hash,
            "controlled_p0_repository_hash": p0.repository_semantic_hash,
            "controlled_p1_repository_hash": p1.repository_semantic_hash,
            "controlled_activation_cycles": state["activation_cycles"],
            "controlled_rollback_cycles": state["rollback_cycles"],
            "controlled_initial_generation": workflow["initial_pointer"]["generation"],
            "controlled_post_activation_generation": workflow["post_activation_state"][
                "current_pointer"
            ]["generation"],
            "controlled_final_generation": workflow["final_pointer"]["generation"],
            "p0_repository_before_hash": repository_hashes["p0_before"],
            "p0_repository_after_activation_hash": repository_hashes[
                "p0_after_activation"
            ],
            "p0_repository_after_rollback_hash": repository_hashes["p0_after_rollback"],
            "p1_repository_before_hash": repository_hashes["p1_before"],
            "p1_repository_after_activation_hash": repository_hashes[
                "p1_after_activation"
            ],
            "p1_repository_after_rollback_hash": repository_hashes["p1_after_rollback"],
            "p0_publication_tree_before_hash": publication_hashes["p0_before"],
            "p0_publication_tree_after_hash": publication_hashes["p0_after"],
            "p1_publication_tree_before_hash": publication_hashes["p1_before"],
            "p1_publication_tree_after_hash": publication_hashes["p1_after"],
            "determinism_runs": 2,
            "determinism_passed": 2,
        }
        try:
            expected_attestation = build_application_phase06_attestation(
                commit_sha=expected_commit_sha,
                physical_identities=physical_identities,
                production_evidence=production_evidence,
                controlled_evidence=controlled_evidence,
                probe_records=records,
            )
        except ActivationError as exc:
            raise Phase06ArtifactVerificationError(
                "attestation evidence reconstruction failed"
            ) from exc
        if attestation != expected_attestation:
            raise Phase06ArtifactVerificationError(
                "attestation differs from independently reconstructed evidence"
            )

    return {
        "artifact_files": sorted(FILES),
        "commit_sha": expected_commit_sha,
        "production_activation_candidates": 0,
        "production_pointer_unchanged": True,
        "controlled_fixture_hash": attestation["controlled_fixture_hash"],
        "controlled_registry_hash": expected_registry_hash,
        "controlled_head_event_hash": expected_head_event_hash,
        "controlled_activation_cycles": 1,
        "controlled_rollback_cycles": 1,
        "security_probe_count": len(records),
        "security_counters": counters,
        "status": attestation["status"],
    }
