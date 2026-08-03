#!/usr/bin/env python
"""Seed CASE-01..CASE-09 assessments into local SQLite (explicit only)."""

from __future__ import annotations

import json
import sys
import uuid
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "src"))

from kg_mnp_demo.application.assessment_service import AssessmentService, write_assessment_artifacts
from kg_mnp_demo.loader import load_case_graph, project_root
from kg_mnp_demo.namespaces import CASE_FILES, CASE_JSON_FILES
from kg_mnp_demo.storage import AssessmentRepository, ArtifactRepository, Database
from kg_mnp_demo.evaluator import evaluate_case
from kg_mnp_demo.inference import apply_owlrl
from kg_mnp_demo.application.contracts import build_assessment_response
from kg_mnp_demo.application.serializers import json_safe, sort_stable
from kg_mnp_demo.trace_graph import build_assessment_subgraph
from kg_mnp_demo.validator import validate_graph


def seed_json_case(case_id: str, service: AssessmentService, repo: AssessmentRepository, arts: ArtifactRepository) -> str:
    path = project_root() / "inputs" / CASE_JSON_FILES[case_id]
    payload = json.loads(path.read_text(encoding="utf-8"))
    execution_id = str(uuid.uuid4())
    execution = service.assess_execution(payload, execution_id=execution_id)
    out = arts.execution_dir(execution_id)
    names = write_assessment_artifacts(execution, out, write_html=False)
    execution.response["artifacts"] = arts.relative_artifacts(names)
    repo.save_execution(
        execution_id=execution.response["execution_id"],
        case_id=execution.response["case_id"],
        assessment_time=execution.response["assessment_time"],
        input_payload=payload,
        result=execution.response,
        artifact_directory=out.name,
        force_recompute=True,
    )
    if case_id == "CASE-06":
        # Explicit historical snapshot using superseded rule version (for rule-update queries).
        hist_id = str(uuid.uuid4())
        hist = json_safe(
            {
                **execution.response,
                "execution_id": hist_id,
                "assessment_time": "2026-05-15T00:00:00Z",
                "rule_results": [
                    {
                        "rule_id": "MNP-ELIG-005",
                        "version": "1.0",
                        "status": "PASS",
                        "effective_from": "2024-01-01T00:00:00Z",
                        "effective_to": "2026-05-31T23:59:59Z",
                    }
                ],
                "warnings": ["seeded historical dependency on MNP-ELIG-005 v1.0"],
            }
        )
        repo.save_execution(
            execution_id=hist_id,
            case_id="CASE-06",
            assessment_time="2026-05-15T00:00:00Z",
            input_payload={"case_id": "CASE-06", "source": "seed-history"},
            result=hist,
            force_recompute=True,
        )
    return execution.response["decision"]


def seed_ttl_only(case_id: str, repo: AssessmentRepository) -> str:
    g = load_case_graph(case_id)
    input_ok = validate_graph(g).conforms
    if input_ok:
        apply_owlrl(g)
        evaluation = evaluate_case(g, case_id, use_updated_rules=True, validate=False)
        assess_ok = validate_graph(g).conforms
        subgraph = build_assessment_subgraph(g, case_id)
    else:
        evaluation = {"decision": None, "blocking_reasons": [], "evidence": [], "rules": [], "remediation_actions": []}
        assess_ok = False
        subgraph = {"nodes": [], "edges": []}
    execution_id = str(uuid.uuid4())
    response = build_assessment_response(
        execution_id=execution_id,
        case_id=case_id,
        assessment_time=evaluation.get("assessment_time") or "2026-07-01T00:00:00Z",
        decision=evaluation.get("decision"),
        publication={
            "publishable": bool(assess_ok),
            "status": "PUBLISHABLE" if assess_ok else "NOT_PUBLISHABLE",
        },
        validations={
            "json_schema": {"label": "JSON Schema Validation", "status": "SKIPPED", "conforms": True, "detail": "TTL seed"},
            "input_graph": {"label": "Input Graph Validation", "status": "PASSED" if input_ok else "FAILED", "conforms": input_ok, "detail": ""},
            "assessment_graph": {"label": "Assessment Graph Validation", "status": "PASSED" if assess_ok else "FAILED", "conforms": assess_ok, "detail": ""},
        },
        evidence=sort_stable(list(evaluation.get("evidence") or [])),
        rule_results=sort_stable(list(evaluation.get("rules") or [])),
        blocking_reasons=sort_stable(list(evaluation.get("blocking_reasons") or [])),
        remediation_actions=sort_stable(list(evaluation.get("remediation_actions") or [])),
        trace_subgraph=subgraph,
    )
    response = json_safe(response)
    repo.save_execution(
        execution_id=execution_id,
        case_id=case_id,
        assessment_time=response["assessment_time"],
        input_payload={"case_id": case_id, "source": "ttl"},
        result=response,
        force_recompute=True,
    )
    return response.get("decision")


def main() -> int:
    db = Database()
    repo = AssessmentRepository(db)
    arts = ArtifactRepository()
    service = AssessmentService()
    results = {}
    for case_id in sorted(CASE_FILES):
        if case_id in CASE_JSON_FILES:
            decision = seed_json_case(case_id, service, repo, arts)
        else:
            decision = seed_ttl_only(case_id, repo)
        results[case_id] = decision
        print(f"{case_id}: {decision}")
    print(json.dumps(results, ensure_ascii=False, indent=2))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
