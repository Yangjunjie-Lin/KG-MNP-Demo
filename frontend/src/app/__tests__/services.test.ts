import { http, HttpResponse } from "msw";
import { describe, expect, it } from "vitest";
import { server } from "../../mocks/server";
import { caseCatalogViewFixture } from "../../mocks/fixtures/api";
import { getAssessmentDetail, runWhatIf } from "../services/assessmentService";
import { listCases } from "../services/caseService";
import { getAffectedAssessments, listRules } from "../services/ruleService";
import { getOntology } from "../services/ontologyService";
import { executeCompetencyQuestion } from "../services/competencyService";

describe("真实 HTTP Service 层", () => {
  it("评估详情来自视图接口", async () => {
    server.use(http.get("*/api/v1/views/assessments/e-1", () => HttpResponse.json({ header: { execution_id: "e-1", case_id: "CASE-07", assessment_time: "2026-07-01T00:00:00Z" }, decision_card: { decision: "ELIGIBLE", publication: { publishable: true, status: "PUBLISHABLE" } }, input_summary: {}, validation_steps: [], evidence_table: [], rule_execution_table: [], blocking_reason_cards: [], remediation_actions: [], process_status: { can_advance: false, authorization_code: { status: "EXPIRED" } }, trace_graph: { nodes: [], edges: [] }, timeline: [], artifacts: [], technical_details: {} })));
    const detail = await getAssessmentDetail("e-1");
    expect(detail.decision).toBe("ELIGIBLE");
    expect(detail.process?.canAdvance).toBe(false);
    expect(detail.process?.authorizationCode?.status).toBe("EXPIRED");
  });

  it("规则、本体和能力问题由 HTTP 响应适配", async () => {
    server.use(
      http.get("*/api/v1/rules", () => HttpResponse.json({ items: [{ rule_id: "MNP-ELIG-004", version: "1.0", effective_from: "2024-01-01", reason_code: "ACTIVE_CONTRACT_RESTRICTION", action_code: "WAIT_OR_TERMINATE_CONTRACT", regulatory_clause: "REG-MNP-CLAUSE-04", inputs: [] }] })),
      http.get("*/api/v1/views/ontology", () => HttpResponse.json({ modules: [{ module: "Core", label_zh: "核心" }], graph: { nodes: [{ id: "a", local_name: "MNPCase", type: "Class", module: "Core" }], edges: [{ source: "a", target: "b", predicate: "hasAssessment" }] }, key_paths: [], stats: {} })),
      http.post("*/api/v1/competency-questions/CQ-01/execute", () => HttpResponse.json({ question_id: "CQ-01", case_id: "CASE-03", status: "success", columns: ["decision"], rows: [{ decision: "BLOCKED" }] })),
      http.get("*/api/v1/rule-updates/affected-assessments", () => HttpResponse.json({ rule_id: "MNP-ELIG-005", old_version: "1.0", new_version: "1.1", items: [{ execution_id: "history", case_id: "CASE-06", assessment_time: "2026-05-15" }] })),
    );
    expect(await listRules()).toHaveLength(1);
    expect((await getOntology()).edges).toHaveLength(1);
    expect((await executeCompetencyQuestion("CQ-01", "CASE-03")).rows).toEqual([{ decision: "BLOCKED" }]);
    expect((await getAffectedAssessments())[0].executionId).toBe("history");
  });

  it("What-if 请求仅发送 changes，不在 Service 计算结论", async () => {
    let body: unknown;
    server.use(http.post("*/api/v1/assessments/e-1/what-if", async ({ request }) => { body = await request.json(); return HttpResponse.json({ baseline: { decision: "BLOCKED" }, scenario: { decision: "ELIGIBLE" }, decision_changed: true, rule_changes: [], reason_changes: {}, evidence_changes: {}, trace_changes: {} }); }));
    const result = await runWhatIf("e-1", { contractStatus: "EXPIRED" });
    expect(body).toEqual({ changes: { evidence: { contract: { contract_status: "EXPIRED" } } } });
    expect(result.scenarioDecision).toBe("ELIGIBLE");
  });

  it("案件列表只请求一次聚合视图，不再逐案例读取历史", async () => {
    let aggregateRequests = 0;
    let historyRequests = 0;
    server.use(
      http.get("*/api/v1/views/cases", () => {
        aggregateRequests += 1;
        return HttpResponse.json(caseCatalogViewFixture);
      }),
      http.get("*/api/v1/cases/:caseId/history", () => {
        historyRequests += 1;
        return HttpResponse.json({ items: [] });
      }),
    );
    const cases = await listCases();
    expect(cases).toHaveLength(9);
    const case06 = cases.find((item) => item.id === "CASE-06");
    expect(case06).toMatchObject({
      decision: "BLOCKED",
      assessmentTime: "2026-07-01T00:00:00Z",
      executionCount: 2,
      hasHistory: true,
    });
    const case01 = cases.find((item) => item.id === "CASE-01");
    expect(case01).toMatchObject({
      decision: "UNKNOWN",
      executionCount: 0,
      hasHistory: false,
      latestExecutionId: null,
    });
    expect(aggregateRequests).toBe(1);
    expect(historyRequests).toBe(0);
  });
});
