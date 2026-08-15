"""Bind revised-input modeling output back to an approved Phase04 request."""

from __future__ import annotations

from collections.abc import Iterable, Mapping
from copy import deepcopy
from typing import Any

from kg_mnp_demo.modeling.canonical_json import semantic_hash

from .errors import AmendmentError, AmendmentErrorCode


def proposal_candidates(proposal: Mapping[str, Any]) -> dict[str, dict[str, Any]]:
    candidates: dict[str, dict[str, Any]] = {}
    for field in (
        "candidate_entities",
        "candidate_assertions",
        "schema_delta_candidates",
    ):
        for candidate in proposal.get(field, []):
            if isinstance(candidate, Mapping) and isinstance(
                candidate.get("candidate_id"), str
            ):
                candidates[str(candidate["candidate_id"])] = dict(candidate)
    return candidates


def _term_matches(
    candidate: Mapping[str, Any],
    term: Mapping[str, Any] | None,
    candidates: Mapping[str, Mapping[str, Any]],
) -> bool:
    if term is None:
        return True
    kind = term.get("term_type")
    if kind == "IRI":
        expected = term.get("iri")
        represented = candidate.get("proposed_iri")
        if represented is None and candidate.get("candidate_kind") == "CLASS_ASSERTION":
            represented = candidate.get("class_iri")
        if represented is None:
            represented = candidate.get("object")
            if isinstance(represented, str) and represented in candidates:
                represented = candidates[represented].get("proposed_iri")
        return represented == expected
    if kind == "LITERAL":
        obj = candidate.get("object")
        if not isinstance(obj, Mapping):
            return False
        if obj.get("value") != term.get("lexical_form"):
            return False
        return obj.get("datatype_iri") == term.get("datatype_iri") and obj.get(
            "language"
        ) == term.get("language")
    return False


def _lineage_matches(
    candidate: Mapping[str, Any],
    *,
    pointers: Iterable[str],
    evidence_refs: Iterable[str],
    source_refs: Iterable[str],
) -> bool:
    pointer_set = set(pointers)
    # MappingRules address the cleaned data payload (for example
    # /subscription/status), while a complete-document diff may expose the
    # enclosing /data prefix. Both are the same explicitly declared input
    # lineage; no RDF-to-JSON inference is performed here.
    pointer_set |= {
        pointer.removeprefix("/data")
        for pointer in pointer_set
        if pointer.startswith("/data/")
    }
    source_set = set(source_refs)
    evidence_set = set(evidence_refs)
    candidate_paths = set(candidate.get("source_paths", []))
    candidate_sources = set(candidate.get("source_paths", [])) | set(
        candidate.get("business_fact_evidence_refs", [])
    )
    candidate_evidence = set(candidate.get("business_fact_evidence_refs", []))
    path_ok = (
        not pointer_set
        or bool(pointer_set & candidate_paths)
        or bool(source_set)
        or bool(evidence_set)
    )
    source_ok = not source_set or bool(source_set & candidate_sources)
    evidence_ok = not evidence_set or bool(evidence_set & candidate_evidence)
    return path_ok and source_ok and evidence_ok


def bind_amendment_to_proposal(
    *,
    amendment_request: Mapping[str, Any],
    proposal: Mapping[str, Any],
    revised_cleaned_data_hash: str,
    declared_changed_json_pointers: Iterable[str],
    target_json_pointers: Iterable[str] = (),
) -> dict[str, Any]:
    """Return the unique candidate represented by the normal proposal generator."""

    if (
        proposal.get("input_snapshot", {}).get("input_semantic_hash")
        != revised_cleaned_data_hash
    ):
        raise AmendmentError(
            AmendmentErrorCode.REENTRY_SEMANTIC_MISMATCH,
            "proposal input snapshot does not equal revised CleanedPartialData",
        )
    amendment_type = amendment_request.get("amendment_type")
    if amendment_type == "PROPOSE_CONSTRAINT_REVIEW":
        raise AmendmentError(
            AmendmentErrorCode.TBOX_AMENDMENT_NOT_EXECUTABLE_IN_PHASE05
        )
    if amendment_type == "NO_CHANGE_RECOMMENDED":
        return {
            "represented": True,
            "candidate": None,
            "candidate_ids": [],
            "candidate_semantic_hash": semantic_hash([]),
        }
    payload = amendment_request.get("structured_proposed_payload")
    if not isinstance(payload, Mapping):
        raise AmendmentError(AmendmentErrorCode.REENTRY_TARGET_UNRESOLVED)
    all_candidates = proposal_candidates(proposal)
    if proposal.get("schema_delta_candidates"):
        raise AmendmentError(
            AmendmentErrorCode.REENTRY_SEMANTIC_MISMATCH,
            "ABox re-entry cannot emit schema/TBox candidates",
        )
    allowed_ids = set(payload.get("candidate_refs") or [])
    candidates = {
        candidate_id: candidate
        for candidate_id, candidate in all_candidates.items()
        if not allowed_ids or candidate_id in allowed_ids
    }
    if not candidates:
        raise AmendmentError(
            AmendmentErrorCode.AMENDMENT_NOT_REPRESENTED_BY_MODELING_PROPOSAL
        )
    term = payload.get("rdf_term")
    evidence = payload.get("evidence_refs") or []
    sources = payload.get("source_refs") or []
    pointers = list(target_json_pointers) or list(declared_changed_json_pointers)
    matches = [
        candidate
        for candidate in candidates.values()
        if _term_matches(candidate, term, all_candidates)
        and _lineage_matches(
            candidate,
            pointers=pointers,
            evidence_refs=evidence,
            source_refs=sources,
        )
        and candidate.get("publication_scope") == "ABOX"
    ]
    if len(matches) != 1:
        code = (
            AmendmentErrorCode.REENTRY_SEMANTIC_MISMATCH
            if term is not None and not matches
            else AmendmentErrorCode.AMENDMENT_NOT_REPRESENTED_BY_MODELING_PROPOSAL
        )
        raise AmendmentError(
            code, "approved amendment is not uniquely represented by ModelingProposal"
        )
    return {
        "represented": True,
        "candidate": deepcopy(matches[0]),
        "candidate_ids": [matches[0]["candidate_id"]],
        "candidate_semantic_hash": semantic_hash(matches[0]),
    }


def verify_candidate_binding(**kwargs: Any) -> dict[str, Any]:
    return bind_amendment_to_proposal(**kwargs)
