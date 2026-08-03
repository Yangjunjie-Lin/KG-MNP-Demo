import { useEffect, useState } from "react";
import {
  AlertTriangle,
  ArrowRight,
  CheckCircle2,
  ChevronLeft,
  XCircle,
} from "lucide-react";
import { SectionHeader } from "../components/SectionHeader";
import { BlockingReasonCard } from "../components/BlockingReasonCard";
import { DecisionBadge, StatusBadge } from "../components/StatusBadges";
import { cn } from "../utils/cn";
import {
  authCodeStatusLabels,
  blockingReasonLabels,
  caseLabels,
  dataSourceLabels,
  decisionLabels,
  evidenceTypeLabels,
  ontologyClassLabels,
  ontologyRelationLabels,
  processStepLabels,
  publicationStatusLabels,
  remediationActionLabels,
  ruleLabels,
  t,
  ui,
} from "../i18n/zh-CN";
import {
  getAssessmentDetail,
  getHistoricalAssessment,
} from "../services/assessmentService";
import type { AssessmentDetail } from "../types/assessment";
import type { Decision, StepStatus } from "../types/common";

function formatTime(iso: string): string {
  return iso.replace("T", " ").replace("Z", "").slice(0, 19);
}

const TABS = [
  { id: "timeline", label: "处理时间线" },
  { id: "validation", label: "验证结果" },
  { id: "evidence", label: "证据表" },
  { id: "rules", label: "规则执行" },
  { id: "blocking", label: "阻塞原因" },
  { id: "process", label: "流程状态" },
  { id: "trace", label: "追溯图" },
];

