"""Compare assessment results: evidence, rules, reasons, traces."""

from __future__ import annotations

from decimal import Decimal, InvalidOperation
from typing import Any

from kg_mnp_demo.application.serializers import json_safe


_EVIDENCE_COMPARE_FIELDS = (
    "evidence_type",
    "source_system",
    "status",
    "generated_at",
    "valid_until",
    "evidence_status",
    "status_code",
    "number_status_code",
    "contract_status",
    "contract_status_code",
    "contract_end_time",
    "outstanding_amount",
    "observed_amount",
    "days_since_last_port",
    "matched",
    "identity_match_flag",
    "has_payment_arrangement",
)


def _norm_amount(value: Any) -> Decimal | None:
    if value is None:
        return None
    try:
        return Decimal(str(value))
    except (InvalidOperation, TypeError, ValueError):
        return None


def _norm_field(key: str, value: Any) -> Any:
    if value is None:
        return None
    if key in {"outstanding_amount", "observed_amount"}:
        return _norm_amount(value)
    if isinstance(value, bool):
        return value
    return str(value)


def evidence_key(ev: dict[str, Any]) -> str:
    if ev.get("evidence_id"):
        return f"id:{ev['evidence_id']}"
    et = ev.get("evidence_type") or ""
    src = ev.get("source_system") or ""
    return f"type:{et}|src:{src}"


def compare_evidence(
    before: list[dict[str, Any]] | None,
    after: list[dict[str, Any]] | None,
) -> dict[str, Any]:
    left = {evidence_key(e): e for e in (before or []) if isinstance(e, dict)}
    right = {evidence_key(e): e for e in (after or []) if isinstance(e, dict)}
    added = [right[k] for k in sorted(set(right) - set(left))]
    removed = [left[k] for k in sorted(set(left) - set(right))]
    modified: list[dict[str, Any]] = []
    for key in sorted(set(left) & set(right)):
        changes: dict[str, Any] = {}
        a, b = left[key], right[key]
        fields = set(_EVIDENCE_COMPARE_FIELDS) | set(a.keys()) | set(b.keys())
        for field in sorted(fields):
            if field in {"evidence_id", "evidence_iri", "iri"}:
                continue
            av = _norm_field(field, a.get(field))
            bv = _norm_field(field, b.get(field))
            if av != bv and (field in a or field in b):
                # Only report meaningful shared/compare fields or present on both sides
                if field in _EVIDENCE_COMPARE_FIELDS or (field in a and field in b):
                    changes[field] = {"before": a.get(field), "after": b.get(field)}
        if changes:
            modified.append({"key": key, "changes": changes})
    return json_safe({"added": added, "removed": removed, "modified": modified})


def compare_rule_results(
    before: list[dict[str, Any]] | None,
    after: list[dict[str, Any]] | None,
) -> list[dict[str, Any]]:
    left = {
        (r.get("rule_id"), r.get("version") or r.get("rule_version")): r
        for r in (before or [])
        if isinstance(r, dict) and r.get("rule_id")
    }
    right = {
        (r.get("rule_id"), r.get("version") or r.get("rule_version")): r
        for r in (after or [])
        if isinstance(r, dict) and r.get("rule_id")
    }
    # Index also by rule_id for status comparison across same id
    left_by_id = {r.get("rule_id"): r for r in (before or []) if isinstance(r, dict)}
    right_by_id = {r.get("rule_id"): r for r in (after or []) if isinstance(r, dict)}
    rule_ids = sorted(set(left_by_id) | set(right_by_id))
    rows: list[dict[str, Any]] = []
    for rid in rule_ids:
        b = left_by_id.get(rid) or {}
        a = right_by_id.get(rid) or {}
        vb = b.get("version") or b.get("rule_version")
        va = a.get("version") or a.get("rule_version")
        sb = b.get("status")
        sa = a.get("status")
        changed = (vb != va) or (sb != sa) or (not b) or (not a)
        kind = "unchanged"
        if not b and a:
            kind = "added"
        elif b and not a:
            kind = "removed"
        elif vb != va and sb != sa:
            kind = "version_and_status_changed"
        elif vb != va:
            kind = "version_changed"
        elif sb != sa:
            kind = "status_changed"
        rows.append(
            {
                "rule_id": rid,
                "version_before": vb,
                "version_after": va,
                "status_before": sb,
                "status_after": sa,
                "changed": changed,
                "change_kind": kind,
            }
        )
    return json_safe(rows)


def compare_reasons(
    before: list[dict[str, Any]] | None,
    after: list[dict[str, Any]] | None,
) -> dict[str, Any]:
    b = {r.get("reason_code") for r in (before or []) if r.get("reason_code")}
    a = {r.get("reason_code") for r in (after or []) if r.get("reason_code")}
    return json_safe(
        {
            "added": sorted(a - b),
            "removed": sorted(b - a),
        }
    )


def compare_traces(
    before: dict[str, Any] | None,
    after: dict[str, Any] | None,
) -> dict[str, Any]:
    be = (before or {}).get("edges") or []
    ae = (after or {}).get("edges") or []
    bn = (before or {}).get("nodes") or []
    an = (after or {}).get("nodes") or []
    return json_safe(
        {
            "baseline_edge_count": len(be),
            "scenario_edge_count": len(ae),
            "baseline_node_count": len(bn),
            "scenario_node_count": len(an),
            "edge_count_delta": len(ae) - len(be),
            "node_count_delta": len(an) - len(bn),
        }
    )


def build_what_if_diff(
    baseline: dict[str, Any],
    scenario: dict[str, Any],
    changes: dict[str, Any] | None = None,
) -> dict[str, Any]:
    if "error" in baseline or "error" in scenario:
        return json_safe(
            {
                "baseline": baseline,
                "scenario": scenario,
                "changes": changes or {},
                "decision_change": {
                    "changed": False,
                    "from": baseline.get("decision"),
                    "to": scenario.get("decision"),
                },
                "rule_changes": [],
                "reason_changes": {"added": [], "removed": []},
                "evidence_changes": {"added": [], "removed": [], "modified": []},
                "trace_changes": {},
            }
        )
    return json_safe(
        {
            "baseline": {
                "decision": baseline.get("decision"),
                "execution_id": baseline.get("execution_id"),
                "case_id": baseline.get("case_id"),
            },
            "scenario": {
                "decision": scenario.get("decision"),
                "execution_id": scenario.get("execution_id"),
                "case_id": scenario.get("case_id"),
            },
            "changes": changes or {},
            "decision_change": {
                "changed": baseline.get("decision") != scenario.get("decision"),
                "from": baseline.get("decision"),
                "to": scenario.get("decision"),
            },
            "rule_changes": compare_rule_results(
                baseline.get("rule_results"), scenario.get("rule_results")
            ),
            "reason_changes": compare_reasons(
                baseline.get("blocking_reasons"), scenario.get("blocking_reasons")
            ),
            "evidence_changes": compare_evidence(
                baseline.get("evidence"), scenario.get("evidence")
            ),
            "trace_changes": compare_traces(
                baseline.get("trace_subgraph"), scenario.get("trace_subgraph")
            ),
        }
    )
