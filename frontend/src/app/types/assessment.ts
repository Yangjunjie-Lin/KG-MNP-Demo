import type {
  Decision,
  EvidenceStatus,
  PublicationStatus,
  RuleExecStatus,
  StepStatus,
} from "./common";
import type { ProcessStepCode } from "./process";

export interface EvidenceItem {
  evidenceId: string;
  evidenceType: string;
  sourceSystem: string;
  status: EvidenceStatus;
  generatedAt: string;
  validUntil: string;
  /** Displayable summary; raw codes stay in typed fields below */
  valueSummary: string;
  identityMatchFlag?: boolean;
  numberStatusCode?: string;
  outstandingAmount?: number;
  currencyCode?: string;
  hasPaymentArrangement?: boolean;
  contractStatusCode?: string;
  contractEndTime?: string;
  daysSinceLastPort?: number;
}

export interface RuleResult {
  ruleId: string;
  version: string;
  status: RuleExecStatus;
  effectiveFrom: string | null;
  effectiveTo: string | null;
  selectedForAssessmentTime: boolean;
  reasonCode?: string | null;
  actionCode?: string | null;
  regulatoryClause?: string | null;
}

export interface BlockingReasonDetail {
  reasonCode: string;
  ruleId: string;
  ruleVersion: string;
  regulatoryClause: string;
  actionCode: string;
  evidenceIds: string[];
  description: string;
}

export interface PipelineStep {
  id: string;
  labelKey: string;
  label: string;
  description: string;
  input: string;
  output: string;
  failure: string;
  status?: StepStatus;
}

export interface ProcessState {
  currentStep: ProcessStepCode | string;
  nextStep?: ProcessStepCode | string | null;
  canAdvance: boolean;
  processBlockingReasons: Array<{
    code: string;
    message: string;
  }>;
  authorizationCode?: {
    status: string;
    issuedAt?: string | null;
    validUntil?: string | null;
    maskedValue?: string | null;
  } | null;
  terminationAgreement?: {
    signedAt?: string | null;
    effectiveAt?: string | null;
    status?: string | null;
  } | null;
  eligibilityDecision?: Decision | null;
}

export interface AssessmentHistoryEntry {
  assessmentId: string;
  assessmentTime: string;
  decision: Decision;
  ruleId: string;
  ruleVersion: string;
  /** e.g. required interval days for porting rule */
  requiredDays?: number;
  observedDays?: number;
  note?: string;
}

export interface CaseSummary {
  id: string;
  title: string;
  scenario: string;
  decision: Decision;
  assessmentTime: string;
  blockingReasons: string[];
  executionCount: number;
  published: boolean;
  publicationStatus: PublicationStatus;
  maskedNumber: string;
  daysSinceLastPort?: number;
}

export interface CaseDetail extends CaseSummary {
  subscriberId: string;
  accountId: string;
  evidence: EvidenceItem[];
  ruleResults: RuleResult[];
  blockingReasonDetails: BlockingReasonDetail[];
  process?: ProcessState;
  /** Present for CASE-06: prior eligible assessment under rule v1.0 */
  historicalAssessment?: AssessmentHistoryEntry;
  currentAssessmentNote?: string;
}

export interface AssessmentDetail {
  caseId: string;
  executionId: string;
  assessmentTime: string;
  decision: Decision;
  publicationStatus: PublicationStatus;
  published: boolean;
  evidence: EvidenceItem[];
  ruleResults: RuleResult[];
  blockingReasonDetails: BlockingReasonDetail[];
  pipelineSteps: PipelineStep[];
  process?: ProcessState;
  historicalAssessment?: AssessmentHistoryEntry;
  currentAssessmentNote?: string;
  executionCount: number;
  maskedNumber: string;
  title: string;
  scenario: string;
}