function TraceGraph({ detail }: { detail: AssessmentDetail }) {
  const [selectedNode, setSelectedNode] = useState<string | null>(null);
  const caseLabel = t(caseLabels, detail.caseId, detail.caseId);
  const firstBlock = detail.blockingReasonDetails[0];
  const brLabel = firstBlock
    ? t(blockingReasonLabels, firstBlock.reasonCode, firstBlock.reasonCode)
    : "无阻塞";
  const ruleLabel = firstBlock
    ? t(ruleLabels, firstBlock.ruleId, firstBlock.ruleId)
    : t(ruleLabels, "MNP-ELIG-001");
  const actionLabel = firstBlock
    ? t(remediationActionLabels, firstBlock.actionCode, firstBlock.actionCode)
    : "—";

  const nodes = [
    { id: "case", label: caseLabel, type: "MNPCase", x: 40, y: 160, color: "#2563eb" },
    { id: "assessment", label: "资格评估", type: "EligibilityAssessment", x: 200, y: 160, color: "#7c3aed" },
    { id: "ev1", label: t(evidenceTypeLabels, "CONTRACT_STATUS"), type: "EvidenceRecord", x: 360, y: 80, color: "#0891b2" },
    { id: "ev2", label: t(evidenceTypeLabels, "BILLING_BALANCE"), type: "EvidenceRecord", x: 360, y: 160, color: "#0891b2" },
    { id: "ev3", label: t(evidenceTypeLabels, "IDENTITY_MATCH"), type: "EvidenceRecord", x: 360, y: 240, color: "#0891b2" },
    { id: "br1", label: brLabel, type: "BlockingReason", x: 530, y: 80, color: "#dc2626" },
    { id: "rule", label: ruleLabel, type: "EligibilityRule", x: 690, y: 40, color: "#7c3aed" },
    { id: "rv", label: firstBlock ? `版本 ${firstBlock.ruleVersion}` : "版本 1.0", type: "RuleVersion", x: 830, y: 40, color: "#5b21b6" },
    { id: "rc", label: firstBlock?.regulatoryClause ?? "监管条款", type: "RegulatoryClause", x: 830, y: 130, color: "#1e3a8a" },
    { id: "ra", label: actionLabel, type: "RemediationAction", x: 690, y: 150, color: "#059669" },
  ];

  const edges = [
    { from: "case", to: "assessment", label: ontologyRelationLabels.hasAssessment },
    { from: "assessment", to: "ev1", label: ontologyRelationLabels.usesEvidence },
    { from: "assessment", to: "ev2", label: ontologyRelationLabels.usesEvidence },
    { from: "assessment", to: "ev3", label: ontologyRelationLabels.usesEvidence },
    { from: "assessment", to: "br1", label: ontologyRelationLabels.hasBlockingReason },
    { from: "br1", to: "rule", label: ontologyRelationLabels.triggeredBy },
    { from: "rule", to: "rv", label: ontologyRelationLabels.hasVersion },
    { from: "rv", to: "rc", label: ontologyRelationLabels.citesClause },
    { from: "br1", to: "ra", label: ontologyRelationLabels.hasRemediation },
  ];

  const nodeMap = Object.fromEntries(nodes.map((n) => [n.id, n]));
  const selected = selectedNode ? nodeMap[selectedNode] : null;
  const typeColors: Record<string, string> = {
    MNPCase: "#dbeafe",
    EligibilityAssessment: "#ede9fe",
    EvidenceRecord: "#cffafe",
    BlockingReason: "#fee2e2",
    EligibilityRule: "#ede9fe",
    RuleVersion: "#f3e8ff",
    RegulatoryClause: "#e0e7ff",
    RemediationAction: "#d1fae5",
  };

  return (
    <div className="flex flex-col lg:flex-row gap-4 min-w-0">
      <div className="flex-1 bg-white border border-slate-200 rounded-lg overflow-x-auto min-w-0">
        <svg viewBox="0 0 980 320" className="w-full min-w-[720px]" style={{ height: 320 }}>
          <defs>
            <marker id="arrow-trace" markerWidth="8" markerHeight="8" refX="7" refY="3" orient="auto">
              <path d="M0,0 L0,6 L8,3 z" fill="#94a3b8" />
            </marker>
          </defs>
          {edges.map((e, i) => {
            const from = nodeMap[e.from];
            const to = nodeMap[e.to];
            if (!from || !to) return null;
            const mx = (from.x + to.x) / 2;
            const my = (from.y + to.y) / 2;
            return (
              <g key={i}>
                <line
                  x1={from.x + 70}
                  y1={from.y + 14}
                  x2={to.x}
                  y2={to.y + 14}
                  stroke="#cbd5e1"
                  strokeWidth="1.5"
                  markerEnd="url(#arrow-trace)"
                />
                <text x={mx + 35} y={my + 10} fontSize="9" fill="#94a3b8" textAnchor="middle">
                  {e.label}
                </text>
              </g>
            );
          })}
          {nodes.map((n) => (
            <g
              key={n.id}
              onClick={() => setSelectedNode(selectedNode === n.id ? null : n.id)}
              className="cursor-pointer"
              style={{ userSelect: "none" }}
            >
              <rect
                x={n.x}
                y={n.y}
                width={140}
                height={28}
                rx={5}
                fill={typeColors[n.type] || "#f8fafc"}
                stroke={selectedNode === n.id ? n.color : "#e2e8f0"}
                strokeWidth={selectedNode === n.id ? 2 : 1}
              />
              <text
                x={n.x + 70}
                y={n.y + 12}
                fontSize="9"
                fill={n.color}
                fontWeight="600"
                textAnchor="middle"
              >
                {t(ontologyClassLabels, n.type, n.type)}
              </text>
              <text x={n.x + 70} y={n.y + 22} fontSize="8" fill="#475569" textAnchor="middle">
                {n.label.length > 14 ? `${n.label.slice(0, 14)}…` : n.label}
              </text>
            </g>
          ))}
        </svg>
      </div>
      {selected && (
        <div className="w-full lg:w-56 bg-white border border-slate-200 rounded-lg p-4 text-xs flex-shrink-0">
          <div className="font-semibold text-slate-700 mb-3">
            {t(ontologyClassLabels, selected.type, selected.type)}
          </div>
          <div className="space-y-2">
            <div>
              <span className="text-slate-400">名称：</span>
              <span className="text-slate-700 break-all">{selected.label}</span>
            </div>
            <div>
              <span className="text-slate-400">类型：</span>
              <span className="text-slate-700">
                {t(ontologyClassLabels, selected.type, selected.type)}
              </span>
            </div>
          </div>
          <button
            type="button"
            onClick={() => setSelectedNode(null)}
            className="mt-3 text-slate-400 hover:text-slate-600 text-[10px]"
          >
            关闭
          </button>
        </div>
      )}
    </div>
  );
}

