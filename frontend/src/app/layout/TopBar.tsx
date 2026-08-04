import { Menu, Play } from "lucide-react";
import { useNavigate } from "react-router";
import { useRunExample, useSystemStatus } from "../query/hooks/useAppQueries";
import { ui } from "../i18n/zh-CN";

export function TopBar({ onToggleSidebar }: { onToggleSidebar?: () => void }) {
  const navigate = useNavigate();
  const system = useSystemStatus();
  const run = useRunExample();
  const online = system.isSuccess && system.data.reachable && system.data.databaseReady;
  const runDemo = () => run.mutate("CASE-03", { onSuccess: (assessment) => navigate(`/assessments/${assessment.executionId}`) });
  return <header className="flex min-h-12 flex-shrink-0 items-center gap-3 overflow-x-hidden border-b border-slate-200 bg-white px-4">
    <button type="button" onClick={onToggleSidebar} className="flex h-8 w-8 flex-shrink-0 items-center justify-center rounded-md text-slate-500 hover:bg-slate-100" aria-label="切换导航"><Menu size={16} /></button>
    <div className="flex min-w-0 flex-1 flex-wrap items-center gap-x-4 gap-y-1 text-xs text-slate-500">
      <span>后端服务：<span className={online ? "font-medium text-emerald-600" : "font-medium text-red-600"}>{online ? "可访问" : system.isLoading ? "检查中" : "暂不可用"}</span></span>
      <span>数据库：<span className={system.data?.databaseReady ? "font-medium text-emerald-600" : "font-medium text-red-600"}>{system.data?.databaseReady ? "已就绪" : "未就绪"}</span></span>
      {system.data && <><span>接口版本：<span className="font-medium text-slate-700">{system.data.apiVersion}</span></span><span>数据规范：<span className="font-medium text-slate-700">{system.data.schemaVersion}</span></span></>}
    </div>
    <button type="button" disabled={run.isPending || !online} onClick={runDemo} className="flex flex-shrink-0 items-center gap-1.5 rounded-md bg-blue-600 px-3 py-1.5 text-xs font-medium text-white transition-colors hover:bg-blue-700 disabled:cursor-not-allowed disabled:opacity-50"><Play size={11} />{run.isPending ? "运行中" : ui.runDemo}</button>
  </header>;
}
