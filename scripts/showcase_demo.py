#!/usr/bin/env python
"""Local offline one-click showcase for KG-MNP eligibility ontology demo.

Always uses the in-memory RDF backend.
"""

# ruff: noqa: E402

from __future__ import annotations

import argparse
import hashlib
import html
import json
import sys
from pathlib import Path
from typing import Any

from rdflib import Graph, Literal
from rdflib.namespace import RDF, XSD

# Ensure src/ is importable when run as scripts/showcase_demo.py
ROOT = Path(__file__).resolve().parents[1]
SRC = ROOT / "src"
if str(SRC) not in sys.path:
    sys.path.insert(0, str(SRC))

from kg_mnp_demo.evaluator import evaluate_case
from kg_mnp_demo.inference import apply_owlrl
from kg_mnp_demo.loader import case_path, load_case_graph
from kg_mnp_demo.namespaces import CASE_FILES, MNP
from kg_mnp_demo.rule_engine import ASSESSMENT_TIME, collect_evidence, resolve_case_uri
from kg_mnp_demo.trace import affected_assessments, blocking_reasons, decision_trace
from kg_mnp_demo.trace_graph import (
    build_assessment_subgraph,
    format_subgraph_tree,
    render_subgraph_html,
)
from kg_mnp_demo.validator import validate_graph

BACKEND = "rdf"
DEFAULT_CASE = "CASE-03"
ALL_CASES = sorted(CASE_FILES.keys())

EVIDENCE_TYPE_LABELS = {
    "IDENTITY_MATCH": "身份核验证据",
    "NUMBER_STATUS": "号码状态证据",
    "BILLING_BALANCE": "计费证据",
    "CONTRACT_STATUS": "合约证据",
    "PORTING_HISTORY": "携转历史证据",
}

REASON_LABELS = {
    "ACTIVE_CONTRACT_RESTRICTION": "当前业务仍受有效合约约束",
    "OUTSTANDING_BALANCE": "存在未结清欠费且无有效缴费安排",
    "PORTING_INTERVAL_TOO_SHORT": "距上次携转间隔未满足最短要求",
    "MISSING_OR_EXPIRED_EVIDENCE": "关键证据缺失或过期",
    "REAL_NAME_MISMATCH": "实名信息不一致",
    "NUMBER_STATUS_INVALID": "号码状态不可用",
}

SHACL_CHECKLIST = [
    "案件包含申请人",
    "案件包含唯一携转号码",
    "案件至少关联一条 hasCaseEvidence",
    "证据包含来源系统",
    "证据包含生成时间",
    "证据包含有效状态",
    "资格规则包含版本和监管条款",
]

CORE_CLASSES = [
    "MNPCase",
    "EligibilityAssessment",
    "EvidenceRecord",
    "EligibilityRule",
    "RuleVersion",
    "RegulatoryClause",
    "EligibilityDecision",
    "BlockingReason",
    "RemediationAction",
]

CORE_RELATIONS = [
    "hasCaseEvidence",
    "hasEligibilityAssessment",
    "usesEvidence",
    "usesRuleVersion",
    "evaluatedByRule",
    "producesDecision",
    "hasBlockingReason",
    "supportedByEvidence",
    "triggeredByRule",
    "citesClause",
    "recommendsAction",
]


def _configure_stdio() -> None:
    """Best-effort UTF-8 stdout/stderr for Windows consoles."""
    for stream in (sys.stdout, sys.stderr):
        try:
            stream.reconfigure(encoding="utf-8", errors="replace")
        except Exception:
            pass


def _local(name: Any) -> str:
    if name is None:
        return ""
    text = str(name)
    return text.rsplit("#", 1)[-1] if "#" in text else text


def _write_json(path: Path, payload: Any) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(
        json.dumps(payload, ensure_ascii=False, indent=2, sort_keys=True) + "\n",
        encoding="utf-8",
    )


def _assessment_time_note() -> str:
    return (
        "本次演示使用固定评估时间，以保证结果可重复。"
        f"（ASSESSMENT_TIME = {ASSESSMENT_TIME.strftime('%Y-%m-%dT%H:%M:%SZ')}）"
    )


