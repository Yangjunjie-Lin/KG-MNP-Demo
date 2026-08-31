"""Deterministic lexical alignment without semantic-probability claims."""

from __future__ import annotations

from difflib import SequenceMatcher
from typing import Any

from kg_mnp.contracts.canonical import stable_urn
from kg_mnp.contracts.registry import validate_contract

from .artifacts import finalize_document, verify_document
from .baseline import verify_baseline_snapshot
from .limits import ModelingLimits
from .terminology import normalize_term, verify_terminology_catalog


def _alignment(term: dict[str, Any], element: dict[str, Any] | None, alignment_type: str, score: int, rationale: str, ambiguity_group: str | None) -> dict[str, Any]:
    semantic = {"source_term_id": term["term_id"], "target_element_id": element["element_id"] if element else None, "alignment_type": alignment_type, "score_basis_points": score}
    return {
        "alignment_id": stable_urn("term-alignment", semantic), "source_term_id": term["term_id"],
        "target_element_id": element["element_id"] if element else None,
        "target_iri": element["iri"] if element else None, "alignment_type": alignment_type,
        "score_basis": "deterministic lexical ranking; not semantic correctness probability",
        "score_basis_points": score, "provider_snapshot_id": None,
        "evidence_refs": term["evidence_refs"], "rationale": rationale,
        "ambiguity_group": ambiguity_group, "review_required": True,
    }


def align_terms(
    terminology: dict[str, Any], baseline: dict[str, Any], *, limits: ModelingLimits | None = None,
) -> dict[str, Any]:
    verify_terminology_catalog(terminology)
    verify_baseline_snapshot(baseline)
    effective_limits = limits or ModelingLimits()
    alignments: list[dict[str, Any]] = []
    for term in terminology["terms"]:
        ranked: list[tuple[int, str, dict[str, Any], str]] = []
        for element in baseline["elements"]:
            labels = [item["value"] for item in element["labels"]]
            iri_local_name = element["iri"].rsplit("#", 1)[-1].rsplit("/", 1)[-1]
            aliases: list[str] = []
            if term["candidate_iris"] and element["iri"] in term["candidate_iris"]:
                ranked.append((10000, "EXACT_IRI", element, "declared candidate IRI equals baseline IRI"))
            for label in labels:
                if term["lexical_form"] == label:
                    ranked.append((10000, "EXACT_LABEL", element, "lexical form equals baseline label"))
                elif term["normalized_form"] == normalize_term(label):
                    ranked.append((9500, "NORMALIZED_LABEL", element, "normalized lexical forms are equal"))
                else:
                    score = int(SequenceMatcher(None, term["normalized_form"], normalize_term(label)).ratio() * 10000)
                    if score >= 6000:
                        ranked.append((score, "LEXICAL_SIMILARITY", element, "bounded lexical similarity ranking"))
            if term["normalized_form"] == normalize_term(iri_local_name) and not any(
                term["normalized_form"] == normalize_term(label) for label in labels
            ):
                ranked.append(
                    (
                        9500,
                        "NORMALIZED_LABEL",
                        element,
                        "normalized lexical form equals the locked baseline IRI local name",
                    )
                )
            if any(normalize_term(alias) in {normalize_term(label) for label in labels} for alias in term["aliases"]):
                aliases.append("DECLARED_ALIAS")
                ranked.append((9000, "DECLARED_ALIAS", element, "declared alias matches a baseline label"))
        deduped: dict[tuple[str, str], tuple[int, str, dict[str, Any], str]] = {}
        for row in ranked:
            key = (row[2]["element_id"], row[1])
            if key not in deduped or row[0] > deduped[key][0]:
                deduped[key] = row
        selected = sorted(deduped.values(), key=lambda row: (-row[0], row[2]["iri"], row[1]))[: effective_limits.max_alignment_candidates_per_term]
        if not selected:
            alignments.append(_alignment(term, None, "NO_MATCH", 0, "no bounded lexical match", None))
            continue
        top = selected[0][0]
        tied = [row for row in selected if row[0] == top]
        ambiguity = stable_urn("term-alignment-ambiguity", {"term_id": term["term_id"], "score_basis_points": top}) if len(tied) > 1 else None
        for score, alignment_type, element, rationale in selected:
            alignments.append(_alignment(term, element, alignment_type, score, rationale, ambiguity if score == top else None))
    core = {
        "manifest_kind": "KG_MNP_TERM_ALIGNMENT_SET", "schema_version": "1.0.0",
        "terminology_catalog_id": terminology["terminology_catalog_id"],
        "baseline_snapshot_id": baseline["baseline_snapshot_id"],
        "alignments": sorted(alignments, key=lambda item: item["alignment_id"]),
    }
    result = finalize_document(core, id_field="term_alignment_set_id", urn_kind="term-alignment-set")
    validate_contract("term-alignment-set", result)
    return result


def verify_alignment_set(value: dict[str, Any]) -> None:
    validate_contract("term-alignment-set", value)
    verify_document(value, id_field="term_alignment_set_id", urn_kind="term-alignment-set")
    if any(not item["review_required"] for item in value["alignments"]):
        raise ValueError("term alignment cannot bypass human review")
