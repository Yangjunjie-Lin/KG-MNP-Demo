from __future__ import annotations

import hashlib
import re
from typing import Any, Mapping

from ..modeling.canonical_json import semantic_hash

SHA256_RE = re.compile(r"^[0-9a-f]{64}$")
REPOSITORY_RE = re.compile(r"^kg-mnp-[0-9a-f]{20}$")


class GraphDBIdentifierError(ValueError):
    pass


def sha256_bytes(data: bytes) -> str:
    return hashlib.sha256(data).hexdigest()


def require_sha256(value: str, field: str = "hash") -> str:
    if not isinstance(value, str) or not SHA256_RE.fullmatch(value):
        raise GraphDBIdentifierError(f"{field} must be lowercase SHA-256")
    return value


def publication_semantic_content(value: Mapping[str, Any]) -> dict[str, Any]:
    fields = (
        "source_compilation_id",
        "source_compilation_semantic_hash",
        "ontology_release_source_hash",
        "graphdb_policy_hash",
        "repository_config_semantic_hash",
        "assembled_dataset_semantic_hash",
        "query_suite_hash",
    )
    missing = [field for field in fields if field not in value]
    if missing:
        raise GraphDBIdentifierError(
            "publication semantic content is incomplete: " + ", ".join(missing)
        )
    return {key: value[key] for key in fields}


def publication_semantic_hash(value: Mapping[str, Any]) -> str:
    return semantic_hash(publication_semantic_content(value))


def publication_id(value: Mapping[str, Any] | str) -> str:
    digest = value if isinstance(value, str) else publication_semantic_hash(value)
    require_sha256(digest, "publication_semantic_hash")
    return f"urn:kg-mnp:graphdb-publication:{digest}"


def repository_id_for_publication(publication: Mapping[str, Any] | str) -> str:
    digest = publication if isinstance(publication, str) else publication_semantic_hash(publication)
    require_sha256(digest, "publication_semantic_hash")
    return f"kg-mnp-{digest[:20]}"


def validate_repository_id(value: str) -> None:
    if not REPOSITORY_RE.fullmatch(value):
        raise GraphDBIdentifierError("repository id is not a generated KG-MNP id")


def tbox_graph_iri(module_code: str, source_hash: str) -> str:
    require_sha256(source_hash, "module source hash")
    if not re.fullmatch(r"[A-Za-z0-9_-]+", module_code):
        raise GraphDBIdentifierError("unsafe ontology module code")
    return f"urn:kg-mnp:graph:tbox:{module_code}:{source_hash}"


def root_tbox_graph_iri(source_hash: str) -> str:
    return tbox_graph_iri("root", source_hash)