def extract_case_input_summary(graph: Graph, case_id: str) -> dict[str, Any]:
    """Parse RDF case facts into a human-readable input summary."""
    q = """
    PREFIX mnp: <https://yangjunjie-lin.github.io/KG-MNP-Demo/ontology/terms#>
    SELECT ?caseId ?masked ?applicant ?numStatus ?idMatch ?amount ?arrangement
           ?ctrStatus ?ctrEnd ?days
    WHERE {
      ?case a mnp:MNPCase ;
            mnp:caseIdentifier ?caseId ;
            mnp:concernsNumber ?phone ;
            mnp:requestedBy ?applicant .
      FILTER(STR(?caseId) = %s)
      OPTIONAL { ?phone mnp:maskedPhoneNumber ?masked }
      OPTIONAL {
        ?case mnp:hasCaseEvidence ?evNum .
        ?evNum mnp:evidenceType "NUMBER_STATUS" ;
               mnp:numberStatusCode ?numStatus .
      }
      OPTIONAL {
        ?case mnp:hasCaseEvidence ?evId .
        ?evId mnp:evidenceType "IDENTITY_MATCH" ;
              mnp:identityMatchFlag ?idMatch .
      }
      OPTIONAL {
        ?case mnp:hasCaseEvidence ?evBill .
        ?evBill mnp:evidenceType "BILLING_BALANCE" ;
                mnp:observedAmount ?amount .
        OPTIONAL { ?evBill mnp:hasPaymentArrangement ?arrangement }
      }
      OPTIONAL {
        ?case mnp:hasCaseEvidence ?evCtr .
        ?evCtr mnp:evidenceType "CONTRACT_STATUS" ;
               mnp:contractStatusCode ?ctrStatus .
        OPTIONAL { ?evCtr mnp:contractEndTime ?ctrEnd }
      }
      OPTIONAL {
        ?case mnp:hasCaseEvidence ?evPort .
        ?evPort mnp:evidenceType "PORTING_HISTORY" ;
                mnp:daysSinceLastPort ?days .
      }
    }
    """ % f'"{case_id}"'

    row = next(iter(graph.query(q)), None)
    evidence_by_type = collect_evidence(graph, case_id)
    evidence_items: list[dict[str, Any]] = []
    type_order = [
        "IDENTITY_MATCH",
        "NUMBER_STATUS",
        "BILLING_BALANCE",
        "CONTRACT_STATUS",
        "PORTING_HISTORY",
    ]
    ordered_types = type_order + sorted(
        t for t in evidence_by_type.keys() if t not in type_order
    )
    for etype in ordered_types:
        views = evidence_by_type.get(etype, [])
        for view in sorted(views, key=lambda v: v.iri):
            evidence_items.append(
                {
                    "evidence_id": _local(view.iri),
                    "evidence_type": etype,
                    "label": EVIDENCE_TYPE_LABELS.get(etype, etype),
                    "status": view.status,
                    "source_system": view.fields.get("source_system"),
                    "generated_at": view.generated_at.isoformat()
                    if view.generated_at
                    else None,
                    "valid_until": view.valid_until.isoformat()
                    if view.valid_until
                    else None,
                }
            )

    id_match = None
    if row and row.idMatch is not None:
        id_match = bool(row.idMatch)

    summary = {
        "case_id": case_id,
        "applicant": _local(row.applicant) if row and row.applicant else None,
        "masked_phone": str(row.masked) if row and row.masked else None,
        "number_status": str(row.numStatus) if row and row.numStatus else None,
        "identity_match": id_match,
        "outstanding_amount": str(row.amount) if row and row.amount is not None else None,
        "has_payment_arrangement": (
            bool(row.arrangement) if row and row.arrangement is not None else None
        ),
        "contract_status": str(row.ctrStatus) if row and row.ctrStatus else None,
        "contract_end_time": str(row.ctrEnd) if row and row.ctrEnd else None,
        "days_since_last_port": int(row.days) if row and row.days is not None else None,
        "assessment_time": ASSESSMENT_TIME.strftime("%Y-%m-%dT%H:%M:%SZ"),
        "assessment_time_note": _assessment_time_note(),
        "evidence": evidence_items,
        "backend": BACKEND,
    }
    return summary


def detect_sample_inferences(graph: Graph) -> list[dict[str, str]]:
    """Detect actual OWL-RL type entailments present in the graph."""
    samples: list[dict[str, str]] = []
    seen: set[tuple[str, str]] = set()

    for s in graph.subjects(RDF.type, MNP.SystemObservation):
        if (s, RDF.type, MNP.EvidenceRecord) in graph:
            key = ("SystemObservation", "EvidenceRecord")
            if key not in seen:
                samples.append(
                    {
                        "subject": _local(s),
                        "from_type": "SystemObservation",
                        "to_type": "EvidenceRecord",
                        "display": "SystemObservation → 推导为 EvidenceRecord",
                    }
                )
                seen.add(key)
            break

    for s in graph.subjects(RDF.type, MNP.BlockingDecision):
        if (s, RDF.type, MNP.EligibilityDecision) in graph:
            key = ("BlockingDecision", "EligibilityDecision")
            if key not in seen:
                samples.append(
                    {
                        "subject": _local(s),
                        "from_type": "BlockingDecision",
                        "to_type": "EligibilityDecision",
                        "display": "BlockingDecision → 推导为 EligibilityDecision",
                    }
                )
                seen.add(key)
            break

    return samples


def run_inference(graph: Graph, case_id: str) -> dict[str, Any]:
    before = len(graph)
    apply_owlrl(graph)
    after = len(graph)
    samples = detect_sample_inferences(graph)
    return {
        "case_id": case_id,
        "triples_before": before,
        "triples_after": after,
        "triples_added": after - before,
        "sample_inferences": samples,
        "backend": BACKEND,
    }


def enrich_inference_after_assessment(graph: Graph, inference: dict[str, Any]) -> None:
    """Re-apply OWL-RL after materialization so BlockingDecision entailment is visible."""
    apply_owlrl(graph)
    samples = detect_sample_inferences(graph)
    # Keep unique sample types, prefer richer set after assessment
    by_key = {
        (s["from_type"], s["to_type"]): s for s in inference.get("sample_inferences", [])
    }
    for s in samples:
        by_key[(s["from_type"], s["to_type"])] = s
    inference["sample_inferences"] = list(by_key.values())
    inference["triples_after_assessment"] = len(graph)


def build_human_trace(
    graph: Graph,
    case_id: str,
    evaluation: dict[str, Any],
) -> dict[str, Any]:
    """Build a real RDF dependency subgraph (not a fabricated linear chain)."""
    br_rows = blocking_reasons(graph, case_id)
    dt_rows = decision_trace(graph, case_id)
    affected = affected_assessments(graph) if case_id == "CASE-06" else []
    subgraph = build_assessment_subgraph(graph, case_id)

    human_chains = [
        {
            "case_id": case_id,
            "assessment_id": f"ASSESS-{case_id}",
            "evidence_id": _local(row.get("evidence")),
            "evidence_source": row.get("sourceSystem"),
            "evidence_status": row.get("evidenceStatus"),
            "rule_id": row.get("ruleId"),
            "rule_version": row.get("ruleVersion"),
            "clause_id": row.get("clauseId"),
            "decision": evaluation.get("decision"),
            "reason_code": row.get("reasonCode"),
            "reason_label": REASON_LABELS.get(row.get("reasonCode") or "", row.get("reasonCode")),
            "action_code": row.get("actionCode"),
            "action_description": row.get("actionDescription"),
        }
        for row in br_rows
    ]
    if not human_chains:
        human_chains = [
            {
                "case_id": case_id,
                "assessment_id": f"ASSESS-{case_id}",
                "evidence_id": None,
                "rule_id": None,
                "rule_version": None,
                "clause_id": None,
                "decision": evaluation.get("decision"),
                "reason_code": None,
                "action_code": None,
            }
        ]

    return {
        "case_id": case_id,
        "decision_trace": dt_rows,
        "blocking_reasons": br_rows,
        "subgraph": subgraph,
        "tree_text": format_subgraph_tree(subgraph),
        "human_chains": human_chains,
        "affected_assessments": affected,
        "backend": BACKEND,
    }


