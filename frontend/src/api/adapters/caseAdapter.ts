import type { CaseSummary } from "../../app/types/assessment";
import type { Decision, PublicationStatus } from "../../app/types/common";
import { adaptAssessmentView, type AssessmentViewModel } from "./assessmentAdapter";
import { array, bool, number, record, text } from "./guards";

export interface CaseViewModel extends CaseSummary {
  latestExecutionId: string | null;
  hasHistory: boolean;
}

export interface CaseDetailViewModel {
  caseId: string;
  scenario: string;
  expectedDecision: string;
  input: Record<string, unknown>;
}

export interface CasePageViewModel {
  case: Record<string, unknown>;
  latestAssessment: AssessmentViewModel | null;
}

export interface CaseHistoryItemView {
  executionId: string;
  caseId: string;
  assessmentTime: string;
  decision: string;
  publicationStatus: string;
  publishable: boolean;
}

function safeDecision(value: unknown): Decision {
  const raw = text(value);
  return ["ELIGIBLE", "BLOCKED", "MANUAL_REVIEW", "CONDITIONAL"].includes(raw)
    ? (raw as Decision)
    : "UNKNOWN";
}

export function adaptCaseCatalog(dto: unknown, histories: Map<string, unknown[]>): CaseViewModel[] {
  const items = array(record(dto).items);
  return items.map((raw) => {
    const item = record(raw);
    const caseId = text(item.case_id);
    const records = (histories.get(caseId) ?? [])
      .map(record)
      .sort((left, right) => text(right.assessment_time).localeCompare(text(left.assessment_time)));
    const latest = records[0] ?? {};
    const hasHistory = records.length > 0;
    return {
      id: caseId,
      title: "预置演示案例",
      scenario: text(item.scenario, "真实后端演示案例"),
      decision: safeDecision(latest.decision),
      assessmentTime: text(latest.assessment_time),
      blockingReasons: [],
      executionCount: records.length,
      published: bool(latest.publishable),
      publicationStatus: text(latest.publication_status, "NOT_PUBLISHABLE") as PublicationStatus,
      maskedNumber: "已脱敏",
      latestExecutionId: hasHistory ? text(latest.execution_id) : null,
      hasHistory,
    };
  });
}

export function adaptAssessmentList(dto: unknown): Array<Record<string, unknown>> {
  return array(record(dto).items).map(record).map((item) => ({
    executionId: text(item.execution_id),
    caseId: text(item.case_id),
    assessmentTime: text(item.assessment_time),
    decision: text(item.decision),
    publicationStatus: text(item.publication_status),
    publishable: bool(item.publishable),
    blockingReasonCount: number(item.blocking_reason_count),
  }));
}

export function adaptCaseHistory(dto: unknown): CaseHistoryItemView[] {
  return array(record(dto).items).map((raw) => {
    const item = record(raw);
    return {
      executionId: text(item.execution_id),
      caseId: text(item.case_id),
      assessmentTime: text(item.assessment_time),
      decision: text(item.decision),
      publicationStatus: text(item.publication_status),
      publishable: bool(item.publishable),
    };
  });
}

export function adaptCaseDetail(dto: unknown): CaseDetailViewModel {
  const value = record(dto);
  return {
    caseId: text(value.case_id),
    scenario: text(value.scenario),
    expectedDecision: text(value.expected_decision),
    input: record(value.input),
  };
}

export function adaptCaseView(dto: unknown): CasePageViewModel {
  const value = record(dto);
  const caseInput = record(value.case);
  const latest = value.latest_assessment;
  return {
    case: caseInput,
    latestAssessment: latest
      ? adaptAssessmentView(latest, { input: caseInput })
      : null,
  };
}
