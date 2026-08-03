"""Presentation / view-model services for frontend pages."""

from __future__ import annotations

from typing import Any

from kg_mnp_demo.application.ontology_service import OntologyService
from kg_mnp_demo.application.query_service import QueryService
from kg_mnp_demo.application.serializers import json_safe
from kg_mnp_demo.loader import project_root, shapes_path
from kg_mnp_demo.namespaces import CASE_FILES, EXAMPLE_META
from kg_mnp_demo.rule_engine import load_all_rule_versions
from kg_mnp_demo.storage import AssessmentRepository


PIPELINE_STEPS = [
    {"id": "json_schema", "label": "JSON Schema", "description": "校验并规范化业务 JSON 输入"},
    {"id": "rdf_builder", "label": "RDF Builder", "description": "构建案件实例图"},
    {"id": "input_shacl", "label": "Input SHACL", "description": "验证输入图结构完整性"},
    {"id": "owlrl", "label": "OWL-RL", "description": "确定性类型与关系扩展"},
    {"id": "rule_engine", "label": "Rule Engine", "description": "确定性资格规则（金额/日期）"},
    {"id": "assessment_materialization", "label": "Assessment Materialization", "description": "物化评估、决定与阻塞原因"},
    {"id": "assessment_shacl", "label": "Assessment SHACL", "description": "验证评估结果图"},
    {"id": "sparql_trace", "label": "SPARQL Trace", "description": "查询真实 RDF 追溯子图"},
]


REASON_TEMPLATES = {
    "ACTIVE_CONTRACT_RESTRICTION": "合约在评估时点仍有效，因此规则 {rule_id} v{rule_version} 未通过。",
    "OUTSTANDING_BALANCE": "存在未结清欠费且无有效缴费安排，因此规则 {rule_id} v{rule_version} 未通过。",
    "PORTING_INTERVAL_TOO_SHORT": "距上次携转间隔不足，因此规则 {rule_id} v{rule_version} 未通过。",
    "MISSING_OR_EXPIRED_EVIDENCE": "关键证据缺失或过期，因此规则 {rule_id} v{rule_version} 需要人工复核。",
    "REAL_NAME_MISMATCH": "实名信息不一致，因此规则 {rule_id} v{rule_version} 未通过。",
    "NUMBER_STATUS_INVALID": "号码状态不可用，因此规则 {rule_id} v{rule_version} 未通过。",
}


def count_shacl_shapes(shapes_file=None) -> dict[str, int]:
    """Count NodeShape and PropertyShape resources from the formal SHACL file."""
    from rdflib import Graph, Namespace
    from rdflib.namespace import RDF

    SH = Namespace("http://www.w3.org/ns/shacl#")
    path = shapes_file or shapes_path()
    g = Graph()
    g.parse(path, format="turtle")
    node_shapes = set(g.subjects(RDF.type, SH.NodeShape))
    prop_typed = set(g.subjects(RDF.type, SH.PropertyShape))
    prop_inline = {o for _s, _p, o in g.triples((None, SH.property, None))}
    property_shapes = prop_typed | prop_inline
    all_shapes = node_shapes | property_shapes
    return {
        "shape_count": len(all_shapes),
        "node_shape_count": len(node_shapes),
        "property_shape_count": len(property_shapes),
    }


def _example_case_stats() -> dict[str, int]:
    stats = {"total": len(CASE_FILES), "eligible": 0, "blocked": 0, "manual_review": 0}
    for case_id, meta in EXAMPLE_META.items():
        if case_id not in CASE_FILES:
            continue
        d = meta.get("expected_decision")
        if d == "ELIGIBLE":
            stats["eligible"] += 1
        elif d == "BLOCKED":
            stats["blocked"] += 1
        elif d == "MANUAL_REVIEW":
            stats["manual_review"] += 1
    return stats