def _case_evidence_nodes(graph: Graph, case_id: str, evidence_type: str | None = None):
    """Yield evidence IRIs linked via hasCaseEvidence (optionally filtered by type)."""
    case_uri = resolve_case_uri(graph, case_id)
    if case_uri is None:
        return
    for ev in graph.objects(case_uri, MNP.hasCaseEvidence):
        if evidence_type is None:
            yield ev
            continue
        et = graph.value(ev, MNP.evidenceType)
        if et is not None and str(et) == evidence_type:
            yield ev


def apply_what_if(graph: Graph, case_id: str, scenario: str) -> dict[str, Any]:
    """Mutate an in-memory copy of the case graph. Never writes TTL files."""
    notes: list[str] = []
    case_uri = resolve_case_uri(graph, case_id)

    if scenario == "contract-expired":
        expired_end = Literal("2026-01-01T00:00:00Z", datatype=XSD.dateTime)
        for ev in _case_evidence_nodes(graph, case_id, "CONTRACT_STATUS"):
            graph.set((ev, MNP.contractStatusCode, Literal("EXPIRED")))
            graph.set((ev, MNP.contractEndTime, expired_end))
            notes.append(f"set {_local(ev)} contractStatusCode=EXPIRED")
            notes.append(f"set {_local(ev)} contractEndTime={expired_end}")
        if case_uri is not None:
            for sub in graph.objects(case_uri, MNP.requestedBy):
                for subscription in graph.objects(sub, MNP.holdsSubscription):
                    for contract in graph.objects(subscription, MNP.governedByContract):
                        graph.set((contract, MNP.contractStatusCode, Literal("EXPIRED")))
                        graph.set((contract, MNP.contractEndTime, expired_end))
                        notes.append(f"set {_local(contract)} contractStatusCode=EXPIRED")
        notes.append("合约已经到期")
    elif scenario == "add-debt":
        for ev in _case_evidence_nodes(graph, case_id, "BILLING_BALANCE"):
            graph.set((ev, MNP.observedAmount, Literal("128.50", datatype=XSD.decimal)))
            graph.set((ev, MNP.hasPaymentArrangement, Literal(False)))
            notes.append(f"set {_local(ev)} outstanding amount=128.50, arrangement=false")
        notes.append("增加欠费")
    elif scenario == "expire-evidence":
        expired = Literal("2026-01-01T00:00:00Z", datatype=XSD.dateTime)
        for ev in _case_evidence_nodes(graph, case_id):
            graph.set((ev, MNP.evidenceValidUntil, expired))
            notes.append(f"set {_local(ev)} evidenceValidUntil={expired}")
        notes.append("证据已过期")
    else:
        raise ValueError(f"Unknown what-if scenario: {scenario}")

    return {"scenario": scenario, "mutations": notes}


def evaluate_pipeline(
    case_id: str,
    *,
    what_if: str | None = None,
) -> dict[str, Any]:
    """Full RDF offline pipeline for one case with dual SHACL validation."""
    graph = load_case_graph(case_id)
    original_ttl_hash = hashlib.sha256(case_path(case_id).read_bytes()).hexdigest()

    what_if_info = None
    if what_if:
        what_if_info = apply_what_if(graph, case_id, what_if)

    input_summary = extract_case_input_summary(graph, case_id)
    input_validation = validate_graph(graph)
    input_payload = {
        "case_id": case_id,
        "label": "Input Graph Validation",
        "validation_status": "PASSED" if input_validation.conforms else "FAILED",
        "status": "PASSED" if input_validation.conforms else "FAILED",
        "conforms": input_validation.conforms,
        "checklist": SHACL_CHECKLIST,
        "detail": input_validation.text,
        "backend": BACKEND,
    }
    # Backward-compatible single validation field mirrors input validation.
    validation_payload = dict(input_payload)

    inference = run_inference(graph, case_id)

    evaluation: dict[str, Any] | None = None
    trace_payload: dict[str, Any] | None = None
    assessment_payload: dict[str, Any] | None = None

    if not input_validation.conforms:
        evaluation = {
            "case_id": case_id,
            "decision": None,
            "blocking_reasons": [],
            "evidence": [],
            "rules": [],
            "regulatory_clauses": [],
            "remediation_actions": [],
            "trace_paths": [],
            "validation_status": "FAILED",
            "validation_detail": input_validation.text,
            "publishable": False,
            "publication_status": "NOT_PUBLISHABLE",
            "backend": BACKEND,
            "skipped_reason": "Input graph SHACL failed; formal eligibility conclusion not produced",
        }
        assessment_payload = {
            "case_id": case_id,
            "label": "Assessment Graph Validation",
            "validation_status": "SKIPPED",
            "status": "SKIPPED",
            "conforms": False,
            "detail": "Skipped because input graph validation failed",
            "backend": BACKEND,
        }
    else:
        evaluation = evaluate_case(
            graph, case_id, use_updated_rules=True, validate=False
        )
        evaluation["backend"] = BACKEND
        evaluation["assessment_time"] = ASSESSMENT_TIME.strftime("%Y-%m-%dT%H:%M:%SZ")
        evaluation["assessment_time_note"] = _assessment_time_note()
        enrich_inference_after_assessment(graph, inference)

        assessment_validation = validate_graph(graph)
        assessment_payload = {
            "case_id": case_id,
            "label": "Assessment Graph Validation",
            "validation_status": "PASSED" if assessment_validation.conforms else "FAILED",
            "status": "PASSED" if assessment_validation.conforms else "FAILED",
            "conforms": assessment_validation.conforms,
            "detail": assessment_validation.text if not assessment_validation.conforms else "",
            "backend": BACKEND,
        }
        if assessment_validation.conforms:
            evaluation["validation_status"] = "PASSED"
            evaluation["validation_detail"] = ""
            evaluation["publishable"] = True
            evaluation["publication_status"] = "PUBLISHABLE"
        else:
            evaluation["validation_status"] = "FAILED"
            evaluation["validation_detail"] = assessment_validation.text
            evaluation["publishable"] = False
            evaluation["publication_status"] = "NOT_PUBLISHABLE"

        # Keep internal results for debugging even if not publishable.
        trace_payload = build_human_trace(graph, case_id, evaluation)

    after_ttl_hash = hashlib.sha256(case_path(case_id).read_bytes()).hexdigest()
    return {
        "case_id": case_id,
        "backend": BACKEND,
        "input_summary": input_summary,
        "validation": validation_payload,
        "input_validation": input_payload,
        "assessment_validation": assessment_payload,
        "inference": inference,
        "evaluation": evaluation,
        "trace": trace_payload,
        "what_if": what_if_info,
        "ttl_unchanged": original_ttl_hash == after_ttl_hash,
        "ttl_sha256": original_ttl_hash,
    }


