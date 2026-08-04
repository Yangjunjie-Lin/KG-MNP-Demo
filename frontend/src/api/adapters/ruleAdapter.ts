import type { EligibilityRule, RuleInputSpec } from "../../app/types/rules";
import { array, number, record, text } from "./guards";

const checkDescriptions: Record<string, string> = {
  "MNP-ELIG-001": "核验实名信息是否一致",
  "MNP-ELIG-002": "核验号码状态是否正常",
  "MNP-ELIG-003": "核验是否存在未结费用",
  "MNP-ELIG-004": "核验是否存在有效合约限制",
  "MNP-ELIG-005": "核验携转间隔是否满足当前版本要求",
};

export function adaptRules(dto: unknown): EligibilityRule[] {
  return array(record(dto).items).map((raw) => {
    const item = record(raw);
    const inputs = array(item.inputs).map((inputRaw) => {
      const input = record(inputRaw);
      return {
        evidenceType: text(input.evidence_type),
        required: input.required !== false,
        fields: array(input.fields).map((field) => text(field)).filter(Boolean),
      } satisfies RuleInputSpec;
    });
    const check = record(item.check);
    const ruleId = text(item.rule_id);
    return {
      ruleId,
      version: text(item.version),
      name: checkDescriptions[ruleId] ?? "资格判断规则",
      effectiveFrom: text(item.effective_from),
      effectiveTo: text(item.effective_to) || null,
      reasonCode: text(item.reason_code),
      actionCode: text(item.action_code),
      regulatoryClause: text(item.regulatory_clause),
      checkDescription: checkDescriptions[ruleId] ?? "资格判断规则",
      inputEvidenceTypes: inputs.map((input) => input.evidenceType),
      inputs,
      decisionWhenPass: text(item.decision_when_pass),
      decisionWhenFail: text(item.decision_when_fail),
      missingEvidenceAction: text(item.missing_evidence_action),
      supersedesVersion: text(item.supersedes_version) || null,
      checkMinimum:
        typeof check.minimum === "number"
          ? number(check.minimum)
          : typeof check.min_days === "number"
            ? number(check.min_days)
            : null,
    };
  });
}

export interface AffectedAssessmentView {
  executionId: string;
  caseId: string;
  assessmentTime: string;
  requiresReassessment: boolean;
  ruleId: string;
  oldVersion: string;
  newVersion: string;
}

export function adaptAffectedAssessments(dto: unknown): AffectedAssessmentView[] {
  const response = record(dto);
  const responseRuleId = text(response.rule_id);
  const responseOldVersion = text(response.old_version);
  const responseNewVersion = text(response.new_version);
  return array(response.items).map((raw) => {
    const item = record(raw);
    return {
      executionId: text(item.execution_id),
      caseId: text(item.case_id),
      assessmentTime: text(item.assessment_time),
      requiresReassessment: item.requires_reassessment !== false,
      ruleId: text(item.rule_id, responseRuleId),
      oldVersion: text(item.old_version, responseOldVersion),
      newVersion: text(item.new_version, responseNewVersion),
    };
  });
}
