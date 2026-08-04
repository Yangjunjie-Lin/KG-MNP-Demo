import { describe, expect, it } from "vitest";
import { adaptAssessmentView } from "../adapters/assessmentAdapter";
import { adaptOntologyView } from "../adapters/ontologyAdapter";
import { adaptSystemStatus } from "../adapters/systemAdapter";
import { adaptWhatIf } from "../adapters/whatIfAdapter";

describe("接口数据适配", () => {
  it("将后端 snake_case 转为评估 View Model，并只使用响应追溯边", () => {
    const result = adaptAssessmentView({
      header: { execution_id: "e-1", case_id: "CASE-03", assessment_time: "2026-07-01T00:00:00Z" },
      decision_card: { decision: "BLOCKED", publication: { status: "PUBLISHABLE", publishable: true } },
      validation_steps: [], evidence_table: [], rule_execution_table: [], blocking_reason_cards: [], process_status: {}, timeline: [],
      trace_graph: { nodes: [{ id: "a", label: "A", type: "MNPCase" }, { id: "b", label: "B", type: "EligibilityAssessment" }], edges: [{ source: "a", target: "b", predicate: "hasAssessment" }] },
    });
    expect(result.executionId).toBe("e-1");
    expect(result.caseId).toBe("CASE-03");
    expect(result.traceEdges).toEqual([{ source: "a", target: "b", relation: "hasAssessment" }]);
    expect(result).not.toHaveProperty("execution_id");
  });

  it("本体布局只增加坐标，不改变节点身份和边关系", () => {
    const result = adaptOntologyView(
      { modules: [], stats: {}, graph: { nodes: [{ id: "iri:a", local_name: "A", type: "Class", module: "Core" }], edges: [{ source: "iri:a", target: "iri:b", predicate: "related" }] } },
      { object_properties: [{ local_name: "related", label_zh: "关联" }] },
    );
    expect(result.nodes[0]).toMatchObject({ id: "iri:a", localName: "A" });
    expect(result.edges[0]).toEqual({ from: "iri:a", to: "iri:b", relation: "related", label: "关联" });
  });

  it("系统状态仅消费真实字段", () => {
    const result = adaptSystemStatus({ status: "ok", time: "now" }, { status: "ready", sqlite: true, neo4j_required: false }, { api_version: "v1", schema_version: "1.0", backend: "rdf" });
    expect(result).toMatchObject({ reachable: true, databaseReady: true, apiVersion: "v1", schemaVersion: "1.0" });
    expect(result).not.toHaveProperty("latency");
    expect(result).not.toHaveProperty("uptime");
  });

  it("情景推演只消费后端差异", () => {
    const result = adaptWhatIf({ baseline: { decision: "BLOCKED" }, scenario: { decision: "ELIGIBLE" }, decision_changed: true, rule_changes: [{ changed: true }], reason_changes: {}, evidence_changes: {}, trace_changes: { edge_count_delta: 2 } });
    expect(result.scenarioDecision).toBe("ELIGIBLE");
    expect(result.ruleChanges).toEqual([{
      ruleId: "",
      versionBefore: "",
      versionAfter: "",
      statusBefore: "SKIP",
      statusAfter: "SKIP",
      changed: true,
      changeKind: "",
    }]);
    expect(result.traceChanges.edgeCountDelta).toBe(2);
  });
});
