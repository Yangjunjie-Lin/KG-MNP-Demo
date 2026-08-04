import { useQuery } from "@tanstack/react-query";
import { AlertTriangle, ArrowRight, CheckCircle2, ChevronLeft, XCircle } from "lucide-react";
import { useMemo, useState } from "react";
import { useNavigate, useParams } from "react-router";
import type { AssessmentViewModel, TraceNodeView } from "../../api/adapters/assessmentAdapter";
import { localName } from "../../api/adapters/guards";
import { isApiError } from "../../api/errors";
import { ApiErrorState, EmptyState, PageSkeleton, RetryButton } from "../components/dataStates";
import { DecisionBadge, StatusBadge } from "../components/StatusBadges";
import {
  authCodeStatusLabels,
  blockingReasonLabels,
  caseLabels,
  dataSourceLabels,
  decisionLabels,
  evidenceStatusLabels,
  evidenceTypeLabels,
  ontologyRelationLabels,
  pipelineStepLabels,
  processStepLabels,
  publicationStatusLabels,
  regulatoryClauseLabels,
  remediationActionLabels,
  ruleLabels,
  stepStatusLabels,
  traceEvidenceLabels,
  traceNodeTypeLabels,
  translateOrUnknown,
  ui,
} from "../i18n/zh-CN";
import { getAssessmentDetail } from "../services/assessmentService";
import { getCaseHistory } from "../services/caseService";
import { cn } from "../utils/cn";
import { useAssessment, useRules } from "../query/hooks/useAppQueries";

const tabs = [
  ["timeline", "处理时间线"], ["validation", "验证结果"], ["evidence", "证据表"],
  ["rules", "规则执行"], ["blocking", "阻塞原因"], ["process", "流程状态"], ["trace", "追溯图"],
] as const;

function formatTime(value?: string | null) { return value ? value.replace("T", " ").replace("Z", "").slice(0, 19) : "暂无信息"; }

function nodeSource(node: TraceNodeView): string {
  return [node.label, node.localId, node.id].filter(Boolean).join(" ");
}

function firstMappedCode(source: string, labels: Record<string, string>): string | undefined {
  return Object.keys(labels).find((code) => source.includes(code));
}

function traceNodeLabel(node: TraceNodeView, detail: AssessmentViewModel): string {
  const rawType = localName(node.type);
  const source = nodeSource(node);
  if (["MNPCase", "Case"].includes(rawType)) {
    return translateOrUnknown(caseLabels, detail.caseId, ui.unknownCase);
  }
  if (["EligibilityAssessment", "Assessment"].includes(rawType)) {
    return `${translateOrUnknown(caseLabels, detail.caseId, ui.unknownCase)}资格评估`;
  }
  if (["EvidenceRecord", "Evidence"].includes(rawType)) {
    const evidenceCode = node.evidenceType
      ?? (source.includes("BILL") ? "BILLING_BALANCE"
        : source.includes("CONTRACT") || source.includes("CTR") ? "CONTRACT_STATUS"
          : source.includes("ID") ? "IDENTITY_MATCH"
            : source.includes("NUM") ? "NUMBER_STATUS"
              : source.includes("PORT") ? "PORTING_HISTORY" : undefined);
    const mapped = evidenceCode ? traceEvidenceLabels[evidenceCode] : undefined;
    if (mapped) return mapped;
  }
  if (["BlockingReason", "Reason"].includes(rawType)) {
    const code = firstMappedCode(source, blockingReasonLabels);
    if (code) return blockingReasonLabels[code];
  }
  if (["EligibilityRule", "Rule"].includes(rawType)) {
    const code = firstMappedCode(source, ruleLabels);
    if (code) return ruleLabels[code];
  }
  if (["RegulatoryClause", "Clause"].includes(rawType)) {
    const clauseNumber = source.match(/(?:REG-MNP-CLAUSE-|Clause-)(\d+)/)?.[1];
    const code = clauseNumber ? `REG-MNP-CLAUSE-${clauseNumber}` : undefined;
    if (code && regulatoryClauseLabels[code]) return regulatoryClauseLabels[code];
  }
  if (["RemediationAction", "Action"].includes(rawType)) {
    const code = firstMappedCode(source, remediationActionLabels);
    if (code) return remediationActionLabels[code];
  }
  if (rawType === "BlockingDecision") return "不可携转结论";
  if (traceNodeTypeLabels[rawType] && ["AssessmentDependency", "RegulatoryDocument", "RuleVersion"].includes(rawType)) {
    return traceNodeTypeLabels[rawType];
  }
  console.warn("[trace] 未识别追溯节点", { id: node.id, label: node.label, type: node.type });
  return "未识别追溯节点";
}

