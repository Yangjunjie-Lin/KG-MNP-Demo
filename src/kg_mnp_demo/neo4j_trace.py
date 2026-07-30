"""Cypher-backed trace queries for Neo4j."""

from __future__ import annotations

from pathlib import Path
from typing import Any

from kg_mnp_demo.loader import project_root
from kg_mnp_demo.neo4j_client import Neo4jConfig, run_read, session_scope


def cypher_dir() -> Path:
    return project_root() / "queries" / "cypher"


def _load_cypher(name: str) -> str:
    path = cypher_dir() / name
    return path.read_text(encoding="utf-8")


def decision_trace(case_id: str, *, config: Neo4jConfig | None = None) -> list[dict[str, Any]]:
    q = _load_cypher("decision_trace.cypher")
    with session_scope(config) as session:
        return run_read(session, q, case_id=case_id)


def blocking_reasons(case_id: str, *, config: Neo4jConfig | None = None) -> list[dict[str, Any]]:
    q = _load_cypher("blocking_reasons.cypher")
    with session_scope(config) as session:
        return run_read(session, q, case_id=case_id)


def affected_assessments(*, config: Neo4jConfig | None = None) -> list[dict[str, Any]]:
    q = _load_cypher("affected_assessments.cypher")
    with session_scope(config) as session:
        return run_read(session, q)


def source_alignment(*, config: Neo4jConfig | None = None) -> list[dict[str, Any]]:
    q = _load_cypher("source_alignment.cypher")
    with session_scope(config) as session:
        return run_read(session, q)


def fetch_evaluation_payload(case_id: str, *, config: Neo4jConfig | None = None) -> dict[str, Any]:
    """Rebuild CLI-compatible JSON from Neo4j for a loaded case."""
    with session_scope(config) as session:
        decision_rows = run_read(
            session,
            """
            MATCH (c:MNPCase {caseIdentifier: $case_id})
                  -[:hasEligibilityAssessment]->(a:EligibilityAssessment)
                  -[:producesDecision]->(d)
            WHERE a.assessmentIdentifier = $assessment_id
            RETURN d.decisionCode AS decision, a.assessmentIdentifier AS assessment_id
            LIMIT 1
            """,
            case_id=case_id,
            assessment_id=f"ASSESS-{case_id}",
        )
        if not decision_rows:
            raise KeyError(f"No Neo4j assessment found for {case_id}. Run neo4j-load first.")

        reasons = run_read(
            session,
            """
            MATCH (a:EligibilityAssessment {assessmentIdentifier: $assessment_id})
                  -[:producesBlockingReason]->(br:BlockingReason)
            OPTIONAL MATCH (br)-[:supportedByEvidence]->(e)
            OPTIONAL MATCH (br)-[:citesClause]->(cl)
            OPTIONAL MATCH (br)-[:recommendsAction]->(act)
            RETURN br.reasonCode AS reason_code,
                   br.ruleId AS rule_id,
                   br.ruleVersion AS rule_version,
                   br.effectiveFrom AS effective_from,
                   br.regulatoryClause AS regulatory_clause,
                   br.actionCode AS action_code,
                   e.evidenceId AS evidence_id,
                   e.evidenceStatus AS evidence_status,
                   e.sourceSystem AS source_system,
                   e.generatedAt AS generated_at,
                   e.validUntil AS valid_until,
                   e.evidenceType AS evidence_type
            ORDER BY br.reasonCode
            """,
            assessment_id=f"ASSESS-{case_id}",
        )

    blocking = []
    traces = []
    for r in reasons:
        evidence = None
        if r.get("evidence_id"):
            evidence = {
                "evidence_id": r["evidence_id"],
                "status": r.get("evidence_status"),
                "source_system": r.get("source_system"),
                "generated_at": r.get("generated_at"),
                "valid_until": r.get("valid_until"),
                "evidence_type": r.get("evidence_type"),
            }
        blocking.append(
            {
                "reason_code": r["reason_code"],
                "rule_id": r.get("rule_id"),
                "rule_version": r.get("rule_version"),
                "effective_from": r.get("effective_from"),
                "regulatory_clause": r.get("regulatory_clause"),
                "action_code": r.get("action_code"),
                "evidence": evidence,
            }
        )
        traces.append(
            {
                "case": case_id,
                "assessment": f"ASSESS-{case_id}",
                "evidence": r.get("evidence_id"),
                "rule": r.get("rule_id"),
                "rule_version": r.get("rule_version"),
                "clause": r.get("regulatory_clause"),
                "decision": decision_rows[0]["decision"],
                "action": r.get("action_code"),
                "reason": r["reason_code"],
            }
        )

    return {
        "case_id": case_id,
        "decision": decision_rows[0]["decision"],
        "blocking_reasons": blocking,
        "trace_paths": traces,
        "backend": "neo4j",
        "validation_status": "PASSED",
    }