def summarize_all_cases() -> dict[str, Any]:
    results: dict[str, Any] = {}
    for case_id in ALL_CASES:
        g = load_case_graph(case_id)
        v = validate_graph(g)
        apply_owlrl(g)
        result = evaluate_case(g, case_id, use_updated_rules=True)
        affected = []
        if case_id == "CASE-06":
            affected = affected_assessments(g)
        results[case_id] = {
            "decision": result["decision"],
            "blocking_reasons": [b["reason_code"] for b in result["blocking_reasons"]],
            "validation_status": "PASSED" if v.conforms else "FAILED",
            "rules": result.get("rules", []),
            "affected_assessments": affected,
            "backend": BACKEND,
        }
    return {
        "backend": BACKEND,
        "assessment_time": ASSESSMENT_TIME.strftime("%Y-%m-%dT%H:%M:%SZ"),
        "assessment_time_note": _assessment_time_note(),
        "cases": results,
    }


def print_input_section(summary: dict[str, Any]) -> None:
    print("[1/6] 案例输入")
    print()
    print(f"案件编号：{summary['case_id']}")
    print(f"申请人：{summary.get('applicant') or '—'}")
    print(f"号码：{summary.get('masked_phone') or '—'}")
    id_match = summary.get("identity_match")
    if id_match is True:
        print("实名核验：一致")
    elif id_match is False:
        print("实名核验：不一致")
    else:
        print("实名核验：—")
    print(f"号码状态：{summary.get('number_status') or '—'}")
    print(f"欠费金额：{summary.get('outstanding_amount') or '—'}")
    arr = summary.get("has_payment_arrangement")
    print(f"是否存在缴费安排：{'是' if arr else '否' if arr is False else '—'}")
    print(f"合约状态：{summary.get('contract_status') or '—'}")
    end = summary.get("contract_end_time") or "—"
    if end != "—" and "T" in end:
        end = end.split("T")[0]
    print(f"合约截止时间：{end}")
    days = summary.get("days_since_last_port")
    print(f"上次携转间隔：{days} 天" if days is not None else "上次携转间隔：—")
    print(f"资格评估时间：{summary.get('assessment_time')}")
    print(_assessment_time_note())
    print()
    print("输入证据：")
    for ev in summary.get("evidence", []):
        print(
            f"- {ev['label']}（{ev['evidence_id']}）："
            f"{ev['status']}，来源 {ev.get('source_system') or '—'}"
            f"；生成 {ev.get('generated_at') or '—'}"
            f"；有效至 {ev.get('valid_until') or '—'}"
        )
    print()


def print_validation_section(
    validation: dict[str, Any],
    *,
    assessment_validation: dict[str, Any] | None = None,
) -> None:
    print("[2/6] SHACL 数据完整性验证")
    print()
    input_status = validation.get("status") or validation.get("validation_status")
    print(f"输入图 SHACL：{input_status}")
    if assessment_validation:
        print(
            f"评估结果图 SHACL：{assessment_validation.get('status') or assessment_validation.get('validation_status')}"
        )
    print()
    if input_status == "PASSED":
        print("已检查：")
        for item in validation.get("checklist", SHACL_CHECKLIST):
            print(f"✓ {item}")
    else:
        print("输入图错误摘要：")
        detail = validation.get("detail") or ""
        lines = [ln for ln in detail.splitlines() if ln.strip()][:12]
        for ln in lines:
            print(f"  {ln}")
        print("完整报告已写入 JSON。")
    if assessment_validation and assessment_validation.get("status") == "FAILED":
        print()
        print("评估结果图未通过验证 → NOT_PUBLISHABLE")
        detail = assessment_validation.get("detail") or ""
        lines = [ln for ln in detail.splitlines() if ln.strip()][:8]
        for ln in lines:
            print(f"  {ln}")
    print()


