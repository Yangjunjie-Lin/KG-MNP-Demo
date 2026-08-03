"""Deterministic MNP process / authorization-code checks (separate from eligibility)."""

from __future__ import annotations

from datetime import datetime, timezone
from typing import Any

from rdflib import Graph, Literal
from rdflib.namespace import XSD

from kg_mnp_demo.application.errors import ApplicationError, ErrorCode
from kg_mnp_demo.application.serializers import json_safe, to_iso_utc
from kg_mnp_demo.namespaces import MNP
from kg_mnp_demo.rule_engine import resolve_case_uri

PROCESS_STEPS = [
    "ELIGIBILITY_CHECK",
    "AUTHORIZATION_CODE_REQUEST",
    "PORT_IN_SUBMISSION",
    "PORTING_EXECUTION",
    "PORTING_CONFIRMATION",
]


def _parse_dt(value: Any) -> datetime | None:
    if value is None:
        return None
    if isinstance(value, datetime):
        return value if value.tzinfo else value.replace(tzinfo=timezone.utc)
    text = str(value).replace("Z", "+00:00")
    try:
        dt = datetime.fromisoformat(text)
    except ValueError:
        return None
    if dt.tzinfo is None:
        dt = dt.replace(tzinfo=timezone.utc)
    return dt.astimezone(timezone.utc)


def _auth_from_graph(graph: Graph, case_id: str) -> dict[str, Any] | None:
    case_uri = resolve_case_uri(graph, case_id)
    if case_uri is None:
        return None
    for code in graph.objects(case_uri, MNP.hasAuthorizationCode):
        status = graph.value(code, MNP.authCodeStatus)
        issued = graph.value(code, MNP.authCodeIssuedAt)
        until = graph.value(code, MNP.authCodeValidUntil)
        return {
            "status": str(status) if status is not None else None,
            "issued_at": to_iso_utc(_parse_dt(issued)) if issued is not None else None,
            "valid_until": to_iso_utc(_parse_dt(until)) if until is not None else None,
            "masked_value": str(graph.value(code, MNP.authCodeValueMasked) or "") or None,
        }
    return None


def _auth_from_payload(payload: dict[str, Any] | None) -> dict[str, Any] | None:
    if not payload:
        return None
    process = payload.get("process") or {}
    auth = process.get("authorization_code")
    if isinstance(auth, dict):
        return {
            "status": auth.get("status"),
            "issued_at": auth.get("issued_at"),
            "valid_until": auth.get("valid_until"),
            "masked_value": auth.get("masked_value"),
        }
    return None


def evaluate_process_state(
    graph: Graph | None,
    case_id: str,
    *,
    decision: str | None,
    assessment_time: datetime | str | None,
    payload: dict[str, Any] | None = None,
) -> dict[str, Any]:
    """Return process transition permission separate from eligibility decision."""
    as_of = _parse_dt(assessment_time)
    if as_of is None:
        raise ApplicationError(ErrorCode.PROCESS_ASSESSMENT_TIME_REQUIRED)
    auth = None
    if graph is not None:
        auth = _auth_from_graph(graph, case_id)
    if auth is None:
        auth = _auth_from_payload(payload)

    blocking: list[dict[str, Any]] = []
    current_step = "ELIGIBILITY_CHECK"
    next_step = "AUTHORIZATION_CODE_REQUEST"
    can_advance = False

    if decision is None:
        blocking.append(
            {
                "code": "ELIGIBILITY_NOT_EVALUATED",
                "message": "资格评估尚未完成，不能进入后续流程。",
            }
        )
    elif decision != "ELIGIBLE":
        blocking.append(
            {
                "code": "ELIGIBILITY_NOT_PASSED",
                "message": "资格评估未通过，不能进入授权码或提交阶段。",
            }
        )
        current_step = "ELIGIBILITY_CHECK"
        next_step = "AUTHORIZATION_CODE_REQUEST"
    else:
        current_step = "AUTHORIZATION_CODE_REQUEST"
        next_step = "PORT_IN_SUBMISSION"
        if auth is None:
            blocking.append(
                {
                    "code": "AUTHORIZATION_CODE_MISSING",
                    "message": "授权码不存在。",
                }
            )
            if auth is None:
                auth = {"status": "MISSING", "issued_at": None, "valid_until": None}
        else:
            status = (auth.get("status") or "").upper()
            until = _parse_dt(auth.get("valid_until"))
            if status == "EXPIRED" or (until is not None and until < as_of):
                auth = {**auth, "status": "EXPIRED"}
                blocking.append(
                    {
                        "code": "AUTHORIZATION_CODE_EXPIRED",
                        "message": "授权码已过期。",
                    }
                )
            elif status in ("", "MISSING"):
                blocking.append(
                    {
                        "code": "AUTHORIZATION_CODE_MISSING",
                        "message": "授权码不存在。",
                    }
                )
            else:
                can_advance = True
                current_step = "AUTHORIZATION_CODE_REQUEST"
                next_step = "PORT_IN_SUBMISSION"

    # Termination agreement signed but not yet effective (CASE-08 style)
    term = (payload or {}).get("process", {}).get("termination_agreement") if payload else None
    if isinstance(term, dict):
        effective = _parse_dt(term.get("effective_at"))
        signed = _parse_dt(term.get("signed_at"))
        if signed is not None and effective is not None and effective > as_of:
            blocking.append(
                {
                    "code": "TERMINATION_NOT_EFFECTIVE",
                    "message": "解除协议已签署但尚未生效。",
                }
            )
            can_advance = False

    return json_safe(
        {
            "current_step": current_step,
            "next_step": next_step,
            "can_advance": can_advance,
            "blocking_reasons": blocking,
            "authorization_code": auth,
            "eligibility_decision": decision,
        }
    )
