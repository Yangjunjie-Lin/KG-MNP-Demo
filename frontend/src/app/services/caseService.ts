// 后续在这里连接本地 FastAPI
import type { CaseDetail, CaseSummary } from "../types/assessment";
import {
  getMockCaseById,
  mockCaseSummaries,
  mockCases,
} from "../data/mockCases";
import { mockCompetencyQuestions } from "../data/mockCompetencyQuestions";
import type { CompetencyQuestion } from "../data/mockCompetencyQuestions";

export async function listCases(): Promise<CaseSummary[]> {
  return Promise.resolve(mockCaseSummaries);
}

export async function getCaseById(caseId: string): Promise<CaseDetail | null> {
  return Promise.resolve(getMockCaseById(caseId) ?? null);
}

export async function listCaseDetails(): Promise<CaseDetail[]> {
  return Promise.resolve(mockCases);
}

export async function getCompetencyQuestions(): Promise<CompetencyQuestion[]> {
  return Promise.resolve(mockCompetencyQuestions);
}