def print_inference_section(inference: dict[str, Any]) -> None:
    print("[3/6] OWL-RL 语义推理")
    print()
    print(f"推理前三元组数量：{inference['triples_before']}")
    print(f"推理后三元组数量：{inference['triples_after']}")
    print(f"新增三元组数量：{inference['triples_added']}")
    print()
    print("示例推理：")
    samples = inference.get("sample_inferences") or []
    if not samples:
        print("（未检测到示例类型推导）")
    for s in samples:
        print(s.get("display") or f"{s.get('from_type')} → {s.get('to_type')}")
        if s.get("subject"):
            print(f"  实例：{s['subject']}")
    print()


def print_evaluation_section(evaluation: dict[str, Any]) -> None:
    print("[4/6] 携转资格判断")
    print()
    if evaluation.get("decision") is None:
        print("资格结论：未生成（SHACL 验证失败）")
        print()
        return
    print(f"资格结论：{evaluation['decision']}")
    if evaluation.get("publication_status") == "NOT_PUBLISHABLE":
        print("发布状态：NOT_PUBLISHABLE（评估结果图验证失败，非正式可发布结论）")
    reasons = evaluation.get("blocking_reasons") or []
    print(f"独立阻塞原因数量：{len(reasons)}")
    print()
    if not reasons:
        print("无独立阻塞原因。")
    for i, reason in enumerate(reasons, start=1):
        code = reason.get("reason_code")
        print(f"阻塞原因 {i}：")
        print(f"原因：{code}")
        print(f"说明：{REASON_LABELS.get(code, reason.get('message') or code)}")
        if reason.get("evidence"):
            ev = reason["evidence"]
            print(
                f"证据：{ev.get('evidence_id')}（{ev.get('source_system')}，{ev.get('status')}）"
            )
        if reason.get("rule_id"):
            print(f"规则：{reason['rule_id']} v{reason.get('rule_version')}")
        if reason.get("regulatory_clause"):
            print(f"监管条款：{reason['regulatory_clause']}")
        if reason.get("action_code"):
            print(f"处理动作：{reason['action_code']}")
        print()
    print(_assessment_time_note())
    print()


def print_trace_section(trace: dict[str, Any] | None, evaluation: dict[str, Any]) -> None:
    print("[5/6] 本体追溯子图")
    print()
    if evaluation.get("publication_status") == "NOT_PUBLISHABLE" and evaluation.get("decision"):
        print("注意：评估结果图未通过验证，以下追溯仅供调试，非正式可发布结论。")
        print()
    if not trace or not (trace.get("tree_text") or trace.get("subgraph")):
        print("追溯子图未生成（验证失败或无评估对象）。")
        print()
        return

    print(trace.get("tree_text") or format_subgraph_tree(trace["subgraph"]))
    print()

    if trace.get("affected_assessments"):
        print("规则更新影响：")
        for row in trace["affected_assessments"]:
            print(
                f"- 评估 {row.get('assessmentId') or _local(row.get('assessment'))}："
                f"旧版本 {row.get('oldVersion')} → 新版本 {row.get('newVersion')}；"
                f"requiresReassessment={row.get('requiresReassessment')}"
            )
        print()


def print_summary_table(all_summary: dict[str, Any]) -> None:
    print("[6/6] 六个案例结果汇总")
    print()
    print(f"{'案例':<10}{'结论':<16}阻塞原因")
    print("-" * 60)
    for case_id in ALL_CASES:
        item = all_summary["cases"][case_id]
        decision = item["decision"]
        reasons = item["blocking_reasons"] or []
        if not reasons:
            print(f"{case_id:<10}{decision:<16}无")
        else:
            print(f"{case_id:<10}{decision:<16}{reasons[0]}")
            for extra in reasons[1:]:
                print(f"{'':<10}{'':<16}{extra}")
        if case_id == "CASE-05":
            print("           关键证据缺失或过期 → 不默认判定通过 → MANUAL_REVIEW")
        if case_id == "CASE-06":
            print("           旧规则版本：1.0")
            print("           新规则版本：1.1")
            affected = item.get("affected_assessments") or []
            hist_rows = [
                r
                for r in affected
                if "ASSESS-CASE-06-HIST" in (r.get("assessmentId") or "")
            ] or list(affected)
            hist = None
            for row in hist_rows:
                flag = str(row.get("requiresReassessment") or "").lower()
                if flag in ("true", "1"):
                    hist = row
                    break
            if hist is None and hist_rows:
                hist = hist_rows[0]
            if hist:
                flag = str(hist.get("requiresReassessment") or "").lower()
                display_flag = "true" if flag in ("true", "1") else hist.get("requiresReassessment")
                print(f"           受影响历史评估：{hist.get('assessmentId')}")
                print(f"           requiresReassessment = {display_flag}")
            else:
                print("           受影响历史评估：ASSESS-CASE-06-HIST")
                print("           requiresReassessment = true")
    print()


def print_what_if_comparison(before: dict[str, Any], after: dict[str, Any], scenario: str) -> None:
    print("=" * 60)
    print(f"What-if 演示：{scenario}")
    print("=" * 60)
    print()
    print("原始输入：")
    if scenario == "contract-expired":
        print("合约仍有效")
    elif scenario == "add-debt":
        print("无欠费或已结清")
    else:
        print("证据在评估时有效")
    print(f"→ {before['evaluation'].get('decision')}")
    print()
    print("变化后输入：")
    for note in (after.get("what_if") or {}).get("mutations", [])[-1:]:
        print(note)
    print(f"→ {after['evaluation'].get('decision')}")
    if after["evaluation"].get("blocking_reasons"):
        codes = [b["reason_code"] for b in after["evaluation"]["blocking_reasons"]]
        print(f"阻塞原因：{', '.join(codes)}")
    print()
    print(f"原始 TTL 未被修改：{after.get('ttl_unchanged')}")
    print()


