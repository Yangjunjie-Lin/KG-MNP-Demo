import { apiGet, apiPost } from "../../api/client";
import {
  adaptCompetencyQuestions,
  adaptCompetencyResult,
} from "../../api/adapters/competencyAdapter";
import type { components } from "../../api/generated/schema";

type ExecuteRequestDto = components["schemas"]["CompetencyExecuteRequest"];

export async function listCompetencyQuestions(signal?: AbortSignal) {
  return adaptCompetencyQuestions(
    await apiGet("/api/v1/competency-questions", { signal }),
  );
}

export async function getCompetencyQuestion(cqId: string, signal?: AbortSignal) {
  return apiGet("/api/v1/competency-questions/{cq_id}", {
    pathParams: { cq_id: cqId },
    signal,
  });
}

export async function executeCompetencyQuestion(
  cqId: string,
  caseId: string,
  signal?: AbortSignal,
) {
  return adaptCompetencyResult(
    await apiPost(
      "/api/v1/competency-questions/{cq_id}/execute",
      { case_id: caseId } satisfies ExecuteRequestDto,
      { pathParams: { cq_id: cqId }, signal },
    ),
  );
}