def _reason_text(reason: dict[str, Any]) -> str:
    code = reason.get("reason_code") or ""
    template = REASON_TEMPLATES.get(code, "规则 {rule_id} v{rule_version} 未通过：{reason_code}。")
    return template.format(
        rule_id=reason.get("rule_id"),
        rule_version=reason.get("rule_version"),
        reason_code=code,
    )


class DashboardView:
    def build(
        self,
        *,
        ontology: OntologyService,
        repository: AssessmentRepository | None = None,
    ) -> dict[str, Any]:
        summary = ontology.get_summary()
        rules = load_all_rule_versions()
        cq = QueryService().list_questions()
        shape_stats = count_shacl_shapes()
        example_cases = _example_case_stats()
        executions = {"total": 0, "eligible": 0, "blocked": 0, "manual_review": 0}
        latest_case_states = {"total": 0, "eligible": 0, "blocked": 0, "manual_review": 0}
        if repository is not None:
            executions = {
                k: repository.count_by_decision().get(k, 0)
                for k in ("total", "eligible", "blocked", "manual_review")
            }
            latest_case_states = {
                k: repository.latest_case_decision_counts().get(k, 0)
                for k in ("total", "eligible", "blocked", "manual_review")
            }
        return json_safe(
            {
                "project": {
                    "name": "KG-MNP Demo",
                    "description": "携号转网资格判断本体演示：确定性规则 + OWL/SHACL/SPARQL。",
                    "root_name": project_root().name,
                },
                "capabilities": [
                    "deterministic_eligibility",
                    "ontology_modules",
                    "competency_questions",
                    "what_if",
                    "assessment_history",
                    "process_authorization_code",
                ],
                "ontology": {
                    "module_count": summary.get("module_count"),
                    "class_count": summary.get("class_count"),
                    "object_property_count": summary.get("object_property_count"),
                    "data_property_count": summary.get("data_property_count"),
                    "shape_count": shape_stats["shape_count"],
                    "node_shape_count": shape_stats["node_shape_count"],
                    "property_shape_count": shape_stats["property_shape_count"],
                    "rule_count": len(rules),
                    "competency_question_count": len(cq),
                },
                "example_cases": example_cases,
                "executions": executions,
                "latest_case_states": latest_case_states,
                # Backward-compatible alias: fixed example inventory only
                "cases": example_cases,
                "pipeline_steps": PIPELINE_STEPS,
                "example_case_ids": sorted(CASE_FILES.keys()),
            }
        )


class AssessmentView:
    def build(self, record_or_result: dict[str, Any]) -> dict[str, Any]:
        result = record_or_result.get("result") or record_or_result
        reasons = result.get("blocking_reasons") or []
        cards = []
        for r in reasons:
            cards.append(
                {
                    "reason": r.get("reason_code"),
                    "reason_text": _reason_text(r),
                    "evidence": r.get("evidence"),
                    "rule": r.get("rule_id"),
                    "rule_version": r.get("rule_version"),
                    "clause": r.get("regulatory_clause"),
                    "action": r.get("action_code"),
                }
            )
        validations = result.get("validations") or {}
        validation_steps = [
            {"id": "json_schema", **(validations.get("json_schema") or {})},
            {"id": "input_graph", **(validations.get("input_graph") or {})},
            {"id": "assessment_graph", **(validations.get("assessment_graph") or {})},
        ]
        return json_safe(
            {
                "header": {
                    "execution_id": result.get("execution_id"),
                    "case_id": result.get("case_id"),
                    "assessment_time": result.get("assessment_time"),
                },
                "decision_card": {
                    "decision": result.get("decision"),
                    "publication": result.get("publication"),
                },
                "input_summary": result.get("input_summary") or {},
                "validation_steps": validation_steps,
                "evidence_table": result.get("evidence") or [],
                "rule_execution_table": result.get("rule_results") or [],
                "blocking_reason_cards": cards,
                "remediation_actions": result.get("remediation_actions") or [],
                "process_status": result.get("process") or {},
                "trace_graph": result.get("trace_subgraph") or {"nodes": [], "edges": []},
                "timeline": self._timeline(result),
                "artifacts": [
                    {"name": k, "file": v}
                    for k, v in sorted((result.get("artifacts") or {}).items())
                ],
                "technical_details": {
                    "schema_version": result.get("schema_version"),
                    "inference": result.get("inference") or {},
                    "warnings": result.get("warnings") or [],
                },
            }
        )

    def _timeline(self, result: dict[str, Any]) -> list[dict[str, Any]]:
        steps = []
        for s in PIPELINE_STEPS:
            status = "DONE"
            if s["id"] == "input_shacl":
                status = (result.get("validations") or {}).get("input_graph", {}).get("status", "DONE")
            if s["id"] == "assessment_shacl":
                status = (result.get("validations") or {}).get("assessment_graph", {}).get("status", "DONE")
            steps.append({"id": s["id"], "label": s["label"], "status": status})
        return steps