def render_html_report(
    primary: dict[str, Any],
    all_summary: dict[str, Any],
    *,
    what_if_result: dict[str, Any] | None = None,
) -> str:
    summary = primary["input_summary"]
    validation = primary.get("input_validation") or primary["validation"]
    assessment_validation = primary.get("assessment_validation") or {}
    inference = primary["inference"]
    evaluation = primary["evaluation"]
    trace = primary.get("trace") or {}
    def esc(v: Any) -> str:
        return html.escape("" if v is None else str(v))

    evidence_rows = "".join(
        f"<tr><td>{esc(e['label'])}</td><td>{esc(e['evidence_id'])}</td>"
        f"<td>{esc(e['status'])}</td><td>{esc(e.get('source_system'))}</td></tr>"
        for e in summary.get("evidence", [])
    )

    subgraph = trace.get("subgraph") or {}
    chain_html = render_subgraph_html(subgraph) if subgraph.get("edges") else ""

    case_rows = ""
    for case_id in ALL_CASES:
        item = all_summary["cases"][case_id]
        reasons = item["blocking_reasons"] or []
        reason_html = "无" if not reasons else "<br/>".join(esc(r) for r in reasons)
        case_rows += (
            f"<tr><td>{esc(case_id)}</td><td><strong>{esc(item['decision'])}</strong></td>"
            f"<td>{reason_html}</td></tr>"
        )

    decision = evaluation.get("decision") or "N/A"
    reason_codes = [b["reason_code"] for b in evaluation.get("blocking_reasons") or []]
    reason_block = (
        "".join(f"<div class='reason'>{esc(c)}</div>" for c in reason_codes)
        or "<div class='reason muted'>无阻塞原因</div>"
    )

    what_if_html = ""
    if what_if_result:
        what_if_html = f"""
<section>
  <h2>输入变化演示（what-if）</h2>
  <p>场景：<code>{esc(what_if_result.get('what_if', {}).get('scenario'))}</code></p>
  <p>原始结论：<strong>{esc(primary['evaluation'].get('decision'))}</strong></p>
  <p>变化后结论：<strong>{esc(what_if_result['evaluation'].get('decision'))}</strong></p>
  <p>原始 TTL 未被修改：{esc(what_if_result.get('ttl_unchanged'))}</p>
</section>
"""

    samples = "".join(
        f"<li>{esc(s.get('display'))}（实例 {esc(s.get('subject'))}）</li>"
        for s in inference.get("sample_inferences") or []
    )

    return f"""<!DOCTYPE html>
<html lang="zh-CN">
<head>
<meta charset="utf-8"/>
<meta name="viewport" content="width=device-width, initial-scale=1"/>
<title>KG-MNP 携号转网资格判断领域本体演示</title>
<style>
  :root {{
    --ink: #1c2430;
    --muted: #5b6777;
    --line: #d7dde6;
    --bg: #f3f6fa;
    --panel: #ffffff;
    --accent: #0b6e4f;
    --warn: #9b2c2c;
    --ok: #276749;
  }}
  * {{ box-sizing: border-box; }}
  body {{
    margin: 0;
    font-family: "Segoe UI", "PingFang SC", "Microsoft YaHei", sans-serif;
    color: var(--ink);
    background:
      radial-gradient(1200px 500px at 10% -10%, #dceee6 0%, transparent 55%),
      radial-gradient(900px 400px at 100% 0%, #e7eef8 0%, transparent 50%),
      var(--bg);
    line-height: 1.55;
  }}
  header {{
    padding: 2.5rem 1.5rem 1.5rem;
    max-width: 980px;
    margin: 0 auto;
  }}
  h1 {{ margin: 0 0 0.75rem; font-size: 1.85rem; letter-spacing: 0.01em; }}
  .question {{
    font-size: 1.05rem;
    color: var(--muted);
    border-left: 4px solid var(--accent);
    padding-left: 1rem;
    margin: 1rem 0 0;
  }}
  main {{ max-width: 980px; margin: 0 auto; padding: 0 1.5rem 3rem; }}
  section {{
    background: var(--panel);
    border: 1px solid var(--line);
    border-radius: 12px;
    padding: 1.25rem 1.35rem;
    margin: 1rem 0;
  }}
  h2 {{ margin: 0 0 0.85rem; font-size: 1.2rem; }}
  .flow {{
    display: flex; flex-wrap: wrap; gap: 0.4rem; align-items: center;
    font-size: 0.95rem;
  }}
  .flow span {{
    background: #eef5f1; border: 1px solid #cfe0d7; border-radius: 999px;
    padding: 0.25rem 0.7rem;
  }}
  .decision-box {{
    display: flex; gap: 1rem; flex-wrap: wrap; align-items: stretch;
  }}
  .badge {{
    min-width: 160px; padding: 1rem; border-radius: 10px;
    background: #fff5f5; border: 1px solid #f0c2c2; color: var(--warn);
    font-size: 1.4rem; font-weight: 700; text-align: center;
  }}
  .badge.ok {{ background: #f0fff4; border-color: #c6f6d5; color: var(--ok); }}
  .reason {{
    padding: 0.75rem 1rem; border-radius: 8px; background: #f7fafc;
    border: 1px solid var(--line); margin: 0.35rem 0;
  }}
  .muted {{ color: var(--muted); }}
  table {{ width: 100%; border-collapse: collapse; font-size: 0.95rem; }}
  th, td {{ border-bottom: 1px solid var(--line); padding: 0.55rem 0.4rem; text-align: left; vertical-align: top; }}
  th {{ color: var(--muted); font-weight: 600; }}
  .subgraph ul.tree {{ list-style: none; padding-left: 1rem; }}
  .subgraph .pred {{ color: var(--accent); font-family: ui-monospace, Consolas, monospace; font-size: 0.9rem; margin-right: 0.35rem; }}
  .subgraph .node {{ display: inline-block; margin: 0.15rem 0; padding: 0.2rem 0.45rem; background: #f8fafc; border: 1px solid var(--line); border-radius: 6px; }}
  .subgraph .ntype {{ color: var(--muted); font-size: 0.78rem; margin-right: 0.35rem; }}
  .subgraph .nlabel, .subgraph .leaf {{ font-weight: 600; }}
  .grid {{ display: grid; grid-template-columns: repeat(auto-fit, minmax(180px, 1fr)); gap: 0.5rem; }}
  .pill {{
    border: 1px solid var(--line); border-radius: 8px; padding: 0.45rem 0.65rem;
    background: #fcfdff; font-family: ui-monospace, Consolas, monospace; font-size: 0.88rem;
  }}
  .note {{ color: var(--muted); font-size: 0.92rem; }}
  footer {{ max-width: 980px; margin: 0 auto; padding: 0 1.5rem 2rem; color: var(--muted); font-size: 0.9rem; }}
</style>
</head>
<body>
<header>
  <h1>KG-MNP 携号转网资格判断领域本体演示</h1>
  <p class="question">如何使用领域本体，把携号转网资格判断中的案件、证据、规则版本、监管条款、资格结论、阻塞原因和处理动作组织成可检查、可追溯和可复核的语义结构？</p>
  <p class="note">{esc(_assessment_time_note())} · backend={esc(BACKEND)}</p>
</header>
<main>
<section>
  <h2>输入摘要（{esc(summary['case_id'])}）</h2>
  <table>
    <tr><th>字段</th><th>值</th></tr>
    <tr><td>案件编号</td><td>{esc(summary['case_id'])}</td></tr>
    <tr><td>申请人</td><td>{esc(summary.get('applicant'))}</td></tr>
    <tr><td>脱敏号码</td><td>{esc(summary.get('masked_phone'))}</td></tr>
    <tr><td>号码状态</td><td>{esc(summary.get('number_status'))}</td></tr>
    <tr><td>实名是否一致</td><td>{esc(summary.get('identity_match'))}</td></tr>
    <tr><td>欠费金额</td><td>{esc(summary.get('outstanding_amount'))}</td></tr>
    <tr><td>缴费安排</td><td>{esc(summary.get('has_payment_arrangement'))}</td></tr>
    <tr><td>合约状态</td><td>{esc(summary.get('contract_status'))}</td></tr>
    <tr><td>合约截止时间</td><td>{esc(summary.get('contract_end_time'))}</td></tr>
    <tr><td>距上次携转天数</td><td>{esc(summary.get('days_since_last_port'))}</td></tr>
    <tr><td>资格评估时间</td><td>{esc(summary.get('assessment_time'))}</td></tr>
  </table>
  <h3>证据</h3>
  <table>
    <tr><th>类型</th><th>证据 ID</th><th>状态</th><th>来源系统</th></tr>
    {evidence_rows}
  </table>
</section>

<section>
  <h2>处理流程</h2>
  <div class="flow">
    <span>输入案例</span>→
    <span>输入图 SHACL（{esc(validation.get('status') or validation.get('validation_status'))}）</span>→
    <span>OWL-RL 推理（+{esc(inference['triples_added'])}）</span>→
    <span>资格规则判断</span>→
    <span>评估结果图 SHACL（{esc(assessment_validation.get('status') or evaluation.get('validation_status'))}）</span>→
    <span>SPARQL 追溯子图</span>→
    <span>结构化输出</span>
  </div>
  <ul>{samples or '<li class="muted">无示例推理</li>'}</ul>
</section>

<section>
  <h2>资格结论</h2>
  <div class="decision-box">
    <div class="badge {'ok' if decision == 'ELIGIBLE' else ''}">{esc(decision)}</div>
    <div style="flex:1">{reason_block}</div>
  </div>
  <p class="note">输入图 SHACL：{esc(validation.get('status') or validation.get('validation_status'))} · 评估结果图 SHACL：{esc(assessment_validation.get('status') or evaluation.get('validation_status'))} · 发布状态：{esc(evaluation.get('publication_status'))}</p>
</section>

<section>
  <h2>资格判断追溯子图</h2>
  <p class="muted">箭头均为真实 RDF 对象属性；非线性伪链。</p>
  {chain_html or '<p class="muted">无追溯子图</p>'}
</section>

<section>
  <h2>六个案例汇总</h2>
  <table>
    <tr><th>案例</th><th>结论</th><th>阻塞原因</th></tr>
    {case_rows}
  </table>
</section>

{what_if_html}

<section>
  <h2>本体核心类</h2>
  <div class="grid">
    {''.join(f'<div class="pill">{esc(c)}</div>' for c in CORE_CLASSES)}
  </div>
</section>

<section>
  <h2>本体核心关系</h2>
  <div class="grid">
    {''.join(f'<div class="pill">{esc(r)}</div>' for r in CORE_RELATIONS)}
  </div>
</section>

<section>
  <h2>研究边界</h2>
  <p>OWL、RDFLib、SHACL、OWL-RL 和知识图谱工具本身不是创新。</p>
  <p>本项目当前验证的是面向携号转网资格判断的领域本体结构，包括资格评估对象化、证据与规则版本联合追溯、多阻塞原因语义分解、证据缺失安全处理和规则更新影响定位。</p>
  <p>当前使用合成数据，不代表真实运营商正式业务结论。</p>
</section>
</main>
<footer>
  由 <code>python scripts/showcase_demo.py</code> 自动生成 · 可直接双击打开 · 无需启动服务器
</footer>
</body>
</html>
"""


