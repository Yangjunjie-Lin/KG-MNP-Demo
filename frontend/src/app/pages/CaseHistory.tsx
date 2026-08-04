import { Eye, Play, Search } from "lucide-react";
import { useMemo, useState } from "react";
import { useNavigate } from "react-router";
import { ApiErrorState, EmptyState, MutationStatus, PageSkeleton } from "../components/dataStates";
import { DecisionBadge } from "../components/StatusBadges";
import { caseLabels, translateOrUnknown, ui } from "../i18n/zh-CN";
import { useCases, useRunExample } from "../query/hooks/useAppQueries";

export function CaseHistory() {
  const navigate = useNavigate(); const query = useCases(); const run = useRunExample(); const [search, setSearch] = useState("");
  const items = useMemo(() => (query.data ?? []).filter((item) => !search || translateOrUnknown(caseLabels, item.id, ui.unknownCase).includes(search) || item.scenario.includes(search)), [query.data, search]);
  if (query.isLoading) return <PageSkeleton />;
  if (query.isError) return <ApiErrorState error={query.error} onRetry={() => void query.refetch()} />;
  const activate = (caseId: string, executionId: string | null) => {
    if (executionId) { navigate(`/assessments/${executionId}`); return; }
    if (!window.confirm("该案例尚未运行，是否现在提交后端执行？")) return;
    run.mutate(caseId, { onSuccess: (assessment) => navigate(`/assessments/${assessment.executionId}`) });
  };
  return <div className="min-w-0 space-y-4 overflow-x-hidden p-6"><div className="flex flex-wrap items-center gap-3"><div className="flex max-w-xs items-center gap-2 rounded-md border border-slate-200 bg-white px-3 py-2"><Search size={14} className="text-slate-400" /><input value={search} onChange={(event) => setSearch(event.target.value)} placeholder="搜索案例" className="min-w-0 flex-1 bg-transparent text-xs outline-none" /></div>{query.isFetching && <span role="status" className="text-xs text-slate-400">正在刷新案件历史…</span>}</div>{items.length === 0 ? <EmptyState /> : <div className="overflow-x-auto rounded-lg border border-slate-200 bg-white"><table className="w-full min-w-[720px] text-xs"><thead><tr className="border-b bg-slate-50 text-left text-slate-500"><th className="px-4 py-3">案例</th><th className="px-4 py-3">最新结论</th><th className="px-4 py-3">评估时间</th><th className="px-4 py-3">执行次数</th><th className="px-4 py-3">操作</th></tr></thead><tbody>{items.map((item) => <tr key={item.id} className="border-b border-slate-100 hover:bg-slate-50"><td className="px-4 py-3"><div className="font-medium text-slate-800">{translateOrUnknown(caseLabels, item.id, ui.unknownCase)}</div><div className="mt-1 text-[10px] text-slate-400">{item.scenario}</div></td><td className="px-4 py-3">{item.hasHistory ? <DecisionBadge decision={item.decision} /> : <span className="text-slate-400">尚未运行</span>}</td><td className="px-4 py-3 text-slate-500">{item.assessmentTime ? item.assessmentTime.slice(0, 19).replace("T", " ") : "尚未运行"}</td><td className="px-4 py-3 text-slate-500">{item.executionCount}</td><td className="px-4 py-3"><button type="button" disabled={run.isPending} onClick={() => activate(item.id, item.latestExecutionId)} className="inline-flex items-center gap-1 font-medium text-blue-600">{item.hasHistory ? <><Eye size={12} />查看详情</> : <><Play size={12} />运行案例</>}</button></td></tr>)}</tbody></table></div>}<MutationStatus pending={run.isPending} error={run.error} /></div>;
}
