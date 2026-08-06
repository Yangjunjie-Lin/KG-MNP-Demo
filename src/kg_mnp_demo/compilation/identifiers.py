"""Stable Stage 06 identifiers.  No clocks, UUIDs, paths, or host metadata."""

from __future__ import annotations

from typing import Any, Mapping

from ..modeling.canonical_json import semantic_hash, stable_urn


def _urn(kind: str, value: Any) -> str:
    return stable_urn(kind, value)


def compilation_semantic_content(value: Mapping[str, Any]) -> dict[str, Any]:
    return {
        key: value[key]
        for key in sorted(value)
        if key not in {"compilation_id", "compilation_semantic_hash"}
    }


def compilation_semantic_hash(value: Mapping[str, Any]) -> str:
    return semantic_hash(compilation_semantic_content(value))


def compilation_id(value: Mapping[str, Any] | str) -> str:
    digest = value if isinstance(value, str) else compilation_semantic_hash(value)
    return f"urn:kg-mnp:compilation:{digest}"


def artifact_id(value: Mapping[str, Any] | str) -> str:
    digest = value if isinstance(value, str) else semantic_hash(value)
    return f"urn:kg-mnp:artifact:{digest}"


def graph_iri(kind: str, package_hash: str) -> str:
    if kind not in {"abox", "modeling-provenance", "review-audit"}:
        raise ValueError(f"unknown compilation graph: {kind}")
    return f"urn:kg-mnp:graph:{kind}:{package_hash}"


def compiled_assertion_id(value: Mapping[str, Any]) -> str:
    return _urn("compiled-assertion", value)


def provenance_record_id(value: Mapping[str, Any]) -> str:
    return _urn("provenance-record", value)


def source_record_id(value: str | Mapping[str, Any]) -> str:
    return _urn("source-record", value)


def source_field_id(value: str | Mapping[str, Any]) -> str:
    return _urn("source-field", value)


def mapping_rule_id(value: str | Mapping[str, Any]) -> str:
    return _urn("mapping-rule", value)


def modeling_evidence_id(value: str | Mapping[str, Any]) -> str:
    return _urn("modeling-evidence", value)


def review_record_id(value: Mapping[str, Any]) -> str:
    return _urn("review-record", value)


def shacl_result_id(value: Mapping[str, Any]) -> str:
    return _urn("shacl-result", value)
