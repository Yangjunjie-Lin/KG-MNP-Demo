import type { AssessmentDetail, PipelineStep } from "../../app/types/assessment";
import { pipelineStepLabels } from "../../app/i18n/zh-CN";
import { getMockCaseById, mockCases } from "./mockCases";

export const pipelineSteps: PipelineStep[] = [
  {
    id: "json-schema",
    labelKey: "JSON Schema",
    label: pipelineStepLabels["JSON Schema"],
    description: "校验并规范化业务结构化输入",
    input: "原始结构化请求",
    output: "验证通过或失败状态",
    failure: "拒绝请求，返回错误说明",
  },
  {
    id: "rdf-builder",
    labelKey: "RDF Builder",
    label: pipelineStepLabels["RDF Builder"],
    description: "构建案件实例知识图谱",
    input: "已验证的结构化对象",
    output: "实例图三元组",
    failure: "记录构建错误，中止推理",
  },
  {
    id: "input-shacl",
    labelKey: "Input SHACL",
    label: pipelineStepLabels["Input SHACL"],
    description: "验证输入图结构完整性",
    input: "输入实例图",
    output: "约束校验报告",
    failure: "生成违规报告，标记数据缺失",
  },
  {
    id: "owl-rl",
    labelKey: "OWL-RL",
    label: pipelineStepLabels["OWL-RL"],
    description: "确定性类型与关系扩展",
    input: "输入图与本体公理",
    output: "扩展推理图",
    failure: "退化为无推理模式并记录警告",
  },
  {
    id: "rule-engine",
    labelKey: "Rule Engine",
    label: pipelineStepLabels["Rule Engine"],
    description: "执行确定性资格规则",
    input: "推理图与规则集",
    output: "资格结论与阻塞原因",
    failure: "规则执行异常，升级为人工复核",
  },
  {
    id: "assessment",
    labelKey: "Assessment",
    label: pipelineStepLabels.Assessment,
    description: "物化评估、决定与阻塞原因",
    input: "规则结果集",
    output: "最终资格结论与评估节点",
    failure: "无可用结果时默认人工复核",
  },
  {
    id: "assessment-shacl",
    labelKey: "Assessment SHACL",
    label: pipelineStepLabels["Assessment SHACL"],
    description: "验证评估结果图完整性",
    input: "评估结果图",
    output: "输出完整性报告",
    failure: "评估图不完整，发出警告",
  },
  {
    id: "sparql-trace",
    labelKey: "SPARQL Trace",
    label: pipelineStepLabels["SPARQL Trace"],
    description: "查询可追溯关系子图",
    input: "完整推理图",
    output: "证据链、规则版本、条款映射",
    failure: "追溯查询失败，降级输出摘要",
  },
];

function stepsForDecision(decision: string): PipelineStep[] {
  const failedAtRule = decision === "BLOCKED" || decision === "MANUAL_REVIEW";
  return pipelineSteps.map((step, index) => {
    if (index < 4) return { ...step, status: "PASSED" as const };
    if (step.id === "rule-engine") {
      return {
        ...step,
        status: failedAtRule && decision === "MANUAL_REVIEW" ? "DONE" : "PASSED",
      };
    }
    if (index <= 6) return { ...step, status: "PASSED" as const };
    return { ...step, status: "DONE" as const };
  });
}

export const mockAssessments: AssessmentDetail[] = mockCases.map((c) => ({
  caseId: c.id,
  executionId: `EXEC-${c.id}`,
  assessmentTime: c.assessmentTime,
  decision: c.decision,
  publicationStatus: c.publicationStatus,
  published: c.published,
  evidence: c.evidence,
  ruleResults: c.ruleResults,
  blockingReasonDetails: c.blockingReasonDetails,
  pipelineSteps: stepsForDecision(c.decision),
  process: c.process,
  historicalAssessment: c.historicalAssessment,
  currentAssessmentNote: c.currentAssessmentNote,
  executionCount: c.executionCount,
  maskedNumber: c.maskedNumber,
  title: c.title,
  scenario: c.scenario,
}));

/** CASE-06 historical assessment snapshot under rule v1.0 */
export const case06HistoricalAssessment: AssessmentDetail = {
  caseId: "CASE-06",
  executionId: "EXEC-CASE-06-HIST",
  assessmentTime: "2026-05-15T00:00:00Z",
  decision: "ELIGIBLE",
  publicationStatus: "PUBLISHABLE",
  published: true,
  evidence: getMockCaseById("CASE-06")!.evidence,
  ruleResults: [
    {
      ruleId: "MNP-ELIG-001",
      version: "1.0",
      status: "PASS",
      effectiveFrom: "2024-01-01T00:00:00Z",
      effectiveTo: null,
      selectedForAssessmentTime: true,
    },
    {
      ruleId: "MNP-ELIG-002",
      version: "1.0",
      status: "PASS",
      effectiveFrom: "2024-01-01T00:00:00Z",
      effectiveTo: null,
      selectedForAssessmentTime: true,
    },
    {
      ruleId: "MNP-ELIG-003",
      version: "1.0",
      status: "PASS",
      effectiveFrom: "2024-01-01T00:00:00Z",
      effectiveTo: null,
      selectedForAssessmentTime: true,
    },
    {
      ruleId: "MNP-ELIG-004",
      version: "1.0",
      status: "PASS",
      effectiveFrom: "2024-01-01T00:00:00Z",
      effectiveTo: null,
      selectedForAssessmentTime: true,
    },
    {
      ruleId: "MNP-ELIG-005",
      version: "1.0",
      status: "PASS",
      effectiveFrom: "2024-01-01T00:00:00Z",
      effectiveTo: "2026-05-31T23:59:59Z",
      selectedForAssessmentTime: true,
    },
  ],
  blockingReasonDetails: [],
  pipelineSteps: stepsForDecision("ELIGIBLE"),
  historicalAssessment: undefined,
  currentAssessmentNote: "历史评估：规则版本 1.0 要求 120 天，观测 150 天，结论可携转。",
  executionCount: 1,
  maskedNumber: "138****0006",
  title: "规则版本更新后携转间隔不足",
  scenario: "历史规则版本下可携转",
};

export function getMockAssessmentDetail(caseId: string): AssessmentDetail | undefined {
  return mockAssessments.find((a) => a.caseId === caseId);
}