function traceNodeTypeLabel(node: TraceNodeView): string {
  const rawType = localName(node.type);
  if (["EvidenceRecord", "Evidence"].includes(rawType)) return "证据";
  if (["BlockingReason", "Reason"].includes(rawType)) return "阻塞原因";
  if (traceNodeTypeLabels[rawType]) return traceNodeTypeLabels[rawType];
  return "未识别追溯节点";
}

function TraceGraph({ detail }: { detail: AssessmentViewModel }) {
  const [selected, setSelected] = useState<string | null>(null);
  const nodes = detail.traceNodes;
  const nodeMap = useMemo(() => Object.fromEntries(nodes.map((node) => [node.id, node])), [nodes]);
  const relationCounts = useMemo(() => {
    const counts = new Map<string, number>();
    detail.traceEdges.forEach((edge) => {
      counts.set(edge.source, (counts.get(edge.source) ?? 0) + 1);
      counts.set(edge.target, (counts.get(edge.target) ?? 0) + 1);
    });
    return counts;
  }, [detail.traceEdges]);
  if (!nodes.length) return <EmptyState message="暂无追溯图数据" />;
  const width = 860; const height = Math.max(420, Math.ceil(nodes.length / 5) * 86 + 80);
  const selectedNode = selected ? nodeMap[selected] : undefined;
  return <div className="space-y-3" data-testid="trace-graph"><div className="overflow-x-auto rounded-lg border border-slate-200 bg-white"><svg viewBox={`0 0 ${width} ${height}`} className="min-w-[760px]" style={{ height }}><defs><marker id="trace-arrow" markerWidth="8" markerHeight="8" refX="7" refY="3" orient="auto"><path d="M0,0 L0,6 L8,3 z" fill="#94a3b8" /></marker></defs>{detail.traceEdges.map((edge, index) => { const source = nodeMap[edge.source]; const target = nodeMap[edge.target]; if (!source || !target) return null; const relation = translateOrUnknown(ontologyRelationLabels, localName(edge.relation), ui.unknownOntologyRelation); return <g key={`${edge.source}-${edge.target}-${index}`}><line x1={source.x + 120} y1={source.y + 18} x2={target.x} y2={target.y + 18} stroke="#cbd5e1" markerEnd="url(#trace-arrow)" /><text x={(source.x + target.x + 120) / 2} y={(source.y + target.y) / 2 + 8} textAnchor="middle" fontSize="8" fill="#64748b">{relation}</text></g>; })}{nodes.map((node) => { const label = traceNodeLabel(node, detail); const active = selected === node.id; return <g key={node.id} onClick={() => setSelected(active ? null : node.id)} className="cursor-pointer"><rect x={node.x} y={node.y} width="120" height="36" rx="4" fill={active ? "#dbeafe" : "#f8fafc"} stroke={active ? "#2563eb" : "#cbd5e1"} /><text x={node.x + 60} y={node.y + 22} textAnchor="middle" fontSize="10" fill="#334155">{label.length > 20 ? `${label.slice(0, 20)}…` : label}</text></g>; })}</svg></div>{selectedNode && <section className="rounded-lg border border-blue-200 bg-blue-50 p-4 text-xs text-slate-700" data-testid="trace-node-details"><h3 className="mb-3 text-sm font-semibold text-slate-800">追溯节点详情</h3><dl className="grid gap-2 md:grid-cols-3"><div><dt className="text-slate-500">节点类型</dt><dd className="font-medium">{traceNodeTypeLabel(selectedNode)}</dd></div><div><dt className="text-slate-500">节点名称</dt><dd className="font-medium">{traceNodeLabel(selectedNode, detail)}</dd></div><div><dt className="text-slate-500">关系数量</dt><dd className="font-medium">{relationCounts.get(selectedNode.id) ?? 0}</dd></div></dl></section>}</div>;
}

