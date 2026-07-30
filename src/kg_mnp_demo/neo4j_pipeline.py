"""Orchestrate evaluate → Neo4j load for a case."""

from __future__ import annotations

from typing import Any

from kg_mnp_demo.evaluator import evaluate_case, materialize_assessment
from kg_mnp_demo.inference import apply_owlrl
from kg_mnp_demo.loader import load_case_graph
from kg_mnp_demo.neo4j_client import Neo4jConfig, ping
from kg_mnp_demo.neo4j_import import load_case_into_neo4j
from kg_mnp_demo.neo4j_trace import (
    affected_assessments,
    blocking_reasons,
    decision_trace,
    fetch_evaluation_payload,
    source_alignment,
)
from kg_mnp_demo.validator import validate_graph


def prepare_and_evaluate(case_id: str, *, use_updated_rules: bool = True):
    g = load_case_graph(case_id)
    validation = validate_graph(g)
    apply_owlrl(g)
    g, result = materialize_assessment(g, case_id, use_updated_rules=use_updated_rules)
    result["validation_status"] = "PASSED" if validation.conforms else "FAILED"
    if not validation.conforms:
        result["validation_detail"] = validation.text
    return g, result, validation


def neo4j_load_case(
    case_id: str,
    *,
    config: Neo4jConfig | None = None,
    reset: bool = False,
    use_updated_rules: bool = True,
) -> dict[str, Any]:
    status = ping(config)
    if not status.get("ok"):
        raise RuntimeError(f"Neo4j unavailable: {status}")
    g, result, validation = prepare_and_evaluate(case_id, use_updated_rules=use_updated_rules)
    load_info = load_case_into_neo4j(
        g, case_id, result, config=config, reset=reset
    )
    return {
        "case_id": case_id,
        "decision": result["decision"],
        "blocking_reasons": result["blocking_reasons"],
        "evidence": result.get("evidence"),
        "rules": result.get("rules"),
        "regulatory_clauses": result.get("regulatory_clauses"),
        "remediation_actions": result.get("remediation_actions"),
        "trace_paths": result.get("trace_paths"),
        "validation_status": result["validation_status"],
        "tmf_mappings_used": result.get("tmf_mappings_used"),
        "ontology_sources": result.get("ontology_sources"),
        "backend": "neo4j",
        "neo4j_load": load_info,
        "validation_ok": validation.conforms,
    }


def neo4j_evaluate_case(case_id: str, *, config: Neo4jConfig | None = None) -> dict[str, Any]:
    """Load (recompute + persist) then return Neo4j-backed payload."""
    loaded = neo4j_load_case(case_id, config=config, reset=False)
    try:
        from_db = fetch_evaluation_payload(case_id, config=config)
        loaded.update(
            {
                "decision": from_db["decision"],
                "blocking_reasons": from_db["blocking_reasons"],
                "trace_paths": from_db["trace_paths"],
            }
        )
    except KeyError:
        pass
    return loaded


def neo4j_trace_case(case_id: str, *, config: Neo4jConfig | None = None) -> dict[str, Any]:
    status = ping(config)
    if not status.get("ok"):
        raise RuntimeError(f"Neo4j unavailable: {status}")
    # Ensure fresh data
    neo4j_load_case(case_id, config=config, reset=False)
    return {
        "case_id": case_id,
        "backend": "neo4j",
        "decision_trace": decision_trace(case_id, config=config),
        "blocking_reasons": blocking_reasons(case_id, config=config),
        "affected_assessments": affected_assessments(config=config)
        if case_id == "CASE-06"
        else [],
        "source_alignment": source_alignment(config=config),
    }
