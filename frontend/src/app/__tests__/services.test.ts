import { describe, expect, it } from "vitest";
import {
  getAssessmentDetail,
  getHistoricalAssessment,
  getPipelineSteps,
  getCompetencyQuestions,
} from "../services/assessmentService";
import { listCases, getCaseById } from "../services/caseService";
import { listRules } from "../services/ruleService";
import { getNodes, getEdges, getModules } from "../services/ontologyService";

describe("Service 层模拟数据", () => {
  it("案例服务返回九个案例", async () => {
    const cases = await listCases();
    expect(cases).toHaveLength(9);
    const c07 = await getCaseById("CASE-07");
    expect(c07?.decision).toBe("ELIGIBLE");
    expect(c07?.process?.canAdvance).toBe(false);
  });

  it("评估服务区分案例六历史与当前", async () => {
    const current = await getAssessmentDetail("CASE-06");
    const historical = await getHistoricalAssessment("CASE-06");
    expect(current?.decision).toBe("BLOCKED");
    expect(historical?.decision).toBe("ELIGIBLE");
    expect(current?.historicalAssessment?.requiredDays).toBe(120);
  });

  it("规则与本体、能力问题可加载", async () => {
    const [rules, nodes, edges, modules, steps, cqs] = await Promise.all([
      listRules(),
      getNodes(),
      getEdges(),
      getModules(),
      getPipelineSteps(),
      getCompetencyQuestions(),
    ]);
    expect(rules.length).toBeGreaterThanOrEqual(5);
    expect(nodes.length).toBeGreaterThan(0);
    expect(edges.length).toBeGreaterThan(0);
    expect(modules.length).toBeGreaterThan(0);
    expect(steps.every((s) => /[\u4e00-\u9fff]/.test(s.label))).toBe(true);
    expect(cqs).toHaveLength(15);
  });
});
