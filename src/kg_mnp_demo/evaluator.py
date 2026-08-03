"""Build assessment graphs and JSON evaluation results."""

from __future__ import annotations

from datetime import datetime
from typing import Any

from rdflib import Graph, Literal, URIRef
from rdflib.namespace import RDF, XSD

from kg_mnp_demo.mappings import mappings_used_for_case
from kg_mnp_demo.namespaces import MNP
from kg_mnp_demo.rule_engine import (
    ASSESSMENT_TIME,
    action_iri,
    clause_iri,
    evaluate_rules,
    resolve_case_uri,
    rule_iri,
    rule_version_iri,
    summarize_decision,
)
from kg_mnp_demo.validator import validate_graph


DECISION_CLASS = {
    "ELIGIBLE": MNP.EligibleDecision,
    "BLOCKED": MNP.BlockingDecision,
    "CONDITIONAL": MNP.ConditionalDecision,
    "MANUAL_REVIEW": MNP.ManualReviewDecision,
}


def _evidence_snapshot(graph: Graph, evidence_iri: str | None) -> dict[str, Any] | None:
    if not evidence_iri:
        return None
    q = """
    PREFIX mnp: <http://example.org/kg-mnp#>
    SELECT ?status ?gen ?until ?sysId ?type ?amount ?contractStatus
           ?contractEnd ?days ?numberStatus ?matched ?arrangement
    WHERE {
      BIND(%s AS ?ev)
      ?ev mnp:evidenceStatus ?status ;
          mnp:evidenceGeneratedAt ?gen ;
          mnp:hasSourceSystem ?sys .
      OPTIONAL { ?ev mnp:evidenceValidUntil ?until }
      OPTIONAL { ?ev mnp:evidenceType ?type }
      OPTIONAL { ?sys mnp:systemIdentifier ?sysId }
      OPTIONAL { ?ev mnp:observedAmount ?amount }
      OPTIONAL { ?ev mnp:contractStatusCode ?contractStatus }
      OPTIONAL { ?ev mnp:contractEndTime ?contractEnd }
      OPTIONAL { ?ev mnp:daysSinceLastPort ?days }
      OPTIONAL { ?ev mnp:numberStatusCode ?numberStatus }
      OPTIONAL { ?ev mnp:identityMatchFlag ?matched }
      OPTIONAL { ?ev mnp:hasPaymentArrangement ?arrangement }
    }
    """ % f"<{evidence_iri}>"
    for row in graph.query(q):
        snap: dict[str, Any] = {
            "evidence_id": evidence_iri.rsplit("#", 1)[-1],
            "evidence_iri": evidence_iri,
            "evidence_type": str(row.type) if row.type else None,
            "source_system": str(row.sysId) if row.sysId else None,
            "generated_at": str(row.gen),
            "valid_until": str(row.until) if row.until else None,
            "status": str(row.status),
        }
        if row.amount is not None:
            amount = str(row.amount)
            snap["outstanding_amount"] = amount
            snap["observed_amount"] = amount
        if row.contractStatus is not None:
            snap["contract_status"] = str(row.contractStatus)
            snap["contract_status_code"] = str(row.contractStatus)
        if row.contractEnd is not None:
            snap["contract_end_time"] = str(row.contractEnd)
        if row.days is not None:
            snap["days_since_last_port"] = int(row.days)
        if row.numberStatus is not None:
            snap["status_code"] = str(row.numberStatus)
            snap["number_status_code"] = str(row.numberStatus)
        if row.matched is not None:
            snap["matched"] = bool(row.matched)
            snap["identity_match_flag"] = bool(row.matched)
        if row.arrangement is not None:
            snap["has_payment_arrangement"] = bool(row.arrangement)
        return snap
    return {
        "evidence_id": evidence_iri.rsplit("#", 1)[-1],
        "evidence_iri": evidence_iri,
    }


