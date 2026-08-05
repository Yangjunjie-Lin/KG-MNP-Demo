"""Generate competency question registry and SPARQL query files."""

from __future__ import annotations

from pathlib import Path

import yaml

ROOT = Path(__file__).resolve().parents[1]
CQ_DIR = ROOT / "competency_questions"
Q_DIR = CQ_DIR / "queries"
PREFIX = "PREFIX mnp: <https://yangjunjie-lin.github.io/KG-MNP-Demo/ontology/terms#>\n"

CQS = [
    ("CQ-01", "当前是否可携转", "What is the current eligibility decision?", "Returns the eligibility decision for a case.", ["decision"], "cq01_current_eligibility.rq", "CASE-01"),
    ("CQ-02", "阻塞原因", "If blocked, what are the blocking reasons?", "Lists independent blocking reason codes.", ["reasonCode"], "cq02_blocking_reasons.rq", "CASE-04"),
    ("CQ-03", "阻塞证据", "What evidence supports each blocking reason?", "Evidence linked to each blocking reason.", ["evidence", "evidenceStatus"], "cq03_blocking_evidence.rq", "CASE-04"),
    ("CQ-04", "证据来源和时间", "What are evidence sources and times?", "Source system and generation/validity times.", ["sourceSystem", "generatedAt"], "cq04_evidence_provenance.rq", "CASE-03"),
    ("CQ-05", "使用的规则版本", "Which rule versions were used?", "Rule versions selected for assessment_time.", ["ruleId", "ruleVersion"], "cq05_rule_versions.rq", "CASE-03"),
    ("CQ-06", "监管条款", "Which regulatory clauses were cited?", "Demo clause identifiers cited by blocking reasons.", ["clauseId"], "cq06_regulatory_clauses.rq", "CASE-03"),
    ("CQ-07", "解除动作", "What remediation actions are recommended?", "Recommended remediation action codes.", ["actionCode"], "cq07_remediation_actions.rq", "CASE-03"),
    ("CQ-08", "当前流程步骤", "What is the current process step?", "Current process step code if present.", ["stepCode"], "cq08_current_process_step.rq", "CASE-07"),
    ("CQ-09", "不能进入下一步的原因", "Why can the process not advance?", "Process events related to blocked transitions.", ["eventTypeCode"], "cq09_process_blocks.rq", "CASE-07"),
    ("CQ-10", "授权码是否有效", "Is the authorization code valid?", "Authorization code status and validity window.", ["authStatus", "validUntil"], "cq10_auth_code_validity.rq", "CASE-07"),
    ("CQ-11", "关联业务", "What services are related to the case?", "Related telecom services/subscriptions.", ["service"], "cq11_related_services.rq", "CASE-01"),
    ("CQ-12", "影响携转的合约", "Which contracts affect portability?", "Contract status and end times.", ["contractStatus"], "cq12_affecting_contracts.rq", "CASE-03"),
    ("CQ-13", "欠费证据是否过期", "Is billing evidence expired?", "Billing evidence validity window.", ["validUntil"], "cq13_billing_evidence_expiry.rq", "CASE-02"),
    ("CQ-14", "多阻塞如何分别处理", "How should multiple blocks be remediated separately?", "Each blocking reason with its own action.", ["reasonCode", "actionCode"], "cq14_multi_block_actions.rq", "CASE-04"),
    ("CQ-15", "规则更新影响哪些评估", "Which assessments are affected by rule updates?", "Assessments marked for reassessment.", ["assessment"], "cq15_affected_assessments.rq", "CASE-06"),
]