export function AssessmentResult({
  caseId,
  onBack,
}: {
  caseId: string;
  onBack: () => void;
}) {
  const [detail, setDetail] = useState<AssessmentDetail | null>(null);
  const [historical, setHistorical] = useState<AssessmentDetail | null>(null);
  const [activeTab, setActiveTab] = useState("timeline");

  useEffect(() => {
    void (async () => {
      const [d, h] = await Promise.all([
        getAssessmentDetail(caseId),
        getHistoricalAssessment(caseId),
      ]);
      setDetail(d);
      setHistorical(h);
    })();
  }, [caseId]);

  if (!detail) {
    return (
      <div className="p-6 text-sm text-slate-400">{ui.loading}</div>
    );
  }

  const isEligible = detail.decision === "ELIGIBLE";
  const isBlocked = detail.decision === "BLOCKED";
  const isCase06 = detail.caseId === "CASE-06";
  const isCase07 = detail.caseId === "CASE-07";
  const decisionZh = t(decisionLabels, detail.decision);

  const timelineSteps = detail.pipelineSteps.map((step) => {
    let status: StepStatus = step.status ?? "PASSED";
    if (step.id === "rule-engine" && detail.ruleResults.some((r) => r.status === "FAIL")) {
      status = "FAILED";
    }
    return { ...step, status };
  });

  return (
    <div className="flex flex-col h-full min-w-0 overflow-x-hidden">
      <div className="bg-white border-b border-slate-200 px-6 py-3 flex items-center gap-3 flex-shrink-0 min-w-0">
        <button
          type="button"
          onClick={onBack}
          className="flex items-center gap-1.5 text-xs text-slate-500 hover:text-slate-700 transition-colors"
        >
          <ChevronLeft size={14} /> 返回案件列表
        </button>
        <div className="w-px h-4 bg-slate-200" />
        <span className="text-xs text-slate-500">{t(caseLabels, detail.caseId)}</span>
        <ArrowRight size={12} className="text-slate-300" />
        <span className="text-xs text-slate-600 font-medium truncate">{detail.title}</span>
      </div>

      <div className="flex-1 overflow-y-auto overflow-x-hidden min-w-0">
        <div
          className={cn(
            "border-b px-6 py-5",
            isEligible
              ? "bg-emerald-50 border-emerald-100"
              : isBlocked
                ? "bg-red-50 border-red-100"
                : "bg-amber-50 border-amber-100",
          )}
        >
          <div className="flex flex-col lg:flex-row lg:items-start justify-between gap-4 min-w-0">
            <div className="flex items-center gap-4 min-w-0">
              <div
                className={cn(
                  "w-12 h-12 rounded-xl flex items-center justify-center flex-shrink-0",
                  isEligible ? "bg-emerald-600" : isBlocked ? "bg-red-600" : "bg-amber-500",
                )}
              >
                {isEligible ? (
                  <CheckCircle2 size={24} className="text-white" />
                ) : isBlocked ? (
                  <XCircle size={24} className="text-white" />
                ) : (
                  <AlertTriangle size={24} className="text-white" />
                )}
              </div>
              <div className="min-w-0">
                <div className="flex flex-wrap items-center gap-3 mb-1">
                  <span
                    className={cn(
                      "text-2xl font-bold",
                      isEligible
                        ? "text-emerald-700"
                        : isBlocked
                          ? "text-red-700"
                          : "text-amber-700",
                    )}
                  >
                    {decisionZh}
                  </span>
                  <DecisionBadge decision={detail.decision} />
                </div>
                <div className="text-sm text-slate-600">
                  {detail.title} — {detail.scenario}
                </div>
              </div>
            </div>
            <div className="grid grid-cols-2 gap-x-6 gap-y-1 text-xs text-left lg:text-right flex-shrink-0">
              <span className="text-slate-400">案例编号</span>
              <span className="text-slate-700">{t(caseLabels, detail.caseId)}</span>
              <span className="text-slate-400">{ui.assessmentTime}</span>
              <span className="text-slate-700">{formatTime(detail.assessmentTime)}</span>
              <span className="text-slate-400">{ui.executionCount}</span>
              <span className="text-slate-700">{detail.executionCount}</span>
              <span className="text-slate-400">{ui.publicationStatus}</span>
              <span
                className={cn(
                  detail.publicationStatus === "PUBLISHABLE"
                    ? "text-emerald-600"
                    : "text-amber-600",
                )}
              >
                {t(publicationStatusLabels, detail.publicationStatus)}
              </span>
            </div>
          </div>
        </div>

        {isCase06 && (
          <div className="px-6 pt-4 space-y-3">
            <div className="bg-emerald-50 border border-emerald-200 rounded-lg p-4">
              <div className="text-xs font-semibold text-emerald-800 mb-1">
                {ui.historicalVersion}（120 天）
              </div>
              <div className="text-sm text-emerald-700">
                {detail.historicalAssessment?.note ??
                  historical?.currentAssessmentNote ??
                  "历史规则版本要求 120 天，结论为可携转。"}
              </div>
              <div className="mt-2">
                <DecisionBadge decision={"ELIGIBLE" as Decision} />
                <span className="ml-2 text-xs text-emerald-600">
                  评估时间：
                  {formatTime(
                    detail.historicalAssessment?.assessmentTime ??
                      historical?.assessmentTime ??
                      "2026-05-15T00:00:00Z",
                  )}
                </span>
              </div>
            </div>
            <div className="bg-red-50 border border-red-200 rounded-lg p-4">
              <div className="text-xs font-semibold text-red-800 mb-1">
                {ui.currentVersion}（180 天）
              </div>
              <div className="text-sm text-red-700">
                {detail.currentAssessmentNote ?? "当前规则版本要求 180 天，结论为不可携转。"}
              </div>
              <div className="mt-2">
                <DecisionBadge decision={detail.decision} />
                <span className="ml-2 text-xs text-red-600">
                  评估时间：{formatTime(detail.assessmentTime)}
                </span>
              </div>
            </div>
          </div>
        )}

        {isCase07 && (
          <div className="px-6 pt-4">
            <div className="bg-amber-50 border border-amber-200 rounded-lg p-4 flex items-start gap-2">
              <AlertTriangle size={16} className="text-amber-600 flex-shrink-0 mt-0.5" />
              <div className="text-xs text-amber-800 leading-relaxed">
                <strong>重要说明：</strong>
                {ui.eligibilityVsProcessNote}
                本案例资格结论为「可携转」，但授权码已过期，流程状态为「不能继续」。二者含义不同，请分别查看资格结论与流程状态。
              </div>
            </div>
          </div>
        )}

        <div className="bg-white border-b border-slate-200 px-6 flex-shrink-0 overflow-x-auto">
          <div className="flex gap-0 min-w-max">
            {TABS.map((tab) => (
              <button
                key={tab.id}
                type="button"
                onClick={() => setActiveTab(tab.id)}
                className={cn(
                  "px-4 py-3 text-sm border-b-2 transition-colors whitespace-nowrap",
                  activeTab === tab.id
                    ? "border-blue-600 text-blue-700 font-medium"
                    : "border-transparent text-slate-500 hover:text-slate-700",
                )}
              >
                {tab.label}
              </button>
            ))}
          </div>
        </div>

        <div className="p-6 min-w-0">
          {activeTab === "timeline" && (
            <div className="space-y-2">
              <SectionHeader title="处理时间线" />
              {timelineSteps.map((step, i) => (
                <div
                  key={step.id}
                  className="flex items-center gap-4 bg-white border border-slate-200 rounded-lg px-4 py-3 min-w-0"
                >
                  <StatusBadge status={step.status ?? "PASSED"} />
                  <div className="flex-1 min-w-0">
                    <span className="text-sm font-medium text-slate-700">{step.label}</span>
                    <span className="ml-2 text-xs text-slate-400">{step.description}</span>
                  </div>
                  <span className="text-xs text-slate-400 flex-shrink-0">
                    {(i * 42 + 18).toString().padStart(4, "0")} 毫秒
                  </span>
                </div>
              ))}
            </div>
          )}

          {activeTab === "validation" && (
            <div className="grid grid-cols-1 md:grid-cols-3 gap-4">
              {[
                {
                  title: "结构化输入校验",
                  status: "PASSED",
                  checks: 24,
                  violations: 0,
                  note: "所有必填字段已提供，数据类型符合数据规范第一版。",
                },
                {
                  title: "输入图约束校验",
                  status: "PASSED",
                  checks: 18,
                  violations: 0,
                  note: "输入图满足全部约束要求。",
                },
                {
                  title: "评估图约束校验",
                  status: "PASSED",
                  checks: 13,
                  violations: 0,
                  note: "评估图输出完整，资格结论与阻塞原因节点均已生成。",
                },
              ].map((v) => (
                <div key={v.title} className="bg-white border border-slate-200 rounded-lg p-4">
                  <div className="flex items-start justify-between mb-3">
                    <div>
                      <div className="text-sm font-semibold text-slate-700 mb-1">{v.title}</div>
                      <StatusBadge status={v.status} />
                    </div>
                  </div>
                  <div className="grid grid-cols-2 gap-2 text-xs mb-3">
                    <div className="bg-slate-50 rounded p-2 text-center">
                      <div className="text-lg font-bold text-slate-700">{v.checks}</div>
                      <div className="text-slate-400">检查项</div>
                    </div>
                    <div className="bg-slate-50 rounded p-2 text-center">
                      <div
                        className={cn(
                          "text-lg font-bold",
                          v.violations === 0 ? "text-emerald-600" : "text-red-600",
                        )}
                      >
                        {v.violations}
                      </div>
                      <div className="text-slate-400">违规项</div>
                    </div>
                  </div>
                  <p className="text-xs text-slate-500 leading-relaxed">{v.note}</p>
                </div>
              ))}
            </div>
          )}

          {activeTab === "evidence" && (
            <div className="min-w-0">
              <SectionHeader title="证据表" sub={`${detail.evidence.length} 条证据`} />
              <div className="bg-white border border-slate-200 rounded-lg overflow-x-auto">
                <table className="w-full text-xs min-w-[720px]">
                  <thead>
                    <tr className="border-b border-slate-200 bg-slate-50">
                      {[
                        "证据编号",
                        "证据类型",
                        "数据来源",
                        "状态",
                        "生成时间",
                        "有效期至",
                        "观测摘要",
                      ].map((h) => (
                        <th
                          key={h}
                          className="px-4 py-2.5 text-left font-semibold text-slate-500 text-[10px]"
                        >
                          {h}
                        </th>
                      ))}
                    </tr>
                  </thead>
                  <tbody>
                    {detail.evidence.map((ev, i) => (
                      <tr
                        key={ev.evidenceId}
                        className={cn(
                          "border-b border-slate-100",
                          i % 2 === 0 ? "" : "bg-slate-50/50",
                        )}
                      >
                        <td className="px-4 py-2.5 text-slate-600">
                          {t(evidenceTypeLabels, ev.evidenceType)}-{i + 1}
                        </td>
                        <td className="px-4 py-2.5 text-violet-700">
                          {t(evidenceTypeLabels, ev.evidenceType)}
                        </td>
                        <td className="px-4 py-2.5 text-slate-500">
                          {t(dataSourceLabels, ev.sourceSystem, ev.sourceSystem)}
                        </td>
                        <td className="px-4 py-2.5">
                          <StatusBadge status={ev.status} />
                        </td>
                        <td className="px-4 py-2.5 text-slate-500">
                          {formatTime(ev.generatedAt)}
                        </td>
                        <td className="px-4 py-2.5 text-slate-500">
                          {formatTime(ev.validUntil)}
                        </td>
                        <td className="px-4 py-2.5 text-slate-600 max-w-xs truncate">
                          {ev.valueSummary}
                        </td>
                      </tr>
                    ))}
                  </tbody>
                </table>
              </div>
            </div>
          )}

          {activeTab === "rules" && (
            <div className="min-w-0">
              <SectionHeader title="规则执行表" />
              <div className="bg-white border border-slate-200 rounded-lg overflow-x-auto">
                <table className="w-full text-xs min-w-[640px]">
                  <thead>
                    <tr className="border-b border-slate-200 bg-slate-50">
                      {["规则名称", "版本", "执行结果", "生效时间", "失效时间", "原因"].map(
                        (h) => (
                          <th
                            key={h}
                            className="px-4 py-2.5 text-left font-semibold text-slate-500 text-[10px]"
                          >
                            {h}
                          </th>
                        ),
                      )}
                    </tr>
                  </thead>
                  <tbody>
                    {detail.ruleResults.map((r, i) => (
                      <tr
                        key={`${r.ruleId}-${r.version}`}
                        className={cn(
                          "border-b border-slate-100",
                          i % 2 === 0 ? "" : "bg-slate-50/50",
                        )}
                      >
                        <td className="px-4 py-2.5 text-violet-700">
                          {t(ruleLabels, r.ruleId)}
                        </td>
                        <td className="px-4 py-2.5 text-slate-500">{r.version}</td>
                        <td className="px-4 py-2.5">
                          <StatusBadge status={r.status} />
                        </td>
                        <td className="px-4 py-2.5 text-slate-500">
                          {r.effectiveFrom ? formatTime(r.effectiveFrom).slice(0, 10) : "—"}
                        </td>
                        <td className="px-4 py-2.5 text-slate-400">
                          {r.effectiveTo ? formatTime(r.effectiveTo).slice(0, 10) : "—"}
                        </td>
                        <td className="px-4 py-2.5 text-slate-500">
                          {r.reasonCode
                            ? t(blockingReasonLabels, r.reasonCode, r.reasonCode)
                            : "—"}
                        </td>
                      </tr>
                    ))}
                  </tbody>
                </table>
              </div>
            </div>
          )}

          {activeTab === "blocking" && (
            <div className="space-y-4">
              <SectionHeader
                title="阻塞原因"
                sub={
                  detail.blockingReasonDetails.length === 0
                    ? "无阻塞原因"
                    : `${detail.blockingReasonDetails.length} 个阻塞原因`
                }
              />
              {detail.blockingReasonDetails.length === 0 && (
                <div className="bg-emerald-50 border border-emerald-200 rounded-lg p-6 text-center">
                  <CheckCircle2 size={32} className="text-emerald-500 mx-auto mb-2" />
                  <div className="text-sm font-medium text-emerald-700">
                    所有规则均通过，无资格阻塞原因
                  </div>
                  {isCase07 && (
                    <div className="text-xs text-emerald-600 mt-2">
                      流程侧仍可能因授权码过期而不能继续，请查看「流程状态」。
                    </div>
                  )}
                </div>
              )}
              {detail.blockingReasonDetails.map((br) => (
                <BlockingReasonCard
                  key={br.reasonCode + br.ruleId}
                  code={br.reasonCode}
                  description={br.description}
                  evidence={br.evidenceIds}
                  ruleId={br.ruleId}
                  ruleVersion={br.ruleVersion}
                  clause={br.regulatoryClause}
                  action={br.actionCode}
                />
              ))}
            </div>
          )}

          {activeTab === "process" && (
            <div className="space-y-4">
              <SectionHeader title={ui.processStatus} />
              <div className="grid grid-cols-1 md:grid-cols-2 gap-4">
                <div className="bg-white border border-slate-200 rounded-lg p-4 space-y-3">
                  <div className="text-xs font-semibold text-slate-500">{ui.decision}</div>
                  <div className="flex items-center gap-2">
                    <DecisionBadge decision={detail.decision} />
                    <span className="text-sm text-slate-700">
                      {isEligible
                        ? "用户满足所有资格条件"
                        : isBlocked
                          ? "用户当前不符合携转资格"
                          : "需要人工审核"}
                    </span>
                  </div>
                  <div className="text-xs text-slate-500 bg-slate-50 rounded p-2 leading-relaxed">
                    {isEligible
                      ? "资格已通过：从资格维度可继续推进携转流程。"
                      : isBlocked
                        ? "资格未通过：需先解除阻塞条件后重新申请。"
                        : "资格待定：需人工核查相关证据。"}
                  </div>
                </div>
                <div className="bg-white border border-slate-200 rounded-lg p-4 space-y-3">
                  <div className="text-xs font-semibold text-slate-500">流程步骤</div>
                  <div className="space-y-2">
                    <div className="flex justify-between text-xs gap-2">
                      <span className="text-slate-500">当前步骤</span>
                      <span className="text-slate-700 text-right">
                        {t(
                          processStepLabels,
                          detail.process?.currentStep ?? "",
                          String(detail.process?.currentStep ?? "—"),
                        )}
                      </span>
                    </div>
                    <div className="flex justify-between text-xs gap-2">
                      <span className="text-slate-500">下一步骤</span>
                      <span className="text-slate-700 text-right">
                        {detail.process?.nextStep
                          ? t(processStepLabels, detail.process.nextStep, String(detail.process.nextStep))
                          : "—"}
                      </span>
                    </div>
                    <div className="flex justify-between text-xs gap-2">
                      <span className="text-slate-500">能否继续</span>
                      <span
                        className={cn(
                          "font-medium",
                          detail.process?.canAdvance ? "text-emerald-600" : "text-red-600",
                        )}
                      >
                        {detail.process?.canAdvance ? ui.canAdvance : ui.cannotAdvance}
                      </span>
                    </div>
                    <div className="flex justify-between text-xs gap-2">
                      <span className="text-slate-500">授权码状态</span>
                      {detail.process?.authorizationCode ? (
                        <StatusBadge status={detail.process.authorizationCode.status} />
                      ) : (
                        <span className="text-slate-400">未签发</span>
                      )}
                    </div>
                  </div>
                  {detail.process?.processBlockingReasons?.map((p) => (
                    <div
                      key={p.code}
                      className="text-xs bg-red-50 border border-red-100 rounded p-2 text-red-700"
                    >
                      {p.message || t(blockingReasonLabels, p.code, p.code)}
                    </div>
                  ))}
                </div>
              </div>

              {isCase07 && (
                <div className="bg-amber-50 border border-amber-200 rounded-lg p-4">
                  <div className="flex items-start gap-2">
                    <AlertTriangle size={15} className="text-amber-600 flex-shrink-0 mt-0.5" />
                    <div className="text-xs text-amber-700 leading-relaxed">
                      <strong>注意：</strong>
                      {ui.eligibilityVsProcessNote}
                      当前资格结论为「{decisionZh}」，但授权码状态为「
                      {t(
                        authCodeStatusLabels,
                        detail.process?.authorizationCode?.status ?? "EXPIRED",
                      )}
                      」，流程「{ui.cannotAdvance}」。资格通过并不等于流程可以继续。
                    </div>
                  </div>
                </div>
              )}

              {!isEligible && !isCase07 && (
                <div className="bg-amber-50 border border-amber-200 rounded-lg p-4">
                  <div className="flex items-start gap-2">
                    <AlertTriangle size={15} className="text-amber-600 flex-shrink-0 mt-0.5" />
                    <div className="text-xs text-amber-700">
                      <strong>注意：</strong>
                      {ui.eligibilityVsProcessNote}
                      当前案件属于资格未通过，需先解除阻塞条件。
                    </div>
                  </div>
                </div>
              )}
            </div>
          )}

          {activeTab === "trace" && (
            <div className="min-w-0">
              <SectionHeader
                title="追溯图"
                sub="案件 → 资格评估 → 证据 → 阻塞原因 → 规则 → 版本 → 条款 → 处理动作"
              />
              <TraceGraph detail={detail} />
            </div>
          )}
        </div>
      </div>
    </div>
  );
}
