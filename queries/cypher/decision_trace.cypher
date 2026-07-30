// Decision trace for a case
// Parameter: $case_id

MATCH (c:MNPCase {caseIdentifier: $case_id})
      -[:hasEligibilityAssessment]->(a:EligibilityAssessment)
      -[:producesDecision]->(d)
OPTIONAL MATCH (a)-[:producesBlockingReason]->(br:BlockingReason)
OPTIONAL MATCH (br)-[:supportedByEvidence]->(e)
OPTIONAL MATCH (br)-[:triggeredByRule]->(rule)
OPTIONAL MATCH (br)-[:triggeredByRuleVersion]->(rv)
OPTIONAL MATCH (br)-[:citesClause]->(cl)
OPTIONAL MATCH (br)-[:recommendsAction]->(act)
RETURN c.caseIdentifier AS caseId,
       a.assessmentIdentifier AS assessment,
       e.evidenceId AS evidence,
       e.evidenceStatus AS evidenceStatus,
       e.sourceSystem AS sourceSystem,
       coalesce(br.ruleId, rule.ruleIdentifier) AS ruleId,
       coalesce(br.ruleVersion, rv.ruleVersion) AS ruleVersion,
       coalesce(br.effectiveFrom, rv.effectiveFrom, rule.effectiveFrom) AS effectiveFrom,
       coalesce(br.regulatoryClause, cl.clauseIdentifier) AS clauseId,
       d.decisionCode AS decisionCode,
       br.reasonCode AS reasonCode,
       coalesce(br.actionCode, act.actionCode) AS actionCode
ORDER BY reasonCode, ruleId
