from __future__ import annotations

from datetime import datetime, timezone
from pathlib import Path
from typing import Any, Mapping, Sequence

from ._io import json_bytes
from .contracts import validate_graphdb_contract


def utc_now() -> str:
    return datetime.now(timezone.utc).replace(microsecond=0).isoformat().replace("+00:00", "Z")


def build_import_attestation(
    *,
    source_publication_id: str,
    source_compilation_id: str,
    repository_config_hash: str,
    import_dataset_hash: str,
    export_dataset_hash: str,
    expected_graph_count: int,
    actual_graph_count: int,
    expected_quad_count: int,
    actual_quad_count: int,
    verification: Mapping[str, Any],
    graphdb_version: Mapping[str, Any] | None = None,
    image_digest: str | None = None,
    base_url: str = "http://127.0.0.1:7200",
    repository_id: str,
    create_status: int | None = None,
    import_status: int | None = None,
    expected_named_graphs: Sequence[str] = (),
    actual_named_graphs: Sequence[str] = (),
    license_state: str = "ACCEPTED",
    license_edition: str = "UNKNOWN",
    license_source_type: str = "UNKNOWN",
    started_at: str | None = None,
    completed_at: str | None = None,
) -> dict[str, Any]:
    explicit_export_hash = str(verification.get("export_semantic_hash", export_dataset_hash))
    complete_export_hash = str(verification.get("complete_export_semantic_hash", explicit_export_hash))
    attestation = {
        "contract_version": "1.0",
        "source_publication_id": source_publication_id,
        "source_compilation_id": source_compilation_id,
        "repository_config_hash": repository_config_hash,
        "import_dataset_hash": import_dataset_hash,
        "import_semantic_hash": import_dataset_hash,
        "export_dataset_hash": explicit_export_hash,
        "explicit_export_semantic_hash": explicit_export_hash,
        "complete_export_semantic_hash": complete_export_hash,
        "expected_graph_count": expected_graph_count,
        "actual_graph_count": actual_graph_count,
        "expected_named_graphs": sorted(set(expected_named_graphs)),
        "actual_named_graphs": sorted(set(actual_named_graphs)),
        "expected_quad_count": expected_quad_count,
        "actual_quad_count": actual_quad_count,
        "physical_default_graph_count": int(verification.get("default_graph_statement_count", -1)),
        "default_graph_check_method": str(
            verification.get("default_graph_check", {}).get("method", "")
        ),
        "default_graph_http_status": int(
            verification.get("default_graph_check", {}).get("http_status", -1)
        ),
        "default_graph_semantic_hash": str(
            verification.get("default_graph_check", {}).get("semantic_hash", "")
        ),
        "forbidden_assertion_count": int(verification.get("forbidden_assertion_count", -1)),
        "violating_forbidden_assertion_count": int(verification.get("violating_forbidden_assertion_count", -1)),
        "inferred_statement_count": int(verification.get("inferred_statement_count", -1)),
        "repository_id": repository_id,
        "repository_ruleset": "empty",
        "base_url": base_url.rstrip("/"),
        "graphdb_version": graphdb_version or {},
        "oci_image_digest": image_digest,
        "license_state": license_state,
        "license_edition": license_edition,
        "license_source_type": license_source_type,
        "started_at": started_at or utc_now(),
        "completed_at": completed_at or utc_now(),
        "create_status": create_status,
        "import_status": import_status,
        "verification": dict(verification),
        "status": "IMPORT_VERIFIED",
    }
    if attestation["license_state"] != "ACCEPTED":
        raise ValueError("verified attestation requires an accepted GraphDB license")
    if (
        expected_graph_count != actual_graph_count
        or sorted(set(expected_named_graphs)) != sorted(set(actual_named_graphs))
        or expected_quad_count != actual_quad_count
        or attestation["physical_default_graph_count"] != 0
        or attestation["violating_forbidden_assertion_count"] != 0
        or attestation["inferred_statement_count"] != 0
    ):
        raise ValueError("verified attestation invariants do not match")
    if not (import_dataset_hash == explicit_export_hash == complete_export_hash):
        raise ValueError("verified attestation import/export hashes do not match")
    if verification.get("status") != "IMPORT_VERIFIED":
        raise ValueError("verified attestation requires successful verification evidence")
    validate_graphdb_contract("import-attestation", attestation)
    return attestation


def write_import_attestation(path: Path, attestation: Mapping[str, Any]) -> None:
    validate_graphdb_contract("import-attestation", attestation)
    destination = Path(path)
    destination.parent.mkdir(parents=True, exist_ok=True)
    destination.write_bytes(json_bytes(attestation))
