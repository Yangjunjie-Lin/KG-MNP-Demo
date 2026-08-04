import { useMutation } from "@tanstack/react-query";
import { Play } from "lucide-react";
import { useEffect, useState } from "react";
import { ApiErrorState, EmptyState, MutationStatus, PageSkeleton } from "../components/dataStates";
import {
  authCodeStatusLabels,
  blockingReasonLabels,
  caseLabels,
  contractStatusLabels,
  dataSourceLabels,
  decisionLabels,
  evidenceStatusLabels,
  evidenceTypeLabels,
  processStepLabels,
  regulatoryClauseLabels,
  remediationActionLabels,
  ruleLabels,
  translateOrUnknown,
  ui,
} from "../i18n/zh-CN";
import { useCases, useCompetencyQuestions } from "../query/hooks/useAppQueries";
import { executeCompetencyQuestion } from "../services/competencyService";
import { cn } from "../utils/cn";

const columnLabels: Record<string, string> = {
  decision: "资格结论", reasonCode: "阻塞原因", ruleId: "资格规则", actionCode: "处理动作",
  authStatus: "授权码状态", caseId: "案例", status: "状态", version: "版本", ruleVersion: "规则版本",
  clause: "监管条款", clauseId: "监管条款", sourceSystem: "数据来源", generatedAt: "生成时间", validUntil: "有效期",
  currentStep: "当前步骤", stepCode: "当前步骤", canAdvance: "能否继续", contractStatus: "合约状态", contractEndTime: "合约结束时间",
  evidence: "证据记录", evidenceType: "证据类型", evidenceStatus: "证据状态", effectiveFrom: "生效时间",
  eventTypeCode: "流程阻塞原因", eventTime: "事件时间", issuedAt: "签发时间", service: "关联业务",
  subscriptionStatus: "订阅状态", contract: "服务合约", contractEnd: "合约结束时间", assessmentTime: "评估时间",
  assessment: "资格评估", oldVersion: "历史版本", newVersion: "当前版本", requiresReassessment: "是否需要重新评估",
};

function ordinal(id: string) { const n = Number(id.replace(/\D/g, "")); const values = ["", "一", "二", "三", "四", "五", "六", "七", "八", "九", "十", "十一", "十二", "十三", "十四", "十五"]; return values[n] ? `问题${values[n]}` : "能力问题"; }
function displayValue(column: string, value: unknown): string {
  if (value == null || value === "") return "暂无信息";
  if (typeof value === "boolean" || value === "true" || value === "false") {
    return value === true || value === "true" ? "是" : "否";
  }
  const raw = String(value);
  if (raw.startsWith("http://") || raw.startsWith("https://")) {
    const resourceLabels: Record<string, string> = {
      evidence: "证据记录", contract: "服务合约", service: "电信业务", assessment: "资格评估",
    };
    return resourceLabels[column] ?? "关联记录";
  }
  const maps = [caseLabels, decisionLabels, blockingReasonLabels, remediationActionLabels,
    regulatoryClauseLabels, ruleLabels, processStepLabels, authCodeStatusLabels,
    evidenceStatusLabels, evidenceTypeLabels, dataSourceLabels, contractStatusLabels];
  for (const map of maps) if (map[raw]) return map[raw];
  if (/^\d{4}-\d{2}-\d{2}T/u.test(raw)) return raw.replace("T", " ").replace(/\+00:00$|Z$/u, "");
  if (/[\u3400-\u9fff]/u.test(raw) || /^[\d\s.*+:/-]+$/u.test(raw)) return raw;
  return "未识别信息";
}

export function CompetencyQuestions() {
  const questions = useCompetencyQuestions(); const cases = useCases(); const [selectedId, setSelectedId] = useState(""); const [caseId, setCaseId] = useState("CASE-03");
  const mutation = useMutation({ mutationFn: ({ cqId, selectedCase }: { cqId: string; selectedCase: string }) => executeCompetencyQuestion(cqId, selectedCase) });
  useEffect(() => { if (!selectedId && questions.data?.[0]) { setSelectedId(questions.data[0].id); setCaseId(questions.data[0].exampleCase); } }, [questions.data, selectedId]);
  if (questions.isLoading || cases.isLoading) return <PageSkeleton />;
  if (questions.isError) return <ApiErrorState error={questions.error} onRetry={() => void questions.refetch()} />;
  if (cases.isError) return <ApiErrorState error={cases.error} onRetry={() => void cases.refetch()} />;
  const selected = questions.data?.find((item) => item.id === selectedId);
  if (!selected) return <EmptyState message="暂无能力问题" />;
  return <div className="flex h-full min-w-0"><aside className="w-64 flex-shrink-0 overflow-y-auto border-r bg-white"><div className="border-b p-3 text-xs font-semibold text-slate-500">能力问题（问题一至问题十五）</div>{questions.data?.map((item) => <button key={item.id} type="button" onClick={() => { setSelectedId(item.id); setCaseId(item.exampleCase); mutation.reset(); }} className={cn("w-full border-b p-3 text-left", selectedId === item.id ? "border-l-2 border-l-blue-500 bg-blue-50" : "hover:bg-slate-50")}><div className="mb-1 text-[10px] text-blue-600">{ordinal(item.id)}</div><div className="text-xs text-slate-700">{item.titleZh}</div></button>)}</aside><main className="min-w-0 flex-1 space-y-4 overflow-y-auto p-6"><section className="rounded-lg border border-slate-200 bg-white p-5"><div className="flex flex-wrap items-center gap-3"><h1 className="text-base font-semibold text-slate-800">{ordinal(selected.id)}：{selected.titleZh}</h1>{(questions.isFetching || cases.isFetching) && <span role="status" className="ml-auto text-xs text-slate-400">正在刷新查询目录…</span>}</div><div className="mt-3 text-xs text-slate-500">结果列由后端查询定义，界面只负责中文显示。</div></section><section className="rounded-lg border border-slate-200 bg-white p-5"><div className="mb-4 flex flex-wrap items-center gap-3"><select aria-label="查询案例" value={caseId} onChange={(event) => { setCaseId(event.target.value); mutation.reset(); }} className="rounded border border-slate-200 px-3 py-2 text-xs">{cases.data?.map((item) => <option key={item.id} value={item.id}>{translateOrUnknown(caseLabels, item.id, ui.unknownCase)}</option>)}</select><button type="button" disabled={mutation.isPending} onClick={() => mutation.mutate({ cqId: selected.id, selectedCase: caseId })} className="inline-flex items-center gap-1.5 rounded bg-blue-600 px-3 py-2 text-xs font-medium text-white"><Play size={12} />执行查询</button></div><MutationStatus pending={mutation.isPending} error={mutation.error} />{mutation.data && <div className="mt-4 overflow-x-auto" data-testid="competency-result">{mutation.data.rows.length ? <table className="w-full min-w-[480px] text-xs"><thead><tr className="border-b bg-slate-50">{mutation.data.columns.map((column) => <th key={column} className="px-3 py-2 text-left text-slate-500">{columnLabels[column] ?? "未识别字段"}</th>)}</tr></thead><tbody>{mutation.data.rows.map((row, index) => <tr key={index} className="border-b">{mutation.data.columns.map((column) => <td key={column} className="px-3 py-2 text-slate-700">{displayValue(column, row[column])}</td>)}</tr>)}</tbody></table> : <EmptyState message="查询已执行，暂无匹配结果" />}</div>}</section></main></div>;
}