interface RuleVersionComparison {
  historical: AssessmentViewModel;
  historicalRule: AssessmentViewModel["ruleResults"][number];
  currentRule: AssessmentViewModel["ruleResults"][number];
}

function findRuleVersionComparison(
  current: AssessmentViewModel,
  candidates: AssessmentViewModel[],
): RuleVersionComparison | null {
  const currentRules = new Map(current.ruleResults.map((rule) => [rule.ruleId, rule]));
  for (const historical of candidates) {
    for (const historicalRule of historical.ruleResults) {
      const currentRule = currentRules.get(historicalRule.ruleId);
      if (currentRule && currentRule.version !== historicalRule.version) {
        return { historical, historicalRule, currentRule };
      }
    }
  }
  return null;
}

function useRuleVersionHistory(detail?: AssessmentViewModel) {
  return useQuery({
    queryKey: ["case-history", detail?.caseId, detail?.executionId],
    enabled: !!detail,
    queryFn: async ({ signal }) => {
      if (!detail) return null;
      const history = await getCaseHistory(detail.caseId, signal);
      const historicalIds = history
        .filter((item) => item.executionId !== detail.executionId)
        .sort((left, right) => right.assessmentTime.localeCompare(left.assessmentTime))
        .map((item) => item.executionId)
        .filter(Boolean)
        .slice(0, 20);
      const candidates = await Promise.all(
        historicalIds.map((historicalId) => getAssessmentDetail(historicalId, signal)),
      );
      return findRuleVersionComparison(detail, candidates);
    },
  });
}

