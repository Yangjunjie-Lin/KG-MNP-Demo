// 后续在这里连接本地 FastAPI
import type { AssessmentDetail, PipelineStep } from "../types/assessment";
import {
  case06HistoricalAssessment,
  getMockAssessmentDetail,
  mockAssessments,
  pipelineSteps,
} from "../data/mockAssessments";
import { mockCompetencyQuestions } from "../data/mockCompetencyQuestions";
import type { CompetencyQuestion } from "../data/mockCompetencyQuestions";

export async function getPipelineSteps(): Promise<PipelineStep[]> {
  return Promise.resolve(pipelineSteps);
}

export async function getAssessmentDetail(
  caseId: string,
): Promise<AssessmentDetail | null> {
  return Promise.resolve(getMockAssessmentDetail(caseId) ?? null);
}

export async function listAssessments(): Promise<AssessmentDetail[]> {
  return Promise.resolve(mockAssessments);
}

export async function getHistoricalAssessment(
  caseId: string,
): Promise<AssessmentDetail | null> {
  if (caseId === "CASE-06") {
    return Promise.resolve(case06HistoricalAssessment);
  }
  return Promise.resolve(null);
}

export async function getCompetencyQuestions(): Promise<CompetencyQuestion[]> {
  return Promise.resolve(mockCompetencyQuestions);
}
