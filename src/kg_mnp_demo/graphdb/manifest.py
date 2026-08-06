from __future__ import annotations

import hashlib
from pathlib import Path
from typing import Any, Mapping

from ..compilation.manifest import artifact_id
from .identifiers import publication_id, publication_semantic_hash, repository_id_for_publication
from .policy import graphdb_policy_semantic_hash


def _artifact(path: str, role: str, data: bytes, *, semantic_sha256: str | None = None) -> dict[str, Any]:
    record = {
        "relative_path": path,
        "role": role,
        "media_type": {".json": "application/json", ".nq": "application/n-quads", ".nt": "application/n-triples", ".ttl": "text/turtle", ".rq": "application/sparql-query", ".yaml": "application/yaml"}.get(Path(path).suffix, "application/octet-stream"),
        "byte_sha256": hashlib.sha256(data).hexdigest(),
        "semantic_sha256": semantic_sha256 or hashlib.sha256(data).hexdigest(),
        "size_bytes": len(data),
        "artifact_id": artifact_id({"relative_path": path, "role": role, "byte_sha256": hashlib.sha256(data).hexdigest(), "semantic_sha256": semantic_sha256 or hashlib.sha256(data).hexdigest()}),
    }
    return record


def complete_import_manifest(content: Mapping[str, Any]) -> dict[str, Any]:
    value = dict(content)
    digest = publication_semantic_hash(value)
    value["publication_semantic_hash"] = digest
    value["publication_id"] = publication_id(digest)
    return value


def build_import_manifest(*, policy: Mapping[str, Any], compilation_manifest: Mapping[str, Any], source_package: Mapping[str, Any], ontology_baseline: Mapping[str, Any], repository_config_bytes: bytes, repository_config_semantic_hash: str, assembled_data: bytes, assembled_semantic_hash: str, query_suite: Mapping[str, Any], artifacts: Mapping[str, tuple[str, bytes, str | None]], tbox_module_count: int, tbox_triple_count: int, stage06_quad_count: int, assembled_quad_count: int, named_graphs: list[str]) -> dict[str, Any]:
    content: dict[str, Any] = {
        "contract_version": "1.0",
        "graphdb_policy_id": policy["runtime_id"],
        "graphdb_policy_version": policy["runtime_version"],
        "graphdb_policy_hash": graphdb_policy_semantic_hash(policy),
        "source_compilation_id": compilation_manifest["compilation_id"],
        "source_compilation_semantic_hash": compilation_manifest["compilation_semantic_hash"],
        "source_package_id": source_package["package_id"],
        "ontology_baseline_id": ontology_baseline["baseline_id"],
        "ontology_version": ontology_baseline["ontology_version"],
        "ontology_release_source_hash": ontology_baseline["release_source_hash"],
        "repository_id": repository_id_for_publication("0" * 64),
        "repository_config_byte_hash": hashlib.sha256(repository_config_bytes).hexdigest(),
        "repository_config_semantic_hash": repository_config_semantic_hash,
        "repository_ruleset": "empty",
        "assembled_dataset_byte_hash": hashlib.sha256(assembled_data).hexdigest(),
        "assembled_dataset_semantic_hash": assembled_semantic_hash,
        "tbox_module_count": tbox_module_count,
        "tbox_triple_count": tbox_triple_count,
        "stage06_quad_count": stage06_quad_count,
        "assembled_quad_count": assembled_quad_count,
        "named_graphs": sorted(set(named_graphs)),
        "artifact_manifest": [_artifact(path, role, data, semantic_sha256=semantic) for path, (role, data, semantic) in sorted(artifacts.items())],
        "query_suite_id": query_suite["query_suite_id"],
        "query_suite_hash": query_suite["query_suite_hash"],
        "release_status": "READY_FOR_GRAPHDB_IMPORT",
    }
    # Repository id is derived from publication hash, so it is filled after the first digest.
    provisional = complete_import_manifest(content)
    provisional["repository_id"] = repository_id_for_publication(provisional["publication_semantic_hash"])
    provisional["publication_semantic_hash"] = publication_semantic_hash(provisional)
    provisional["publication_id"] = publication_id(provisional["publication_semantic_hash"])
    provisional["repository_id"] = repository_id_for_publication(provisional["publication_semantic_hash"])
    return provisional