class OntologyView:
    KEY_PATHS = {
        "case-to-decision": ("MNPCase", "hasEligibilityAssessment", "EligibilityAssessment"),
        "reason-to-remediation": ("BlockingReason", "recommendsAction", "RemediationAction"),
        "rule-to-regulation": ("EligibilityRule", "operationalizesClause", "RegulatoryClause"),
        "assessment-to-evidence": ("EligibilityAssessment", "usesEvidence", "EvidenceRecord"),
    }

    def build(self, ontology: OntologyService) -> dict[str, Any]:
        modules = ontology.list_modules()
        graph = ontology.build_ontology_graph()
        props = {p["local_name"]: p for p in ontology.list_object_properties()}
        key_paths = []
        for path_id, (src, pred, tgt) in self.KEY_PATHS.items():
            prop = props.get(pred)
            exists = prop is not None and src in (prop.get("domain") or []) and tgt in (prop.get("range") or [])
            if exists:
                key_paths.append(
                    {
                        "id": path_id,
                        "source_class": src,
                        "predicate": pred,
                        "target_class": tgt,
                        "exists_in_rdf": True,
                    }
                )
        return json_safe(
            {
                "modules": modules,
                "graph": graph,
                "key_paths": key_paths,
                "stats": ontology.get_summary(),
            }
        )


class ComparisonView:
    def build(self, what_if_result: dict[str, Any]) -> dict[str, Any]:
        from kg_mnp_demo.application.comparison import build_what_if_diff

        baseline = what_if_result.get("baseline") or {}
        scenario = what_if_result.get("scenario") or {}
        # Prefer precomputed fields when present
        if what_if_result.get("rule_changes") is not None and what_if_result.get(
            "evidence_changes"
        ) is not None:
            return json_safe(what_if_result)
        return build_what_if_diff(
            baseline, scenario, changes=what_if_result.get("changes")
        )


class TraceView:
    def build(self, result: dict[str, Any]) -> dict[str, Any]:
        trace = result.get("trace_subgraph") or {"nodes": [], "edges": []}
        return json_safe(
            {
                "case_id": result.get("case_id"),
                "execution_id": result.get("execution_id"),
                "graph": trace,
                "node_count": len(trace.get("nodes") or []),
                "edge_count": len(trace.get("edges") or []),
            }
        )


class CaseView:
    def build(self, case_payload: dict[str, Any], latest: dict[str, Any] | None = None) -> dict[str, Any]:
        return json_safe(
            {
                "case": case_payload,
                "latest_assessment": AssessmentView().build(latest) if latest else None,
            }
        )


class RuleView:
    def build(self) -> dict[str, Any]:
        rules = load_all_rule_versions()
        return json_safe(
            {
                "items": sorted(
                    rules,
                    key=lambda r: (r.get("rule_id") or "", r.get("version") or ""),
                )
            }
        )
