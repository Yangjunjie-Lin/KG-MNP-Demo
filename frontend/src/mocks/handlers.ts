import { http, HttpResponse } from "msw";
import {
  affectedAssessmentsFixture,
  assessmentRecordFixture,
  assessmentViewsFixture,
  caseCatalogFixture,
  competencyQuestionsFixture,
  competencyResultFixture,
  dashboardFixture,
  exampleInputFixture,
  examplesFixture,
  healthFixture,
  historiesFixture,
  metaFixture,
  ontologyPropertiesFixture,
  ontologyViewFixture,
  readyFixture,
  ruleCatalogFixture,
  ruleVersionsFixture,
  whatIfFixture,
} from "./fixtures/api";

export const handlers = [
  http.get("*/api/v1/health", () => HttpResponse.json(healthFixture)),
  http.get("*/api/v1/ready", () => HttpResponse.json(readyFixture)),
  http.get("*/api/v1/meta", () => HttpResponse.json(metaFixture)),
  http.get("*/api/v1/views/dashboard", () => HttpResponse.json(dashboardFixture)),
  http.get("*/api/v1/cases", () => HttpResponse.json(caseCatalogFixture)),
  http.get("*/api/v1/cases/:caseId/history", ({ params }) => {
    const caseId = String(params.caseId);
    return HttpResponse.json({ case_id: caseId, items: historiesFixture[caseId] ?? [] });
  }),
  http.get("*/api/v1/assessments/:executionId", ({ params }) => {
    const executionId = String(params.executionId);
    const view = assessmentViewsFixture[executionId];
    return HttpResponse.json(
      assessmentRecordFixture(executionId, view?.header.case_id ?? "CASE-03"),
    );
  }),
  http.get("*/api/v1/views/assessments/:executionId", ({ params }) => {
    const executionId = String(params.executionId);
    const view = assessmentViewsFixture[executionId];
    return view
      ? HttpResponse.json(view)
      : HttpResponse.json(
          { error: { code: "ASSESSMENT_NOT_FOUND", message: "not found", details: [], retryable: false } },
          { status: 404 },
        );
  }),
  http.get("*/api/v1/examples", () => HttpResponse.json(examplesFixture)),
  http.get("*/api/v1/examples/:caseId", ({ params }) => {
    const caseId = String(params.caseId);
    return HttpResponse.json({
      case_id: caseId,
      scenario: "后端示例案例",
      expected_decision: caseId === "CASE-03" ? "BLOCKED" : "ELIGIBLE",
      input: { ...exampleInputFixture, case_id: caseId },
    });
  }),
  http.post("*/api/v1/examples/:caseId/run", ({ params }) =>
    HttpResponse.json(assessmentRecordFixture(`exec-${String(params.caseId).toLowerCase()}`, String(params.caseId))),
  ),
  http.post("*/api/v1/assessments", () => HttpResponse.json(assessmentRecordFixture())),
  http.post("*/api/v1/assessments/:executionId/what-if", () => HttpResponse.json(whatIfFixture)),
  http.get("*/api/v1/views/ontology", () => HttpResponse.json(ontologyViewFixture)),
  http.get("*/api/v1/ontology/properties", () => HttpResponse.json(ontologyPropertiesFixture)),
  http.get("*/api/v1/rules", () => HttpResponse.json(ruleCatalogFixture)),
  http.get("*/api/v1/rules/:ruleId/versions", ({ params }) =>
    HttpResponse.json({
      rule_id: params.ruleId,
      versions: ruleVersionsFixture[String(params.ruleId)] ?? [],
    }),
  ),
  http.get("*/api/v1/rule-updates/affected-assessments", () =>
    HttpResponse.json(affectedAssessmentsFixture),
  ),
  http.get("*/api/v1/competency-questions", () =>
    HttpResponse.json(competencyQuestionsFixture),
  ),
  http.post("*/api/v1/competency-questions/:cqId/execute", () =>
    HttpResponse.json(competencyResultFixture),
  ),
];
