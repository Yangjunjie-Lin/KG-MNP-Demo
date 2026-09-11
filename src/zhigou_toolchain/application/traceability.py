"""Structured trace projection; deliberately contains no free-form explanation."""

from __future__ import annotations

import json
from typing import Any

from .policy import QueryCategory
from .publication_binding import PublicationBinding


def _terms(row: dict[str, Any]) -> dict[str, dict[str, Any]]:
    return {
        binding["variable"]: binding["term"]
        for binding in row.get("bindings", [])
    }


def build_traceability(
    *,
    binding: PublicationBinding,
    category: QueryCategory,
    parameters: dict[str, Any],
    rows: list[dict[str, Any]],
) -> dict[str, Any]:
    base: dict[str, Any] = {
        "queried_resource": parameters,
        "publication": {
            "publication_id": binding.publication_id,
            "publication_semantic_hash": binding.publication_semantic_hash,
        },
        "compilation": {"compilation_id": binding.compilation_id},
        "graphdb": {
            "repository_id": binding.repository_id,
            "graph_iris": sorted(
                {
                    term.get("iri")
                    for row in rows
                    for term in _terms(row).values()
                    if term.get("term_type") == "IRI" and ":graph:" in term.get("iri", "")
                }
            ),
        },
        "business_facts": [],
        "modeling": [],
        "review": [],
        "evidence": [],
        "source": [],
    }
    if category not in {
        QueryCategory.PROVENANCE,
        QueryCategory.REVIEW_TRACE,
        QueryCategory.SOURCE_TRACE,
        QueryCategory.EVIDENCE_TRACE,
        QueryCategory.CROSS_TRACE,
    }:
        return base
    facts: set[tuple[str, str, str]] = set()
    modeling: set[tuple[str, str, str]] = set()
    reviews: set[tuple[str, str, str, str]] = set()
    evidence: set[str] = set()
    sources: set[str] = set()
    for row in rows:
        terms = _terms(row)
        subject = terms.get("subject", {}).get("iri")
        predicate = terms.get("predicate", {}).get("iri")
        object_term = terms.get("object")
        if subject and predicate and object_term:
            facts.add((subject, predicate, json.dumps(object_term, ensure_ascii=False, sort_keys=True, separators=(",", ":"))))
        assertion = terms.get("assertion", {}).get("iri")
        candidate = terms.get("candidateId", {}).get("iri")
        effective = terms.get("effectiveCandidateId", {}).get("iri") or candidate
        if assertion:
            modeling.add((assertion, candidate or "", effective or ""))
        decision = terms.get("decisionId", {}).get("iri")
        outcome = terms.get("outcome", {}).get("lexical_form")
        reviewer = terms.get("reviewerId", {}).get("iri")
        decided_at = terms.get("decidedAt", {}).get("lexical_form")
        if decision:
            reviews.add((decision, outcome or "", reviewer or "", decided_at or ""))
        if terms.get("evidenceRef", {}).get("iri"):
            evidence.add(terms["evidenceRef"]["iri"])
        if terms.get("sourceRef", {}).get("iri"):
            sources.add(terms["sourceRef"]["iri"])
    for subject, predicate, serialized_object in sorted(facts):
        object_term = json.loads(serialized_object)
        base["business_facts"].append(
            {"subject": {"term_type": "IRI", "iri": subject}, "predicate": {"term_type": "IRI", "iri": predicate}, "object": object_term}
        )
    base["modeling"] = [
        {
            "assertion_id": assertion,
            "candidate_id": candidate or None,
            "effective_candidate_id": effective or None,
        }
        for assertion, candidate, effective in sorted(modeling)
    ]
    base["review"] = [
        {
            "decision_id": decision,
            "outcome": outcome or None,
            "reviewer_id": reviewer or None,
            "decided_at": decided_at or None,
        }
        for decision, outcome, reviewer, decided_at in sorted(reviews)
    ]
    base["evidence"] = [{"evidence_ref": value} for value in sorted(evidence)]
    base["source"] = [{"source_ref": value} for value in sorted(sources)]
    return base
