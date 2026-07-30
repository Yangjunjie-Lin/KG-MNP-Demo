// Assessments affected by superseded rule versions

MATCH (newRv:RuleVersion)-[:supersedesRuleVersion]->(oldRv:RuleVersion)
OPTIONAL MATCH (newRv)-[:affectsAssessment]->(a1:EligibilityAssessment)
OPTIONAL MATCH (a2:EligibilityAssessment)-[:usesRuleVersion]->(oldRv)
WITH newRv, oldRv, collect(DISTINCT a1) + collect(DISTINCT a2) AS assessments
UNWIND assessments AS assessment
WITH DISTINCT newRv, oldRv, assessment
WHERE assessment IS NOT NULL
OPTIONAL MATCH (assessment)<-[:hasEligibilityAssessment]-(c:MNPCase)
RETURN assessment.assessmentIdentifier AS assessmentId,
       oldRv.ruleVersion AS oldVersion,
       newRv.ruleVersion AS newVersion,
       c.caseIdentifier AS caseId,
       assessment.requiresReassessment AS requiresReassessment
ORDER BY assessmentId