QUERIES = {
    "cq01_current_eligibility.rq": """
SELECT ?caseId ?decision WHERE {
  ?case a mnp:MNPCase ; mnp:caseIdentifier ?caseId ; mnp:hasEligibilityAssessment ?a .
  FILTER(STR(?caseId) = STR(?requestedCaseId))
  ?a mnp:producesDecision ?d . ?d mnp:decisionCode ?decision .
}
ORDER BY ?caseId
""",
    "cq02_blocking_reasons.rq": """
SELECT ?caseId ?reasonCode WHERE {
  ?case a mnp:MNPCase ; mnp:caseIdentifier ?caseId ; mnp:hasEligibilityAssessment ?a .
  FILTER(STR(?caseId) = STR(?requestedCaseId))
  ?a mnp:producesBlockingReason ?r . ?r mnp:reasonCode ?reasonCode .
}
ORDER BY ?reasonCode
""",
    "cq03_blocking_evidence.rq": """
SELECT ?caseId ?reasonCode ?evidence ?evidenceStatus WHERE {
  ?case a mnp:MNPCase ; mnp:caseIdentifier ?caseId ; mnp:hasEligibilityAssessment ?a .
  FILTER(STR(?caseId) = STR(?requestedCaseId))
  ?a mnp:producesBlockingReason ?r .
  ?r mnp:reasonCode ?reasonCode .
  OPTIONAL { ?r mnp:supportedByEvidence ?evidence . OPTIONAL { ?evidence mnp:evidenceStatus ?evidenceStatus } }
}
ORDER BY ?reasonCode
""",
    "cq04_evidence_provenance.rq": """
SELECT ?caseId ?evidence ?evidenceType ?sourceSystem ?generatedAt ?validUntil WHERE {
  ?case a mnp:MNPCase ; mnp:caseIdentifier ?caseId ; mnp:hasCaseEvidence ?evidence .
  FILTER(STR(?caseId) = STR(?requestedCaseId))
  OPTIONAL { ?evidence mnp:evidenceType ?evidenceType }
  OPTIONAL { ?evidence mnp:evidenceGeneratedAt ?generatedAt }
  OPTIONAL { ?evidence mnp:evidenceValidUntil ?validUntil }
  OPTIONAL { ?evidence mnp:hasSourceSystem ?sys . ?sys mnp:systemIdentifier ?sourceSystem }
}
ORDER BY ?evidenceType
""",
    "cq05_rule_versions.rq": """
SELECT ?caseId ?ruleId ?ruleVersion ?effectiveFrom WHERE {
  ?case a mnp:MNPCase ; mnp:caseIdentifier ?caseId ; mnp:hasEligibilityAssessment ?a .
  FILTER(STR(?caseId) = STR(?requestedCaseId))
  ?a mnp:usesRuleVersion ?rv .
  OPTIONAL { ?rv mnp:ruleIdentifier ?ruleId }
  OPTIONAL { ?rv mnp:ruleVersion ?ruleVersion }
  OPTIONAL { ?rv mnp:effectiveFrom ?effectiveFrom }
}
ORDER BY ?ruleId ?ruleVersion
""",
    "cq06_regulatory_clauses.rq": """
SELECT ?caseId ?reasonCode ?clauseId WHERE {
  ?case a mnp:MNPCase ; mnp:caseIdentifier ?caseId ; mnp:hasEligibilityAssessment ?a .
  FILTER(STR(?caseId) = STR(?requestedCaseId))
  ?a mnp:producesBlockingReason ?r .
  ?r mnp:reasonCode ?reasonCode ; mnp:citesClause ?c .
  ?c mnp:clauseIdentifier ?clauseId .
}
ORDER BY ?clauseId
""",
    "cq07_remediation_actions.rq": """
SELECT ?caseId ?reasonCode ?actionCode WHERE {
  ?case a mnp:MNPCase ; mnp:caseIdentifier ?caseId ; mnp:hasEligibilityAssessment ?a .
  FILTER(STR(?caseId) = STR(?requestedCaseId))
  ?a mnp:producesBlockingReason ?r .
  ?r mnp:reasonCode ?reasonCode ; mnp:recommendsAction ?act .
  ?act mnp:actionCode ?actionCode .
}
ORDER BY ?actionCode
""",
    "cq08_current_process_step.rq": """
SELECT ?caseId ?stepCode WHERE {
  ?case a mnp:MNPCase ; mnp:caseIdentifier ?caseId .
  FILTER(STR(?caseId) = STR(?requestedCaseId))
  OPTIONAL { ?case mnp:currentProcessStep ?step . ?step mnp:stepCode ?stepCode }
}
ORDER BY ?caseId
""",
    "cq09_process_blocks.rq": """
SELECT ?caseId ?eventTypeCode ?eventTime WHERE {
  ?case a mnp:MNPCase ; mnp:caseIdentifier ?caseId .
  FILTER(STR(?caseId) = STR(?requestedCaseId))
  OPTIONAL {
    ?case mnp:hasProcessEvent ?ev .
    ?ev mnp:eventTypeCode ?eventTypeCode ; mnp:eventTime ?eventTime .
  }
}
ORDER BY ?eventTime
""",
    "cq10_auth_code_validity.rq": """
SELECT ?caseId ?authStatus ?issuedAt ?validUntil WHERE {
  ?case a mnp:MNPCase ; mnp:caseIdentifier ?caseId .
  FILTER(STR(?caseId) = STR(?requestedCaseId))
  OPTIONAL {
    ?case mnp:hasAuthorizationCode ?code .
    OPTIONAL { ?code mnp:authCodeStatus ?authStatus }
    OPTIONAL { ?code mnp:authCodeIssuedAt ?issuedAt }
    OPTIONAL { ?code mnp:authCodeValidUntil ?validUntil }
  }
}
ORDER BY ?caseId
""",
    "cq11_related_services.rq": """
SELECT ?caseId ?service ?subscriptionStatus WHERE {
  ?case a mnp:MNPCase ; mnp:caseIdentifier ?caseId ; mnp:requestedBy ?sub .
  FILTER(STR(?caseId) = STR(?requestedCaseId))
  OPTIONAL {
    ?sub mnp:hasSubscription ?ss .
    ?ss mnp:subscribesToService ?service .
    OPTIONAL { ?ss mnp:subscriptionStatusCode ?subscriptionStatus }
  }
}
ORDER BY ?service
""",
    "cq12_affecting_contracts.rq": """
SELECT ?caseId ?contract ?contractStatus ?contractEnd WHERE {
  ?case a mnp:MNPCase ; mnp:caseIdentifier ?caseId ; mnp:requestedBy ?sub .
  FILTER(STR(?caseId) = STR(?requestedCaseId))
  OPTIONAL {
    ?sub mnp:hasSubscription ?ss .
    ?ss mnp:governedByContract ?contract .
    OPTIONAL { ?contract mnp:contractStatusCode ?contractStatus }
    OPTIONAL { ?contract mnp:contractEndTime ?contractEnd }
  }
}
ORDER BY ?contract
""",
    "cq13_billing_evidence_expiry.rq": """
SELECT ?caseId ?evidence ?evidenceStatus ?validUntil ?assessmentTime WHERE {
  ?case a mnp:MNPCase ; mnp:caseIdentifier ?caseId ; mnp:hasCaseEvidence ?evidence .
  FILTER(STR(?caseId) = STR(?requestedCaseId))
  ?evidence mnp:evidenceType "BILLING_BALANCE" .
  OPTIONAL { ?evidence mnp:evidenceStatus ?evidenceStatus }
  OPTIONAL { ?evidence mnp:evidenceValidUntil ?validUntil }
  OPTIONAL {
    ?case mnp:hasEligibilityAssessment ?a .
    ?a mnp:assessmentTime ?assessmentTime .
  }
}
ORDER BY ?evidence
""",
    "cq14_multi_block_actions.rq": """
SELECT ?caseId ?reasonCode ?actionCode ?clauseId WHERE {
  ?case a mnp:MNPCase ; mnp:caseIdentifier ?caseId ; mnp:hasEligibilityAssessment ?a .
  FILTER(STR(?caseId) = STR(?requestedCaseId))
  ?a mnp:producesBlockingReason ?r .
  ?r mnp:reasonCode ?reasonCode .
  OPTIONAL { ?r mnp:recommendsAction ?act . ?act mnp:actionCode ?actionCode }
  OPTIONAL { ?r mnp:citesClause ?c . ?c mnp:clauseIdentifier ?clauseId }
}
ORDER BY ?reasonCode
""",
    "cq15_affected_assessments.rq": """
SELECT ?assessment ?oldVersion ?newVersion WHERE {
  ?new mnp:supersedesRuleVersion ?old .
  ?assessment mnp:usesRuleVersion ?old .
  OPTIONAL { ?old mnp:ruleVersion ?oldVersion }
  OPTIONAL { ?new mnp:ruleVersion ?newVersion }
  OPTIONAL {
    ?case a mnp:MNPCase ; mnp:caseIdentifier ?caseId ; mnp:hasEligibilityAssessment ?assessment .
    FILTER(STR(?caseId) = STR(?requestedCaseId))
  }
}
ORDER BY ?assessment
""",
}


def main() -> None:
    CQ_DIR.mkdir(parents=True, exist_ok=True)
    Q_DIR.mkdir(parents=True, exist_ok=True)
    registry = {
        "competency_questions": [
            {
                "id": cid,
                "title_zh": title,
                "question": question,
                "description": desc,
                "required_inputs": ["case_id"],
                "return_fields": fields,
                "query_file": qf,
                "supported_backends": ["rdf"],
                "example_case": ex,
            }
            for cid, title, question, desc, fields, qf, ex in CQS
        ]
    }
    (CQ_DIR / "registry.yaml").write_text(
        yaml.dump(registry, allow_unicode=True, sort_keys=False),
        encoding="utf-8",
    )
    for name, body in QUERIES.items():
        (Q_DIR / name).write_text(PREFIX + body.strip() + "\n", encoding="utf-8")
    print(f"Wrote {len(QUERIES)} queries and registry")


if __name__ == "__main__":
    main()
