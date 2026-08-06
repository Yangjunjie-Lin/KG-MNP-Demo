from __future__ import annotations

from datetime import datetime, timezone
from pathlib import Path
from typing import Any, Mapping

from ._io import json_bytes
from .contracts import validate_graphdb_contract


def utc_now() -> str:
    return datetime.now(timezone.utc).replace(microsecond=0).isoformat().replace("+00:00", "Z")


def build_import_attestation(*, source_publication_id: str, source_compilation_id: str, repository_config_hash: str, import_dataset_hash: str, export_dataset_hash: str, expected_graph_count: int, actual_graph_count: int, expected_quad_count: int, actual_quad_count: int, verification: Mapping[str, Any], graphdb_version: Mapping[str, Any] | None = None, image_digest: str | None = None, base_url: str = "http://127.0.0.1:7200", repository_id: str, create_status: int | None = None, import_status: int | None = None, status: str = "IMPORT_VERIFIED", started_at: str | None = None, completed_at: str | None = None) -> dict[str, Any]:
    attestation = {
        "contract_version": "1.0",
        "source_publication_id": source_publication_id,
        "source_compilation_id": source_compilation_id,
        "repository_config_hash": repository_config_hash,
        "import_dataset_hash": import_dataset_hash,
        "export_dataset_hash": export_dataset_hash,
        "expected_graph_count": expected_graph_count,
        "actual_graph_count": actual_graph_count,
        "expected_quad_count": expected_quad_count,
        "actual_quad_count": actual_quad_count,
        "repository_id": repository_id,
        "base_url": base_url.rstrip("/"),
        "graphdb_version": graphdb_version or {},
        "oci_image_digest": image_digest,
        "started_at": started_at or utc_now(),
        "completed_at": completed_at or utc_now(),
        "create_status": create_status,
        "import_status": import_status,
        "verification": dict(verification),
        "status": status,
    }
    if status == "IMPORT_VERIFIED":
        if expected_graph_count != actual_graph_count or expected_quad_count != actual_quad_count:
            raise ValueError("verified attestation counts do not match")
        if import_dataset_hash != export_dataset_hash:
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
