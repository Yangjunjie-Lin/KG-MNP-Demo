import { apiGet, apiPost } from "../../api/client";
import { adaptAssessmentRecord } from "../../api/adapters/assessmentAdapter";
import { array, record, text } from "../../api/adapters/guards";

export interface ExampleView {
  caseId: string;
  scenario: string;
  expectedDecision: string;
  input?: Record<string, unknown>;
}

export async function listExamples(signal?: AbortSignal): Promise<ExampleView[]> {
  const dto = record(await apiGet("/api/v1/examples", { signal }));
  return array(dto.items).map((raw) => {
    const item = record(raw);
    return {
      caseId: text(item.case_id),
      scenario: text(item.scenario),
      expectedDecision: text(item.expected_decision),
    };
  });
}

export async function getExample(caseId: string, signal?: AbortSignal): Promise<ExampleView> {
  const item = record(
    await apiGet("/api/v1/examples/{case_id}", {
      pathParams: { case_id: caseId },
      signal,
    }),
  );
  return {
    caseId: text(item.case_id),
    scenario: text(item.scenario),
    expectedDecision: text(item.expected_decision),
    input: record(item.input),
  };
}

export async function runExample(caseId: string, signal?: AbortSignal) {
  return adaptAssessmentRecord(
    await apiPost(
      "/api/v1/examples/{case_id}/run",
      undefined,
      { pathParams: { case_id: caseId }, signal },
    ),
  );
}
