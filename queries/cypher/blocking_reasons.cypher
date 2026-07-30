// Independent blocking reasons for a case
// Parameter: $case_id

MATCH (c:MNPCase {caseIdentifier: $case_id})
      -[:hasEligibilityAssessment]->(a:EligibilityAssessment)
WHERE a.assessmentIdentifier = 'ASSESS-' + $case_id
MATCH (a)-[:producesBlockingReason]->(br:BlockingReason)
OPTIONAL MATCH (br)-[:supportedByEvidence]->(e)
OPTIONAL MATCH (br)-[:triggeredByRule]->(rule)
OPTIONAL MATCH (br)-[:triggeredByRuleVersion]->(rv)
OPTIONAL MATCH (br)-[:citesClause]->(cl)
OPTIONAL MATCH (br)-[:recommendsAction]->(act)
RETURN c.caseIdentifier AS caseId,
       br.reasonCode AS reasonCode,
       e.evidenceId AS evidence,
       e.evidenceStatus AS evidenceStatus,
       e.sourceSystem AS sourceSystem,
       e.generatedAt AS generatedAt,
       coalesce(br.ruleId, rule.ruleIdentifier) AS ruleId,
       coalesce(br.ruleVersion, rv.ruleVersion) AS ruleVersion,
       coalesce(br.effectiveFrom, rv.effectiveFrom) AS effectiveFrom,
       coalesce(br.regulatoryClause, cl.clauseIdentifier) AS clauseId,
       cl.clauseText AS clauseText,
       coalesce(br.actionCode, act.actionCode) AS actionCode,
       act.actionDescription AS actionDescription
ORDER BY reasonCode
