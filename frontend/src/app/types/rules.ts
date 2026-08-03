export interface RuleInputSpec {
  evidenceType: string;
  required: boolean;
  fields: string[];
}

export interface EligibilityRule {
  ruleId: string;
  version: string;
  name: string;
  effectiveFrom: string;
  effectiveTo: string | null;
  reasonCode: string;
  actionCode: string;
  regulatoryClause: string;
  checkDescription: string;
  inputEvidenceTypes: string[];
  inputs: RuleInputSpec[];
  decisionWhenPass: string;
  decisionWhenFail: string;
  missingEvidenceAction: string;
  supersedesVersion?: string | null;
  /** Numeric check parameter when applicable (e.g. min porting interval days) */
  checkMinimum?: number | null;
}
