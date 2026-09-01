"""Deterministic semantic identifiers."""

from __future__ import annotations

from typing import Any

from kg_mnp.contracts.canonical import semantic_hash, stable_urn


def semantic_id(kind: str, value: Any) -> str:
    return stable_urn(kind, value)


def statement_id(*, graph_role: str, subject: str, predicate: str, object_term: str) -> str:
    return stable_urn(
        "semantic-statement",
        {
            "graph_role": graph_role,
            "subject": subject,
            "predicate": predicate,
            "object": object_term,
        },
    )


def graph_iri(package_id: str, role: str, graph_digest: str) -> str:
    digest = semantic_hash({"package_id": package_id, "role": role, "graph_digest": graph_digest})
    return f"urn:kg-mnp:ontology-package-graph:{digest}"


def skolem_iri(role: str, structural_value: Any) -> str:
    return stable_urn(f"skolem-{role}", structural_value)


def package_storage_key(package_id: str) -> str:
    """Return the portable 64-hex filesystem key for a package URN."""

    value = package_id.rsplit(":", 1)[-1]
    if len(value) != 64 or any(character not in "0123456789abcdef" for character in value):
        raise ValueError("invalid ontology package ID")
    return value
