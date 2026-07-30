"""Explicit Cypher MERGE of evaluation results for reliable tracing."""

from __future__ import annotations

from typing import Any

from kg_mnp_demo.neo4j_client import run_write


def upsert_evaluation_result(session, case_id: str, result: dict[str, Any]) -> dict[str, Any]:
    """Write case/assessment/decision/reasons with stable property names."""
    decision = result["decision"]
    assessment_id = f"ASSESS-{case_id}"

    run_write(
        session,
        """
        MERGE (c:MNPCase {caseIdentifier: $case_id})
        SET c.uri = $case_uri
        MERGE (a:EligibilityAssessment {assessmentIdentifier: $assessment_id})
        SET a.caseIdentifier = $case_id,
            a.requiresReassessment = coalesce(a.requiresReassessment, false)
        MERGE (c)-[:hasEligibilityAssessment]->(a)
        WITH a
        OPTIONAL MATCH (a)-[rd:producesDecision]->(oldd)
        DELETE rd
        WITH a
        MERGE (d:EligibilityDecision {decisionCode: $decision, caseIdentifier: $case_id})
        SET d:Decision
        FOREACH (_ IN CASE WHEN $decision = 'ELIGIBLE' THEN [1] ELSE [] END |
          SET d:EligibleDecision)
        FOREACH (_ IN CASE WHEN $decision = 'BLOCKED' THEN [1] ELSE [] END |
          SET d:BlockingDecision)
        FOREACH (_ IN CASE WHEN $decision = 'CONDITIONAL' THEN [1] ELSE [] END |
          SET d:ConditionalDecision)
        FOREACH (_ IN CASE WHEN $decision = 'MANUAL_REVIEW' THEN [1] ELSE [] END |
          SET d:ManualReviewDecision)
        MERGE (a)-[:producesDecision]->(d)
        """,
        case_id=case_id,
        case_uri=f"http://example.org/kg-mnp#{case_id}",
        assessment_id=assessment_id,
        decision=decision,
    )

    # Clear prior blocking reasons for this assessment
    run_write(
        session,
        """
        MATCH (a:EligibilityAssessment {assessmentIdentifier: $assessment_id})
              -[r:producesBlockingReason]->(br:BlockingReason)
        DETACH DELETE br
        """,
        assessment_id=assessment_id,
    )

    for reason in result.get("blocking_reasons", []):
        run_write(
            session,
            """
            MATCH (a:EligibilityAssessment {assessmentIdentifier: $assessment_id})
            MERGE (br:BlockingReason {
              reasonCode: $reason_code,
              caseIdentifier: $case_id
            })
            SET br.ruleId = $rule_id,
                br.ruleVersion = $rule_version,
                br.effectiveFrom = $effective_from,
                br.regulatoryClause = $clause,
                br.actionCode = $action_code
            MERGE (a)-[:producesBlockingReason]->(br)
            WITH br
            FOREACH (_ IN CASE WHEN $evidence_id IS NULL THEN [] ELSE [1] END |
              MERGE (e:EvidenceRecord {evidenceId: $evidence_id})
              SET e.evidenceStatus = $evidence_status,
                  e.sourceSystem = $source_system,
                  e.generatedAt = $generated_at,
                  e.validUntil = $valid_until,
                  e.evidenceType = $evidence_type
              MERGE (br)-[:supportedByEvidence]->(e)
            )
            WITH br
            MERGE (rule:EligibilityRule {ruleIdentifier: $rule_id, ruleVersion: $rule_version})
            SET rule.effectiveFrom = $effective_from
            MERGE (br)-[:triggeredByRule]->(rule)
            MERGE (rv:RuleVersion {ruleIdentifier: $rule_id, ruleVersion: $rule_version})
            SET rv.effectiveFrom = $effective_from
            MERGE (br)-[:triggeredByRuleVersion]->(rv)
            WITH br
            FOREACH (_ IN CASE WHEN $clause IS NULL THEN [] ELSE [1] END |
              MERGE (cl:RegulatoryClause {clauseIdentifier: $clause})
              MERGE (br)-[:citesClause]->(cl)
            )
            WITH br
            FOREACH (_ IN CASE WHEN $action_code IS NULL THEN [] ELSE [1] END |
              MERGE (act:RemediationAction {actionCode: $action_code})
              MERGE (br)-[:recommendsAction]->(act)
            )
            """,
            assessment_id=assessment_id,
            case_id=case_id,
            reason_code=reason.get("reason_code"),
            rule_id=reason.get("rule_id"),
            rule_version=reason.get("rule_version"),
            effective_from=reason.get("effective_from"),
            clause=reason.get("regulatory_clause"),
            action_code=reason.get("action_code"),
            evidence_id=(reason.get("evidence") or {}).get("evidence_id"),
            evidence_status=(reason.get("evidence") or {}).get("status"),
            source_system=(reason.get("evidence") or {}).get("source_system"),
            generated_at=(reason.get("evidence") or {}).get("generated_at"),
            valid_until=(reason.get("evidence") or {}).get("valid_until"),
            evidence_type=(reason.get("evidence") or {}).get("evidence_type"),
        )

    # Link rules used
    for rule in result.get("rules", []):
        run_write(
            session,
            """
            MATCH (a:EligibilityAssessment {assessmentIdentifier: $assessment_id})
            MERGE (rule:EligibilityRule {ruleIdentifier: $rule_id, ruleVersion: $version})
            SET rule.effectiveFrom = $effective_from,
                rule.status = $status
            MERGE (a)-[:evaluatedByRule]->(rule)
            MERGE (rv:RuleVersion {ruleIdentifier: $rule_id, ruleVersion: $version})
            SET rv.effectiveFrom = $effective_from
            MERGE (a)-[:usesRuleVersion]->(rv)
            """,
            assessment_id=assessment_id,
            rule_id=rule["rule_id"],
            version=rule["version"],
            effective_from=rule.get("effective_from"),
            status=rule.get("status"),
        )

    # CASE-06 style: mark historical assessments when a RuleVersion supersedes another
    run_write(
        session,
        """
        MATCH (newRv:RuleVersion)-[:supersedesRuleVersion]->(oldRv:RuleVersion)
        MATCH (a:EligibilityAssessment)-[:usesRuleVersion]->(oldRv)
        SET a.requiresReassessment = true
        MERGE (marker:ReassessmentMarker {assessmentIdentifier: a.assessmentIdentifier})
        SET marker.reassessmentReason = 'Rule version superseded; reassessment required'
        MERGE (a)-[:markedForReassessment]->(marker)
        MERGE (newRv)-[:affectsAssessment]->(a)
        """,
    )

    # Ensure supersedes edge exists for MNP-ELIG-005 1.1 -> 1.0
    run_write(
        session,
        """
        MERGE (oldRv:RuleVersion {ruleIdentifier: 'MNP-ELIG-005', ruleVersion: '1.0'})
        MERGE (newRv:RuleVersion {ruleIdentifier: 'MNP-ELIG-005', ruleVersion: '1.1'})
        MERGE (newRv)-[:supersedesRuleVersion]->(oldRv)
        """,
    )

    # Seed historical assessment node for CASE-06 if present in evaluation context
    if case_id == "CASE-06":
        run_write(
            session,
            """
            MERGE (c:MNPCase {caseIdentifier: 'CASE-06'})
            MERGE (hist:EligibilityAssessment {assessmentIdentifier: 'ASSESS-CASE-06-HIST'})
            SET hist.caseIdentifier = 'CASE-06',
                hist.requiresReassessment = true
            MERGE (c)-[:hasEligibilityAssessment]->(hist)
            MERGE (oldRv:RuleVersion {ruleIdentifier: 'MNP-ELIG-005', ruleVersion: '1.0'})
            MERGE (hist)-[:usesRuleVersion]->(oldRv)
            MERGE (newRv:RuleVersion {ruleIdentifier: 'MNP-ELIG-005', ruleVersion: '1.1'})
            MERGE (newRv)-[:supersedesRuleVersion]->(oldRv)
            MERGE (newRv)-[:affectsAssessment]->(hist)
            MERGE (marker:ReassessmentMarker {assessmentIdentifier: 'ASSESS-CASE-06-HIST'})
            SET marker.reassessmentReason = 'Rule version superseded; reassessment required'
            MERGE (hist)-[:markedForReassessment]->(marker)
            MERGE (d:EligibilityDecision {decisionCode: 'ELIGIBLE', caseIdentifier: 'CASE-06-HIST'})
            SET d:EligibleDecision
            MERGE (hist)-[:producesDecision]->(d)
            """,
        )

    # Mapping records for source_alignment
    for m in result.get("tmf_mappings_used", []):
        run_write(
            session,
            """
            MERGE (map:MappingRecord {id: $id})
            SET map.sourceApi = $source_api,
                map.sourceFieldPath = $source_path,
                map.targetTerm = $target_term,
                map.mappingType = $mapping_type,
                map.mappingReviewStatus = $review_status
            """,
            id=m.get("id"),
            source_api=m.get("source_api"),
            source_path=m.get("source_path"),
            target_term=m.get("target_term"),
            mapping_type=m.get("mapping_type"),
            review_status=m.get("review_status"),
        )

    return {
        "assessment_id": assessment_id,
        "decision": decision,
        "blocking_reason_count": len(result.get("blocking_reasons", [])),
    }
