from __future__ import annotations

from kg_mnp_demo.diagnostics import AuthorityBindings
from kg_mnp_demo.diagnostics.policy import diagnostic_policy_hash


def bindings() -> AuthorityBindings:
    publication_hash = "a" * 64
    return AuthorityBindings(
        publication_id=f"urn:kg-mnp:e2e-publication:{publication_hash}",
        publication_semantic_hash=publication_hash,
        phase01_attestation_hash="b" * 64,
        phase02_attestation_hash="c" * 64,
        query_registry_hash="d" * 64,
        repository_semantic_hash="e" * 64,
        diagnostic_policy_hash=diagnostic_policy_hash(),
    )


def snapshot(
    *,
    facts=None,
    requirements=None,
    candidates=None,
    constraint_results=None,
    conflict_rules=None,
):
    value = bindings()
    return {
        "authority_bindings": value.to_dict(),
        "requirements": requirements if requirements is not None else [],
        "facts": facts if facts is not None else [],
        "candidates": candidates if candidates is not None else [],
        "constraint_results": constraint_results if constraint_results is not None else [],
        "conflict_rules": conflict_rules if conflict_rules is not None else [],
    }
