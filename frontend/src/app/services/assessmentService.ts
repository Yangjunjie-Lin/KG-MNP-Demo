import { apiGet, apiPost } from "../../api/client";
import {
  adaptAssessmentArtifacts,
  adaptAssessmentComparison,
  adaptAssessmentRecord,
  adaptAssessmentTimeline,
  adaptAssessmentTrace,
  adaptAssessmentView,
  type AssessmentViewModel,
} from "../../api/adapters/assessmentAdapter";
import { adaptAssessmentList } from "../../api/adapters/caseAdapter";
import {
  adaptWhatIf,
  toWhatIfDtoChanges,
  type WhatIfScenarioChanges,
} from "../../api/adapters/whatIfAdapter";
import type { components } from "../../api/generated/schema";

export type AssessmentPayload = components["schemas"]["MNPCaseInput"];
export type AssessmentCreateRequest = components["schemas"]["AssessmentCreateRequest"];
type WhatIfRequestDto = components["schemas"]["WhatIfRequest"];

export async function createAssessment(
  payload: AssessmentPayload,
  options: { persist?: boolean; forceRecompute?: boolean; signal?: AbortSignal } = {},
): Promise<AssessmentViewModel> {
  const body: AssessmentCreateRequest = {
    payload,
    persist: options.persist ?? true,
    force_recompute: options.forceRecompute ?? false,
  };
  return adaptAssessmentRecord(
    await apiPost("/api/v1/assessments", body, { signal: options.signal }),
  );
}

export async function listAssessments(signal?: AbortSignal) {
  return adaptAssessmentList(await apiGet("/api/v1/assessments", { signal }));
}

export async function getAssessmentDetail(
  executionId: string,
  signal?: AbortSignal,
): Promise<AssessmentViewModel> {
  const [view, record] = await Promise.all([
    apiGet("/api/v1/views/assessments/{execution_id}", {
      pathParams: { execution_id: executionId },
      signal,
    }),
    apiGet("/api/v1/assessments/{execution_id}", {
      pathParams: { execution_id: executionId },
      signal,
    }),
  ]);
  return adaptAssessmentView(view, record);
}

export const getAssessmentView = getAssessmentDetail;

export async function getAssessmentRecord(executionId: string, signal?: AbortSignal) {
  return adaptAssessmentRecord(
    await apiGet("/api/v1/assessments/{execution_id}", {
      pathParams: { execution_id: executionId },
      signal,
    }),
  );
}

export async function compareAssessments(left: string, right: string, signal?: AbortSignal) {
  return adaptAssessmentComparison(
    await apiGet("/api/v1/assessments/compare", { query: { left, right }, signal }),
  );
}

export async function getAssessmentArtifacts(executionId: string, signal?: AbortSignal) {
  return adaptAssessmentArtifacts(
    await apiGet("/api/v1/assessments/{execution_id}/artifacts", {
      pathParams: { execution_id: executionId },
      signal,
    }),
  );
}

export async function getAssessmentTrace(executionId: string, signal?: AbortSignal) {
  const dto = await apiGet("/api/v1/assessments/{execution_id}/trace", {
    pathParams: { execution_id: executionId },
    signal,
  });
  return adaptAssessmentTrace({ ...dto, execution_id: executionId });
}

export async function getAssessmentTraceView(executionId: string, signal?: AbortSignal) {
  return adaptAssessmentTrace(
    await apiGet("/api/v1/views/assessments/{execution_id}/trace", {
      pathParams: { execution_id: executionId },
      signal,
    }),
  );
}

export async function getAssessmentTimeline(executionId: string, signal?: AbortSignal) {
  return adaptAssessmentTimeline(
    await apiGet("/api/v1/views/assessments/{execution_id}/timeline", {
      pathParams: { execution_id: executionId },
      signal,
    }),
  );
}

export async function runWhatIf(
  executionId: string,
  changes: WhatIfScenarioChanges,
  signal?: AbortSignal,
) {
  const body: WhatIfRequestDto = { changes: toWhatIfDtoChanges(changes) };
  return adaptWhatIf(
    await apiPost(
      "/api/v1/assessments/{execution_id}/what-if",
      body,
      { pathParams: { execution_id: executionId }, signal },
    ),
  );
}
