"""Authority-bound effective candidate and entity IRI resolution."""

from __future__ import annotations

from typing import Any, Mapping

from ..modeling.canonical_json import semantic_hash
from ..modeling.package_validation import proposal_candidates_by_id


class CandidateResolutionError(ValueError):
    pass


def _effective(item: Mapping[str, Any], candidates: Mapping[str, Mapping[str, Any]]) -> Mapping[str, Any]:
    envelope = item.get("confirmed_candidate")
    if not isinstance(envelope, Mapping):
        raise CandidateResolutionError("confirmed item lacks confirmed_candidate")
    effective_id = envelope.get("effective_candidate_id")
    source_id = envelope.get("source_candidate_id")
    candidate = candidates.get(str(effective_id))
    if candidate is None and effective_id == source_id:
        candidate = candidates.get(str(source_id))
    if candidate is None and isinstance(item.get("decision"), str) and item.get("decision") == "MODIFY_AND_CONFIRM":
        # Modified candidates are stored in the Stage 05 envelope semantic content.
        candidate = envelope.get("semantic_content")
    if not isinstance(candidate, Mapping):
        raise CandidateResolutionError(f"effective candidate is not present: {effective_id}")
    return candidate


def resolve_effective_candidates(package: Mapping[str, Any], proposal: Mapping[str, Any]) -> dict[str, Mapping[str, Any]]:
    candidates = proposal_candidates_by_id(proposal)
    resolved: dict[str, Mapping[str, Any]] = {}
    for item in package.get("confirmed_abox_decisions", []):
        source_id = str(item.get("candidate_id"))
        envelope = item.get("confirmed_candidate", {})
        effective_id = str(envelope.get("effective_candidate_id"))
        candidate = _effective(item, candidates)
        if source_id in resolved and resolved[source_id] != candidate:
            raise CandidateResolutionError(f"candidate has multiple effective resolutions: {source_id}")
        resolved[source_id] = candidate
        resolved[effective_id] = candidate
    return resolved


def resolve_effective_entity_iris(package: Mapping[str, Any], proposal: Mapping[str, Any]) -> dict[str, str]:
    return resolve_entity_iris(resolve_effective_candidates(package, proposal))


def resolve_entity_iris(
    candidates: Mapping[str, Mapping[str, Any]],
) -> dict[str, str]:
    """Resolve ENTITY candidate identifiers to IRIs with Stage 06 collision rules.

    The compiler and Stage 07 forbidden-assertion projection share this pure
    resolver so an audit projection cannot drift from the published ABox.
    """

    entity_iris: dict[str, str] = {}
    by_iri: dict[str, str] = {}
    for candidate_id, candidate in candidates.items():
        if candidate.get("candidate_kind", "ENTITY") != "ENTITY":
            continue
        iri = candidate.get("proposed_iri")
        if not isinstance(iri, str) or not iri:
            raise CandidateResolutionError(f"ENTITY has no proposed_iri: {candidate_id}")
        marker = semantic_hash(candidate)
        previous = by_iri.get(iri)
        if previous is not None and previous != marker:
            raise CandidateResolutionError(f"duplicate entity IRI: {iri}")
        by_iri[iri] = marker
        entity_iris[candidate_id] = iri
    return entity_iris


def resolve_candidate_iri(candidate_id: str, entity_iris: Mapping[str, str]) -> str:
    try:
        return entity_iris[candidate_id]
    except KeyError as exc:
        raise CandidateResolutionError(f"candidate is not a confirmed ENTITY: {candidate_id}") from exc
