from __future__ import annotations

from fastapi import APIRouter, Depends, Query

from kg_mnp_demo.api.dependencies import AppState, get_state
from kg_mnp_demo.api.schemas.common import ERROR_RESPONSES
from kg_mnp_demo.api.schemas.rules import (
    AffectedAssessmentsResponse,
    RuleDetailResponse,
    RuleListResponse,
)
from kg_mnp_demo.application.errors import ApplicationError, ErrorCode
from kg_mnp_demo.rule_engine import load_all_rule_versions

router = APIRouter()


@router.get("/rules", response_model=RuleListResponse, responses=ERROR_RESPONSES)
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


@router.get(
    "/rules/{rule_id}",
    response_model=RuleDetailResponse,
    responses=ERROR_RESPONSES,
)
def get_rule(rule_id: str):
    versions = [r for r in load_all_rule_versions() if r["rule_id"] == rule_id]
    if not versions:
        raise ApplicationError(
            ErrorCode.RULE_NOT_FOUND,
            message=f"未找到规则：{rule_id}",
            details=[rule_id],
        )
    return {"rule_id": rule_id, "versions": versions}


@router.get(
    "/rules/{rule_id}/versions",
    response_model=RuleDetailResponse,
    responses=ERROR_RESPONSES,
)
def rule_versions(rule_id: str):
    return get_rule(rule_id)


@router.get(
    "/rule-updates/affected-assessments",
    response_model=AffectedAssessmentsResponse,
    responses=ERROR_RESPONSES,
)
def rule_update_affected(
    rule_id: str = Query(..., description="Rule identifier, e.g. MNP-ELIG-005"),
    old_version: str = Query(..., description="Superseded rule version"),
    new_version: str | None = Query(None, description="New rule version"),
    case_id: str | None = Query(None),
    state: AppState = Depends(get_state),
):
    items = state.repository.find_affected_by_rule_version(
        rule_id=rule_id,
        old_version=old_version,
        new_version=new_version,
        case_id=case_id,
    )
    return {
        "rule_id": rule_id,
        "old_version": old_version,
        "new_version": new_version,
        "items": items,
    }
