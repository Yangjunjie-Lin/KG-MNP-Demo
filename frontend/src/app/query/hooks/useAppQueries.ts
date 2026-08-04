import { useMutation, useQuery, useQueryClient } from "@tanstack/react-query";
import { getDashboard } from "../../services/dashboardService";
import { listCases } from "../../services/caseService";
import { getAssessmentDetail, createAssessment, runWhatIf, type AssessmentPayload } from "../../services/assessmentService";
import { getOntology } from "../../services/ontologyService";
import { getAffectedAssessments, listRules } from "../../services/ruleService";
import { listCompetencyQuestions } from "../../services/competencyService";
import { getSystemStatus } from "../../services/systemService";
import { listExamples, runExample } from "../../services/exampleService";
import { queryKeys } from "../keys";
import type { WhatIfScenarioChanges } from "../../../api/adapters/whatIfAdapter";

export const useSystemStatus = () =>
  useQuery({ queryKey: queryKeys.system, queryFn: ({ signal }) => getSystemStatus(signal), refetchInterval: 30_000 });
export const useDashboard = () => useQuery({ queryKey: queryKeys.dashboard, queryFn: ({ signal }) => getDashboard(signal) });
export const useExamples = () => useQuery({ queryKey: queryKeys.examples, queryFn: ({ signal }) => listExamples(signal) });
export const useCases = () => useQuery({ queryKey: queryKeys.cases, queryFn: ({ signal }) => listCases(signal) });
export const useAssessment = (executionId: string) => useQuery({ queryKey: queryKeys.assessment(executionId), queryFn: ({ signal }) => getAssessmentDetail(executionId, signal), enabled: !!executionId });
export const useOntology = () => useQuery({ queryKey: queryKeys.ontology, queryFn: ({ signal }) => getOntology(signal) });
export const useRules = () => useQuery({ queryKey: queryKeys.rules, queryFn: ({ signal }) => listRules(signal) });
export const useAffectedAssessments = () => useQuery({ queryKey: queryKeys.affectedAssessments, queryFn: ({ signal }) => getAffectedAssessments(signal) });
export const useCompetencyQuestions = () => useQuery({ queryKey: queryKeys.competencyQuestions, queryFn: ({ signal }) => listCompetencyQuestions(signal) });

function useInvalidateCore() {
  const client = useQueryClient();
  return async () => {
    await Promise.all([
      client.invalidateQueries({ queryKey: queryKeys.cases }),
      client.invalidateQueries({ queryKey: queryKeys.assessments }),
      client.invalidateQueries({ queryKey: queryKeys.dashboard }),
    ]);
  };
}

export function useRunExample() {
  const invalidate = useInvalidateCore();
  return useMutation({ mutationFn: (caseId: string) => runExample(caseId), onSuccess: invalidate });
}

export function useCreateAssessment() {
  const invalidate = useInvalidateCore();
  return useMutation({ mutationFn: (payload: AssessmentPayload) => createAssessment(payload), onSuccess: invalidate });
}

export function useWhatIf() {
  return useMutation({ mutationFn: ({ executionId, changes }: { executionId: string; changes: WhatIfScenarioChanges }) => runWhatIf(executionId, changes) });
}