def materialize_assessment(
    graph: Graph,
    case_id: str,
    *,
    use_updated_rules: bool | None = True,
    assessment_time: datetime | None = None,
    validate: bool = True,
    rule_version_overrides: dict[str, str] | None = None,
) -> tuple[Graph, dict[str, Any]]:
    as_of = assessment_time or ASSESSMENT_TIME
    outcomes = evaluate_rules(
        graph,
        case_id,
        use_updated_rules=use_updated_rules,
        assessment_time=as_of,
        rule_version_overrides=rule_version_overrides,
    )
    decision = summarize_decision(outcomes)

    assessment = MNP[f"Assessment-{case_id}"]
    decision_node = MNP[f"Decision-{case_id}"]
    dependency = MNP[f"Dep-{case_id}"]
    case_uri = resolve_case_uri(graph, case_id) or MNP[case_id]
    assessment_time_str = as_of.strftime("%Y-%m-%dT%H:%M:%SZ")

    graph.add((assessment, RDF.type, MNP.EligibilityAssessment))
    graph.add((assessment, MNP.assessmentIdentifier, Literal(f"ASSESS-{case_id}")))
    graph.add(
        (
            assessment,
            MNP.assessmentTime,
            Literal(assessment_time_str, datatype=XSD.dateTime),
        )
    )
    graph.add((assessment, MNP.aboutCase, case_uri))
    graph.add((case_uri, MNP.hasEligibilityAssessment, assessment))
    graph.add((assessment, MNP.dependsOn, dependency))
    graph.add((dependency, RDF.type, MNP.AssessmentDependency))

    graph.add((decision_node, RDF.type, DECISION_CLASS[decision]))
    graph.add((decision_node, MNP.decisionCode, Literal(decision)))
    graph.add((assessment, MNP.producesDecision, decision_node))

    blocking_reasons: list[dict[str, Any]] = []
    evidence_list: list[dict[str, Any]] = []
    rules_list: list[dict[str, Any]] = []
    clauses: list[dict[str, Any]] = []
    actions: list[dict[str, Any]] = []
    trace_paths: list[dict[str, Any]] = []

    seen_evidence: set[str] = set()

    for outcome in outcomes:
        r_uri = rule_iri(outcome.rule_id, outcome.version)
        rv_uri = rule_version_iri(outcome.rule_id, outcome.version)
        graph.add((assessment, MNP.evaluatedByRule, r_uri))
        graph.add((assessment, MNP.usesRuleVersion, rv_uri))
        graph.add((dependency, MNP.dependsOnRuleVersion, rv_uri))

        rules_list.append(
            {
                "rule_id": outcome.rule_id,
                "version": outcome.version,
                "effective_from": outcome.effective_from,
                "effective_to": outcome.effective_to,
                "selected_for_assessment_time": outcome.selected_for_assessment_time
                or assessment_time_str,
                "status": outcome.status,
            }
        )

        if outcome.evidence_iri:
            graph.add((assessment, MNP.usesEvidence, URIRef(outcome.evidence_iri)))
            graph.add((dependency, MNP.dependsOnEvidence, URIRef(outcome.evidence_iri)))
            if outcome.evidence_iri not in seen_evidence:
                snap = _evidence_snapshot(graph, outcome.evidence_iri)
                if snap:
                    evidence_list.append(snap)
                seen_evidence.add(outcome.evidence_iri)

        if outcome.status in ("FAIL", "MISSING"):
            reason = MNP[f"Reason-{case_id}-{outcome.reason_code}"]
            graph.add((reason, RDF.type, MNP.BlockingReason))
            graph.add((reason, MNP.reasonCode, Literal(outcome.reason_code)))
            graph.add((reason, MNP.reasonDescription, Literal(outcome.message)))
            graph.add((assessment, MNP.producesBlockingReason, reason))
            if outcome.evidence_iri:
                graph.add((reason, MNP.supportedByEvidence, URIRef(outcome.evidence_iri)))
            graph.add((reason, MNP.triggeredByRule, r_uri))
            graph.add((reason, MNP.triggeredByRuleVersion, rv_uri))
            if outcome.regulatory_clause:
                c_uri = clause_iri(outcome.regulatory_clause)
                graph.add((reason, MNP.citesClause, c_uri))
                clauses.append(
                    {
                        "clause_id": outcome.regulatory_clause,
                        "iri": str(c_uri),
                    }
                )
            if outcome.action_code:
                a_uri = action_iri(outcome.action_code)
                graph.add((reason, MNP.recommendsAction, a_uri))
                actions.append(
                    {
                        "action_code": outcome.action_code,
                        "iri": str(a_uri),
                    }
                )

            reason_payload = {
                "reason_code": outcome.reason_code,
                "rule_id": outcome.rule_id,
                "rule_version": outcome.version,
                "effective_from": outcome.effective_from,
                "effective_to": outcome.effective_to,
                "assessment_time": outcome.selected_for_assessment_time
                or assessment_time_str,
                "regulatory_clause": outcome.regulatory_clause,
                "action_code": outcome.action_code,
                "evidence": _evidence_snapshot(graph, outcome.evidence_iri),
            }
            blocking_reasons.append(reason_payload)
            trace_paths.append(
                {
                    "case": case_id,
                    "assessment": str(assessment),
                    "evidence": outcome.evidence_iri,
                    "rule": outcome.rule_id,
                    "rule_version": outcome.version,
                    "clause": outcome.regulatory_clause,
                    "decision": decision,
                    "action": outcome.action_code,
                    "reason": outcome.reason_code,
                }
            )

    if case_id == "CASE-06":
        _mark_reassessments(graph)

    if decision == "ELIGIBLE":
        for outcome in outcomes:
            trace_paths.append(
                {
                    "case": case_id,
                    "assessment": str(assessment),
                    "evidence": outcome.evidence_iri,
                    "rule": outcome.rule_id,
                    "rule_version": outcome.version,
                    "clause": outcome.regulatory_clause,
                    "decision": decision,
                    "action": None,
                    "reason": None,
                }
            )

    validation = validate_graph(graph) if validate else None
    result = {
        "case_id": case_id,
        "decision": decision,
        "blocking_reasons": blocking_reasons,
        "evidence": evidence_list,
        "rules": rules_list,
        "regulatory_clauses": clauses,
        "remediation_actions": actions,
        "trace_paths": trace_paths,
        "assessment_time": assessment_time_str,
        "validation_status": (
            ("PASSED" if validation.conforms else "FAILED") if validation else None
        ),
        "validation_detail": (
            (validation.text if validation and not validation.conforms else "")
            if validation
            else ""
        ),
        "declared_tmf_mappings": mappings_used_for_case(),
        "ontology_sources": [
            {
                "name": "Point-Topic/cto-ontology",
                "reuse_mode": "conceptual_reference",
                "runtime_dependency": False,
            },
            {
                "name": "tmforum-apis",
                "reuse_mode": "schema_mapping",
                "runtime_dependency": False,
            },
        ],
    }
    return graph, result


