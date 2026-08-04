import { apiGet } from "../../api/client";
import {
  adaptCaseCatalog,
  adaptCaseDetail,
  adaptCaseHistory,
  adaptCaseView,
  type CaseViewModel,
} from "../../api/adapters/caseAdapter";
import { adaptAssessmentRecord } from "../../api/adapters/assessmentAdapter";

export async function listCases(signal?: AbortSignal): Promise<CaseViewModel[]> {
  const catalog = await apiGet("/api/v1/views/cases", { signal });
  return adaptCaseCatalog(catalog);
}

export async function getCaseById(caseId: string, signal?: AbortSignal) {
  return adaptCaseDetail(
    await apiGet("/api/v1/cases/{case_id}", { pathParams: { case_id: caseId }, signal }),
  );
}

export async function getCaseHistory(caseId: string, signal?: AbortSignal) {
  return adaptCaseHistory(
    await apiGet("/api/v1/cases/{case_id}/history", {
      pathParams: { case_id: caseId },
      signal,
    }),
  );
}

export async function getCaseLatest(caseId: string, signal?: AbortSignal) {
  const dto = await apiGet("/api/v1/cases/{case_id}/latest", {
    pathParams: { case_id: caseId },
    signal,
  });
  return dto ? adaptAssessmentRecord(dto) : null;
}

export async function getCaseView(caseId: string, signal?: AbortSignal) {
  return adaptCaseView(
    await apiGet("/api/v1/views/cases/{case_id}", {
      pathParams: { case_id: caseId },
      signal,
    }),
  );
}
