export const queryKeys = {
  system: ["system"] as const,
  dashboard: ["dashboard"] as const,
  examples: ["examples"] as const,
  cases: ["cases"] as const,
  assessments: ["assessments"] as const,
  assessment: (executionId: string) => ["assessments", executionId] as const,
  ontology: ["ontology"] as const,
  rules: ["rules"] as const,
  affectedAssessments: ["rules", "affected"] as const,
  competencyQuestions: ["competency-questions"] as const,
};