export function AssessmentResult() {
  const { executionId = "" } = useParams(); const navigate = useNavigate(); const query = useAssessment(executionId); const history = useRuleVersionHistory(query.data); const rules = useRules(); const [activeTab, setActiveTab] = useState<(typeof tabs)[number][0]>("timeline");
  if (query.isLoading) return <PageSkeleton />;
  if (isApiError(query.error) && query.error.status === 404) return <div role="alert" className="m-6 rounded border border-slate-200 bg-white p-10 text-center"><h1 className="mb-2 text-lg font-semibold text-slate-800">未找到相关评估</h1><p className="mb-4 text-sm text-slate-500">该评估记录不存在或已被移除，请检查地址。</p><RetryButton onRetry={() => void query.refetch()} /></div>;
  if (query.isError) return <ApiErrorState error={query.error} onRetry={() => void query.refetch()} />;
  if (!query.data) return <EmptyState message="未找到相关评估" />;
  const detail = query.data;
  const isEligible = detail.decision === "ELIGIBLE"; const isBlocked = detail.decision === "BLOCKED";
  const comparison = history.data;
  const historicalMinimum = comparison ? rules.data?.find((rule) => rule.ruleId === comparison.historicalRule.ruleId && rule.version === comparison.historicalRule.version)?.checkMinimum : null;
  const currentMinimum = comparison ? rules.data?.find((rule) => rule.ruleId === comparison.currentRule.ruleId && rule.version === comparison.currentRule.version)?.checkMinimum : null;
  const processHasData = !!(detail.process?.currentStep || detail.process?.authorizationCode || detail.process?.processBlockingReasons.length);
  const processCannotAdvanceAfterEligibility = isEligible && processHasData && !detail.process?.canAdvance;
  return <div className="flex h-full min-w-0 flex-col overflow-x-hidden"><div className="flex flex-shrink-0 items-center gap-3 border-b border-slate-200 bg-white px-6 py-3"><button type="button" onClick={() => navigate("/cases")} className="flex items-center gap-1 text-xs text-slate-500"><ChevronLeft size={14} />返回案件列表</button><span className="text-xs text-slate-500">{translateOrUnknown(caseLabels, detail.caseId, ui.unknownCase)}</span>{(query.isFetching || history.isFetching || rules.isFetching) && <span role="status" className="ml-auto text-xs text-slate-400">正在刷新评估详情…</span>}</div><div className="min-w-0 flex-1 overflow-y-auto">
    <section className={cn("border-b px-6 py-5", isEligible ? "border-emerald-100 bg-emerald-50" : isBlocked ? "border-red-100 bg-red-50" : "border-amber-100 bg-amber-50")}><div className="flex flex-wrap items-center gap-4"><div className={cn("flex h-12 w-12 items-center justify-center rounded-lg", isEligible ? "bg-emerald-600" : isBlocked ? "bg-red-600" : "bg-amber-500")}>{isEligible ? <CheckCircle2 className="text-white" /> : <XCircle className="text-white" />}</div><div><div className="text-xs text-slate-500">资格结论</div><DecisionBadge decision={detail.decision} /></div><div className="ml-auto text-right text-xs text-slate-500"><div>评估时间：{formatTime(detail.assessmentTime)}</div><div>发布状态：{translateOrUnknown(publicationStatusLabels, detail.publicationStatus, ui.unknownStatus)}</div></div></div></section>
    {history.isError && <ApiErrorState error={history.error} onRetry={() => void history.refetch()} />}
    {comparison && rules.isError && <ApiErrorState error={rules.error} onRetry={() => void rules.refetch()} />}
    {comparison && rules.isLoading && <section className="px-6 pt-4 text-xs text-slate-500">正在加载规则版本对比…</section>}
    {comparison && rules.data && <section className="grid gap-3 px-6 pt-4 md:grid-cols-2"><div className="rounded-lg border border-emerald-200 bg-emerald-50 p-4"><div className="mb-2 text-xs font-semibold text-emerald-800">历史规则版本 {comparison.historicalRule.version} / {historicalMinimum == null ? "门槛暂无信息" : `${historicalMinimum} 天`}</div><DecisionBadge decision={comparison.historical.decision} /><div className="mt-2 text-xs text-emerald-700">评估时间：{formatTime(comparison.historical.assessmentTime)}</div></div><div className="rounded-lg border border-red-200 bg-red-50 p-4"><div className="mb-2 text-xs font-semibold text-red-800">当前规则版本 {comparison.currentRule.version} / {currentMinimum == null ? "门槛暂无信息" : `${currentMinimum} 天`}</div><DecisionBadge decision={detail.decision} /><div className="mt-2 text-xs text-red-700">评估时间：{formatTime(detail.assessmentTime)}</div></div></section>}
    {processCannotAdvanceAfterEligibility && <section className="px-6 pt-4"><div className="flex items-start gap-2 rounded-lg border border-amber-200 bg-amber-50 p-4 text-xs text-amber-800"><AlertTriangle size={16} /><span>资格结论为{translateOrUnknown(decisionLabels, detail.decision, ui.unknownStatus)}；{detail.process?.authorizationCode ? `授权码${translateOrUnknown(authCodeStatusLabels, detail.process.authorizationCode.status, ui.unknownStatus)}，` : ""}流程不能继续。资格结论与流程状态分别来自后端。</span></div></section>}
    <div className="mt-4 overflow-x-auto border-y border-slate-200 bg-white px-6"><div className="flex min-w-max">{tabs.map(([id, label]) => <button key={id} type="button" onClick={() => setActiveTab(id)} className={cn("border-b-2 px-4 py-3 text-xs", activeTab === id ? "border-blue-600 font-medium text-blue-700" : "border-transparent text-slate-500")}>{label}</button>)}</div></div>
    <div className="min-w-0 p-6">
      {activeTab === "timeline" && (detail.timeline.length ? <div className="space-y-2">{detail.timeline.map((step) => <div key={step.id} className="flex items-center gap-3 rounded-lg border border-slate-200 bg-white px-4 py-3"><StatusBadge status={step.status ?? "PENDING"} /><span className="text-sm text-slate-700">{translateOrUnknown(stepStatusLabels, step.status, "处理状态未知")} · {translateOrUnknown(pipelineStepLabels, step.id, "处理步骤")}</span></div>)}</div> : <EmptyState message="暂无时间线数据" />)}
      {activeTab === "validation" && (detail.validationSteps.length ? <div className="grid gap-3 md:grid-cols-3">{detail.validationSteps.map((step) => <div key={step.id} className="rounded-lg border border-slate-200 bg-white p-4"><div className="mb-2 text-sm font-medium text-slate-700">{translateOrUnknown(pipelineStepLabels, step.id, "验证步骤")}</div><StatusBadge status={step.status ?? "PENDING"} /></div>)}</div> : <EmptyState message="暂无验证结果" />)}
      {activeTab === "evidence" && (detail.evidence.length ? <div className="overflow-x-auto rounded-lg border border-slate-200 bg-white"><table className="w-full min-w-[650px] text-xs"><thead><tr className="border-b bg-slate-50 text-left text-slate-500"><th className="px-3 py-2">证据类型</th><th className="px-3 py-2">来源</th><th className="px-3 py-2">状态</th><th className="px-3 py-2">生成时间</th><th className="px-3 py-2">有效期</th></tr></thead><tbody>{detail.evidence.map((item, index) => <tr key={`${item.evidenceId}-${index}`} className="border-b"><td className="px-3 py-2">{translateOrUnknown(evidenceTypeLabels, item.evidenceType, ui.unknownEvidence)}</td><td className="px-3 py-2">{translateOrUnknown(dataSourceLabels, item.sourceSystem, ui.unknownDataSource)}</td><td className="px-3 py-2">{translateOrUnknown(evidenceStatusLabels, item.status, ui.unknownStatus)}</td><td className="px-3 py-2">{formatTime(item.generatedAt)}</td><td className="px-3 py-2">{formatTime(item.validUntil)}</td></tr>)}</tbody></table></div> : <EmptyState message="暂无证据记录" />)}
      {activeTab === "rules" && (detail.ruleResults.length ? <div className="space-y-2">{detail.ruleResults.map((rule, index) => <div key={`${rule.ruleId}-${rule.version}-${index}`} className="flex flex-wrap items-center gap-3 rounded-lg border border-slate-200 bg-white p-4"><span className="text-sm font-medium text-violet-700">{translateOrUnknown(ruleLabels, rule.ruleId, ui.unknownRule)}</span><span className="text-xs text-slate-500">版本 {rule.version}</span><StatusBadge status={rule.status} /></div>)}</div> : <EmptyState message="暂无规则执行记录" />)}
      {activeTab === "blocking" && (detail.blockingReasonDetails.length ? <div className="space-y-3">{detail.blockingReasonDetails.map((reason, index) => <div key={`${reason.reasonCode}-${index}`} className="rounded-lg border border-red-200 bg-red-50 p-4"><div className="font-medium text-red-800">{translateOrUnknown(blockingReasonLabels, reason.reasonCode, ui.unknownStatus)}</div><div className="mt-2 grid gap-2 text-xs text-slate-600 md:grid-cols-3"><span>{translateOrUnknown(ruleLabels, reason.ruleId, ui.unknownRule)}</span><span>{translateOrUnknown(regulatoryClauseLabels, reason.regulatoryClause, ui.unknownClause)}</span><span>{translateOrUnknown(remediationActionLabels, reason.actionCode, ui.unknownAction)}</span></div></div>)}</div> : <EmptyState message="本次评估没有资格阻塞原因" />)}
      {activeTab === "process" && <div className="rounded-lg border border-slate-200 bg-white p-5"><div className="grid gap-3 text-sm md:grid-cols-3"><div><div className="text-xs text-slate-400">当前步骤</div>{translateOrUnknown(processStepLabels, detail.process?.currentStep, "流程步骤未知")}</div><div><div className="text-xs text-slate-400">是否可以继续</div><span className={detail.process?.canAdvance ? "text-emerald-700" : "text-red-700"}>{detail.process?.canAdvance ? "可以继续" : "不能继续"}</span></div><div><div className="text-xs text-slate-400">授权码状态</div>{translateOrUnknown(authCodeStatusLabels, detail.process?.authorizationCode?.status, "暂无授权码")}</div></div>{detail.process?.processBlockingReasons.length ? <div className="mt-4 border-t pt-3 text-xs text-red-700">{detail.process.processBlockingReasons.map((reason) => translateOrUnknown(blockingReasonLabels, reason.code, ui.unknownStatus)).join("、")}</div> : null}</div>}
      {activeTab === "trace" && <><div className="mb-3 flex items-center gap-2 text-xs text-slate-500">真实追溯关系：{detail.traceNodes.length} 个节点，{detail.traceEdges.length} 条边 <ArrowRight size={12} /></div><TraceGraph detail={detail} /></>}
    </div>
  </div></div>;
}