def _mark_reassessments(graph: Graph) -> None:
    q = """
    PREFIX mnp: <http://example.org/kg-mnp#>
    SELECT ?assessment ?old ?new WHERE {
      ?new mnp:supersedesRuleVersion ?old .
      ?assessment mnp:usesRuleVersion ?old .
    }
    """
    for row in graph.query(q):
        marker = MNP[f"Reassess-{row.assessment.rsplit('#', 1)[-1]}"]
        graph.add((marker, RDF.type, MNP.ReassessmentMarker))
        graph.add(
            (
                marker,
                MNP.reassessmentReason,
                Literal("Rule version superseded; reassessment required"),
            )
        )
        graph.add((row.assessment, MNP.markedForReassessment, marker))
        graph.set((row.assessment, MNP.requiresReassessment, Literal(True)))
        graph.add((row.new, MNP.affectsAssessment, row.assessment))


def evaluate_case(
    graph: Graph,
    case_id: str,
    *,
    use_updated_rules: bool | None = True,
    assessment_time: datetime | None = None,
    validate: bool = True,
    rule_version_overrides: dict[str, str] | None = None,
) -> dict[str, Any]:
    _, result = materialize_assessment(
        graph,
        case_id,
        use_updated_rules=use_updated_rules,
        assessment_time=assessment_time,
        validate=validate,
        rule_version_overrides=rule_version_overrides,
    )
    return result