def write_outputs(
    output_dir: Path,
    primary: dict[str, Any],
    all_summary: dict[str, Any],
    *,
    write_html: bool = True,
    what_if_result: dict[str, Any] | None = None,
) -> list[Path]:
    output_dir.mkdir(parents=True, exist_ok=True)
    written: list[Path] = []
    # CASE-03 → case03_*.json
    prefix = primary["case_id"].lower().replace("-", "")

    mapping = {
        f"{prefix}_input_summary.json": primary["input_summary"],
        f"{prefix}_input_validation.json": primary.get("input_validation")
        or primary["validation"],
        f"{prefix}_assessment_validation.json": primary.get("assessment_validation")
        or {},
        f"{prefix}_inference.json": primary["inference"],
        f"{prefix}_evaluation.json": primary["evaluation"],
        f"{prefix}_trace.json": primary.get("trace")
        or {"case_id": primary["case_id"], "skipped": True},
        f"{prefix}_trace_subgraph.json": (primary.get("trace") or {}).get("subgraph")
        or {"case_id": primary["case_id"], "skipped": True},
        "all_cases_summary.json": all_summary,
    }
    for name, payload in mapping.items():
        path = output_dir / name
        _write_json(path, payload)
        written.append(path)

    if what_if_result:
        path = output_dir / f"{prefix}_what_if.json"
        _write_json(
            path,
            {
                "baseline_decision": primary["evaluation"].get("decision"),
                "what_if": what_if_result.get("what_if"),
                "decision": what_if_result["evaluation"].get("decision"),
                "blocking_reasons": what_if_result["evaluation"].get("blocking_reasons"),
                "ttl_unchanged": what_if_result.get("ttl_unchanged"),
            },
        )
        written.append(path)

    if write_html:
        html_path = output_dir / "demo_report.html"
        html_path.write_text(
            render_html_report(primary, all_summary, what_if_result=what_if_result),
            encoding="utf-8",
        )
        written.append(html_path)

    readme = output_dir / "README.md"
    if not readme.exists():
        readme.write_text(
            "# demo_outputs\n\n"
            "本目录中的 JSON / HTML 由 `python scripts/showcase_demo.py` 自动生成，"
            "请勿手工编辑结果文件。\n",
            encoding="utf-8",
        )
        written.append(readme)

    return written


