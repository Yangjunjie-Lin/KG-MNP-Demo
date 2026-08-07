"""Deterministic audit-only projection of rejected/deferred ABox assertions."""

from __future__ import annotations

from dataclasses import dataclass
import hashlib
from pathlib import Path
from typing import Any, Mapping

from rdflib import Literal, URIRef

from ..compilation.abox_compiler import (
    ABoxCompilationError,
    candidate_to_rdf_triple,
)
from ..compilation.candidate_resolution import (
    CandidateResolutionError,
    resolve_effective_candidates,
    resolve_entity_iris,
)
from ..compilation.rdf_canonical import canonical_ntriples
from ..modeling.canonical_json import canonical_json_bytes
from ..modeling.dependencies import ROOT, TERM_INVENTORY_PATH, verify_ontology_baseline_manifest
from ..modeling.package_validation import (
    load_term_type_index,
    proposal_candidates_by_id,
)


class ForbiddenAssertionProjectionError(ValueError):
    pass


@dataclass(frozen=True)
class ForbiddenAssertionProjection:
    records: tuple[dict[str, Any], ...]
    triples: tuple[tuple[Any, Any, Any], ...]
    ntriples: bytes
    semantic_hash: str

    @property
    def statement_count(self) -> int:
        return len(set(self.triples))

    def as_json(self) -> dict[str, Any]:
        return {
            "contract_version": "1.0",
            "forbidden_assertion_count": self.statement_count,
            "projection_record_count": len(self.records),
            "canonical_ntriples_sha256": hashlib.sha256(self.ntriples).hexdigest(),
            "semantic_hash": self.semantic_hash,
            "records": list(self.records),
        }


def _rdf_object(term: Any) -> dict[str, Any]:
    if isinstance(term, URIRef):
        return {"term_type": "IRI", "value": str(term)}
    if isinstance(term, Literal):
        value: dict[str, Any] = {"term_type": "LITERAL", "value": str(term)}
        if term.language:
            value["language"] = term.language
        if term.datatype:
            value["datatype_iri"] = str(term.datatype)
        return value
    raise ForbiddenAssertionProjectionError(
        f"unsupported projected RDF object term: {type(term).__name__}"
    )


def _not_applicable(
    decision: Mapping[str, Any],
    *,
    candidate_kind: str,
    reason: str,
) -> dict[str, Any]:
    source_id = decision.get("candidate_id")
    return {
        "decision_id": str(decision["decision_id"]),
        "decision_outcome": str(decision["decision"]),
        "source_candidate_id": str(source_id) if isinstance(source_id, str) else None,
        "effective_candidate_id": str(source_id) if isinstance(source_id, str) else None,
        "candidate_kind": candidate_kind,
        "projection_status": "NOT_APPLICABLE",
        "reason": reason,
        "subject": None,
        "predicate": None,
        "object": None,
        "canonical_ntriples_line": None,
    }


def project_forbidden_business_assertions(
    proposal: Mapping[str, Any],
    final_review_decision_log: Mapping[str, Any],
    confirmed_modeling_package: Mapping[str, Any],
    ontology_baseline: Mapping[str, Any],
    *,
    root: Path = ROOT,
) -> ForbiddenAssertionProjection:
    """Project REJECT/DEFER decisions without publishing the projected triples."""

    root = Path(root).resolve()
    baseline_errors = verify_ontology_baseline_manifest(ontology_baseline, root=root)
    if baseline_errors:
        raise ForbiddenAssertionProjectionError(
            "Stage 03 baseline verification failed: " + "; ".join(baseline_errors)
        )
    term_types = load_term_type_index(
        root / "docs" / "ontology" / TERM_INVENTORY_PATH.name
    )
    proposal_candidates = proposal_candidates_by_id(proposal)
    candidates: dict[str, Mapping[str, Any]] = dict(proposal_candidates)
    # Overlay confirmed effective resolutions so references to a modified
    # confirmed ENTITY resolve exactly as they do in Stage 06.
    package_items = []
    for item in confirmed_modeling_package.get("confirmed_abox_decisions", []):
        envelope = item.get("confirmed_candidate", {})
        source_id = envelope.get("source_candidate_id")
        effective_id = envelope.get("effective_candidate_id")
        if source_id in proposal_candidates or effective_id in proposal_candidates:
            package_items.append(item)
    if package_items:
        package_for_resolution = dict(confirmed_modeling_package)
        package_for_resolution["confirmed_abox_decisions"] = package_items
        candidates.update(resolve_effective_candidates(package_for_resolution, proposal))
    entity_iris = resolve_entity_iris(candidates)
    records: list[dict[str, Any]] = []
    triples: list[tuple[Any, Any, Any]] = []
    for decision in sorted(
        final_review_decision_log.get("decisions", []),
        key=lambda item: str(item.get("decision_id")),
    ):
        outcome = decision.get("decision")
        if outcome not in {"REJECT", "DEFER"}:
            continue
        candidate_id = decision.get("candidate_id")
        if not isinstance(candidate_id, str):
            records.append(
                _not_applicable(
                    decision,
                    candidate_kind="UNRESOLVED_ISSUE",
                    reason="UNRESOLVED_ISSUE_NO_FORMAL_ABOX_TRIPLE",
                )
            )
            continue
        candidate = proposal_candidates.get(candidate_id)
        if candidate is None:
            raise ForbiddenAssertionProjectionError(
                f"reviewed Candidate is absent from ModelingProposal: {candidate_id}"
            )
        kind = str(candidate.get("candidate_kind", "ENTITY"))
        if candidate.get("publication_scope") != "ABOX":
            records.append(
                _not_applicable(
                    decision,
                    candidate_kind=kind,
                    reason="NON_ABOX_CANDIDATE_NO_FORMAL_BUSINESS_TRIPLE",
                )
            )
            continue
        if kind == "MAPPING_ASSERTION":
            records.append(
                _not_applicable(
                    decision,
                    candidate_kind=kind,
                    reason="MAPPING_ASSERTION_NO_FORMAL_ABOX_TRIPLE",
                )
            )
            continue
        candidate_with_id = dict(candidate)
        candidate_with_id.setdefault("candidate_id", candidate_id)
        try:
            triple = candidate_to_rdf_triple(
                candidate_with_id, entity_iris, term_types
            )
        except (ABoxCompilationError, CandidateResolutionError):
            records.append(
                _not_applicable(
                    decision,
                    candidate_kind=kind,
                    reason="CANDIDATE_CANNOT_FORM_FORMAL_ABOX_TRIPLE",
                )
            )
            continue
        line = canonical_ntriples([triple]).decode("utf-8").rstrip("\n")
        triples.append(triple)
        records.append(
            {
                "decision_id": str(decision["decision_id"]),
                "decision_outcome": str(outcome),
                "source_candidate_id": candidate_id,
                "effective_candidate_id": candidate_id,
                "candidate_kind": kind,
                "projection_status": "PROJECTED",
                "reason": None,
                "subject": str(triple[0]),
                "predicate": str(triple[1]),
                "object": _rdf_object(triple[2]),
                "canonical_ntriples_line": line,
            }
        )
    ntriples = canonical_ntriples(triples)
    semantic_content = {
        "records": records,
        "canonical_ntriples_sha256": hashlib.sha256(ntriples).hexdigest(),
    }
    semantic_hash = hashlib.sha256(canonical_json_bytes(semantic_content)).hexdigest()
    return ForbiddenAssertionProjection(
        records=tuple(records),
        triples=tuple(triples),
        ntriples=ntriples,
        semantic_hash=semantic_hash,
    )
