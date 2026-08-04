import { ChevronRight, Clock, Play } from "lucide-react";
import { useNavigate } from "react-router";
import { ApiErrorState, EmptyState, MutationStatus, PageSkeleton } from "../components/dataStates";
import { MetricCard } from "../components/MetricCard";
import { SectionHeader } from "../components/SectionHeader";
import { DecisionBadge } from "../components/StatusBadges";
import { caseLabels, translateOrUnknown, ui } from "../i18n/zh-CN";
import { useCases, useDashboard, useRunExample } from "../query/hooks/useAppQueries";

function formatTime(value: string) { return value ? value.replace("T", " ").replace("Z", "").slice(0, 16) : "尚未运行"; }

export function SystemOverview() {
  const navigate = useNavigate();
  const dashboard = useDashboard();
  const cases = useCases();
  const run = useRunExample();
  if (dashboard.isLoading || cases.isLoading) return <PageSkeleton />;
  if (dashboard.isError) return <ApiErrorState error={dashboard.error} onRetry={() => void dashboard.refetch()} />;
  if (cases.isError) return <ApiErrorState error={cases.error} onRetry={() => void cases.refetch()} />;
  if (!dashboard.data || !cases.data) return <EmptyState />;
  const stats = dashboard.data.ontology;
  const openCase = (caseId: string, executionId: string | null) => {
    if (executionId) { navigate(`/assessments/${executionId}`); return; }
    if (!window.confirm("该案例尚未运行，是否现在提交后端执行？")) return;
    run.mutate(caseId, { onSuccess: (assessment) => navigate(`/assessments/${assessment.executionId}`) });
  };
  return <div className="min-w-0 max-w-full space-y-6 overflow-x-hidden p-6">
    <section><SectionHeader title="真实数据统计" sub={dashboard.isFetching ? "正在刷新" : "来自后端当前数据"} /><div className="grid grid-cols-2 gap-3 sm:grid-cols-3 xl:grid-cols-6"><MetricCard label="本体模块" value={stats.modules} /><MetricCard label="本体类" value={stats.classes} /><MetricCard label="对象属性" value={stats.objectProperties} /><MetricCard label="数据属性" value={stats.dataProperties} /><MetricCard label="约束形状" value={stats.shapes} /><MetricCard label="资格规则" value={stats.rules} /></div></section>
    <section><SectionHeader title="运行数据" /><div className="grid grid-cols-2 gap-3 md:grid-cols-4"><MetricCard label="能力问题" value={stats.competencyQuestions} /><MetricCard label="示例案例" value={dashboard.data.examples} /><MetricCard label="执行记录" value={dashboard.data.executions} /><MetricCard label="当前案例" value={dashboard.data.exampleCaseIds.length} /></div></section>
    <section><SectionHeader title="最新案件状态" sub="按每个案例最新评估时间汇总" /><div className="grid grid-cols-2 gap-3 md:grid-cols-4"><MetricCard label="已运行案例" value={dashboard.data.latestCaseStates.total} /><MetricCard label="最新可携转" value={dashboard.data.latestCaseStates.eligible} color="text-emerald-600" /><MetricCard label="最新不可携转" value={dashboard.data.latestCaseStates.blocked} color="text-red-600" /><MetricCard label="最新需人工复核" value={dashboard.data.latestCaseStates.manualReview} color="text-amber-600" /></div></section>
    <section><SectionHeader title="示例案件" sub="点击已有结果查看详情；尚未运行的案例将提交后端执行" />{cases.data.length === 0 ? <EmptyState message="暂无示例案例" /> : <div className="grid grid-cols-1 gap-3 md:grid-cols-2 xl:grid-cols-3">{cases.data.map((item) => <button key={item.id} type="button" disabled={run.isPending} onClick={() => openCase(item.id, item.latestExecutionId)} className="group min-w-0 rounded-lg border border-slate-200 bg-white p-4 text-left transition-all hover:border-blue-300 hover:shadow-sm disabled:opacity-60"><div className="mb-2 flex items-start justify-between gap-2"><span className="rounded bg-slate-50 px-1.5 py-0.5 text-xs text-slate-500">{translateOrUnknown(caseLabels, item.id, ui.unknownCase)}</span>{item.hasHistory ? <DecisionBadge decision={item.decision} /> : <span className="text-xs text-slate-400">尚未运行</span>}</div><div className="mb-3 min-h-10 text-xs leading-relaxed text-slate-500">{item.scenario}</div><div className="flex items-center gap-2 text-[11px] text-slate-400"><Clock size={10} /><span>{formatTime(item.assessmentTime)}</span><span className="ml-auto flex items-center gap-1 text-blue-600">{item.hasHistory ? <><span>查看详情</span><ChevronRight size={10} /></> : <><Play size={10} /><span>运行案例</span></>}</span></div></button>)}</div>}<div className="mt-3"><MutationStatus pending={run.isPending} error={run.error} /></div></section>
  </div>;
}