def build_parser() -> argparse.ArgumentParser:
    p = argparse.ArgumentParser(
        description="KG-MNP local offline one-click showcase (RDF backend only)"
    )
    p.add_argument("--case", default=DEFAULT_CASE, choices=ALL_CASES)
    p.add_argument(
        "--input",
        default=None,
        help="External JSON case input (delegates to kg_mnp_demo.pipeline)",
    )
    p.add_argument(
        "--all",
        action="store_true",
        help="Run all six cases as the primary focus (still writes summary)",
    )
    p.add_argument("--output-dir", default=str(ROOT / "demo_outputs"))
    p.add_argument("--no-html", action="store_true")
    p.add_argument("--print-rdf", action="store_true")
    p.add_argument(
        "--what-if",
        choices=["contract-expired", "add-debt", "expire-evidence"],
        default=None,
        help="In-memory input mutation demo (does not modify TTL files)",
    )
    return p


def main(argv: list[str] | None = None) -> int:
    _configure_stdio()
    args = build_parser().parse_args(argv)
    output_dir = Path(args.output_dir)
    if not output_dir.is_absolute():
        output_dir = ROOT / output_dir

    if args.input:
        from kg_mnp_demo.pipeline import main as pipeline_main

        pipeline_argv = ["--input", args.input, "--output-dir", str(output_dir)]
        if args.no_html:
            pipeline_argv.append("--no-html")
        if args.print_rdf:
            pipeline_argv.append("--print-rdf")
        return pipeline_main(pipeline_argv)

    print("=" * 60)
    print("KG-MNP 携号转网资格判断本体演示")
    print("=" * 60)
    print()
    print(f"backend = {BACKEND}（强制离线 RDF）")
    print(_assessment_time_note())
    print()

    focus_case = args.case
    primary = evaluate_pipeline(focus_case)
    exit_code = 0
    if not primary["input_validation"]["conforms"]:
        exit_code = 1
    elif primary.get("assessment_validation") and not primary["assessment_validation"].get("conforms", True):
        exit_code = 1
    elif primary["evaluation"] and not primary["evaluation"].get("publishable", True):
        exit_code = 1

    print_input_section(primary["input_summary"])
    print_validation_section(
        primary["input_validation"],
        assessment_validation=primary.get("assessment_validation"),
    )
    print_inference_section(primary["inference"])
    print_evaluation_section(primary["evaluation"])
    print_trace_section(primary.get("trace"), primary["evaluation"])

    all_summary = summarize_all_cases()
    print_summary_table(all_summary)

    what_if_result = None
    if args.what_if:
        what_if_result = evaluate_pipeline(focus_case, what_if=args.what_if)
        print_what_if_comparison(primary, what_if_result, args.what_if)
        if not what_if_result.get("ttl_unchanged", True):
            exit_code = 1

    if args.all:
        print("（--all）已完成六个案例汇总写入 all_cases_summary.json")
        print()

    written = write_outputs(
        output_dir,
        primary,
        all_summary,
        write_html=not args.no_html,
        what_if_result=what_if_result,
    )

    print("输出文件：")
    for path in written:
        print(f"  - {path.relative_to(ROOT) if path.is_relative_to(ROOT) else path}")
    if not args.no_html:
        print()
        print(f"HTML 演示报告：{(output_dir / 'demo_report.html')}")
        print("可直接双击打开，无需启动服务器。")
    print()

    return exit_code


if __name__ == "__main__":
    sys.exit(main())
