from __future__ import annotations

from fastapi import APIRouter

from kg_mnp_demo.application.errors import ApplicationError, ErrorCode
from kg_mnp_demo.evaluator import materialize_assessment
from kg_mnp_demo.inference import apply_owlrl
from kg_mnp_demo.loader import load_case_graph
from kg_mnp_demo.rule_engine import load_all_rule_versions
from kg_mnp_demo.trace import affected_assessments

router = APIRouter()


@router.get("/rules")
def list_rules():
    rules = load_all_rule_versions()
    items = sorted(
        [
            {
                "rule_id": r["rule_id"],
                "version": r["version"],
                "name": r.get("name"),
                "effective_from": r.get("effective_from"),
                "effective_to": r.get("effective_to"),
                "reason_code": r.get("reason_code"),
                "action_code": r.get("action_code"),
                "regulatory_clause": r.get("regulatory_clause"),
            }
            for r in rules
        ],
        key=lambda x: (x["rule_id"], x["version"]),
    )
    return {"items": items}


@router.get("/rules/{rule_id}")
def get_rule(rule_id: str):
    versions = [r for r in load_all_rule_versions() if r["rule_id"] == rule_id]
    if not versions:
        raise ApplicationError(ErrorCode.CASE_NOT_FOUND, message=f"未找到规则：{rule_id}", details=[rule_id])
    return {"rule_id": rule_id, "versions": versions}


@router.get("/rules/{rule_id}/versions")
def rule_versions(rule_id: str):
    return get_rule(rule_id)


@router.get("/rule-updates/affected-assessments")
def rule_update_affected():
    g = load_case_graph("CASE-06")
    apply_owlrl(g)
    materialize_assessment(g, "CASE-06", use_updated_rules=True, validate=False)
    return {"case_id": "CASE-06", "items": affected_assessments(g)}
