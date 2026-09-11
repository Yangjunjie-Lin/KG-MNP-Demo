"""Prompt 2 ArtifactReference/ArtifactManifest integration for ingestion."""

from __future__ import annotations

from typing import Any

from zhigou_toolchain.contracts.canonical import bytes_sha256, stable_urn
from zhigou_toolchain.contracts.catalog import ContractCatalog
from zhigou_toolchain.contracts.registry import validate_contract


def artifact_reference(
    *,
    artifact_type: str,
    contract_name: str,
    contract_version: str,
    schema_id: str,
    path: str,
    content: bytes,
    dependencies: tuple[str, ...] = (),
    provenance_refs: tuple[str, ...] = (),
) -> dict[str, Any]:
    identity = {
        "artifact_type": artifact_type,
        "contract_name": contract_name,
        "contract_version": contract_version,
        "path": path,
        "sha256": bytes_sha256(content),
    }
    reference = {
        "manifest_kind": "KG_MNP_ARTIFACT_REFERENCE",
        "schema_version": "1.0.0",
        "artifact_id": stable_urn("artifact", identity),
        "artifact_type": artifact_type,
        "contract_name": contract_name,
        "contract_version": contract_version,
        "schema_id": schema_id,
        "path": path,
        "media_type": "application/json",
        "size_bytes": len(content),
        "sha256": bytes_sha256(content),
        "semantic_hash": bytes_sha256(content),
        "dependencies": sorted(set(dependencies)),
        "provenance_refs": sorted(set(provenance_refs)),
    }
    validate_contract("artifact-reference", reference)
    return reference


def artifact_manifest(
    artifacts: tuple[dict[str, Any], ...],
    *,
    root_artifacts: tuple[str, ...] | None = None,
    dependencies: tuple[str, ...] = (),
) -> dict[str, Any]:
    ordered = sorted(artifacts, key=lambda item: item["artifact_id"])
    roots = sorted(set(root_artifacts or tuple(item["artifact_id"] for item in ordered)))
    core = {
        "artifacts": ordered,
        "root_artifacts": roots,
        "dependencies": sorted(set(dependencies)),
        "contract_catalog_digest": ContractCatalog.load().digest,
        "extensions": {},
    }
    manifest = {
        "manifest_kind": "KG_MNP_ARTIFACT_MANIFEST",
        "schema_version": "1.0.0",
        "artifact_set_id": stable_urn("artifact-set", core),
        **core,
    }
    validate_contract("artifact-manifest", manifest)
    return manifest


EMPTY_ARTIFACT_MANIFEST = None
