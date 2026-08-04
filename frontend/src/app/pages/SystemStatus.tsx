import { ApiErrorState, EmptyState, PageSkeleton } from "../components/dataStates";
import { MetricCard } from "../components/MetricCard";
import { SectionHeader } from "../components/SectionHeader";
import { useSystemStatus } from "../query/hooks/useAppQueries";

const backendLabels: Record<string, string> = {
  rdf: "本地语义图谱",
};

function formatCheckedAt(value: string): string {
  const date = new Date(value);
  return Number.isNaN(date.getTime()) ? "暂无信息" : date.toLocaleString("zh-CN");
}

function yesNo(value: boolean): string {
  return value ? "是" : "否";
}

export function SystemStatus() {
  const query = useSystemStatus();

  if (query.isLoading) return <PageSkeleton />;
  if (query.isError) {
    return <ApiErrorState error={query.error} onRetry={() => void query.refetch()} />;
  }
  if (!query.data) return <EmptyState message="暂无系统状态信息" />;

  const status = query.data;
  const backendLabel = backendLabels[status.backend.toLowerCase()] ?? "后端类型未识别";

  return (
    <div className="min-w-0 space-y-5 overflow-x-hidden p-6">
      <div className="flex flex-wrap items-start justify-between gap-2">
        <SectionHeader title="系统状态" sub="实时监控" />
        {query.isFetching && !query.isLoading && (
          <span role="status" className="text-xs text-slate-400">
            正在刷新状态…
          </span>
        )}
      </div>

      <div className="grid grid-cols-2 gap-3 lg:grid-cols-4">
        <MetricCard
          label="服务可访问"
          value={status.reachable ? "是" : "否"}
          color={status.reachable ? "text-emerald-600" : "text-red-600"}
        />
        <MetricCard
          label="数据库就绪"
          value={status.databaseReady ? "是" : "否"}
          color={status.databaseReady ? "text-emerald-600" : "text-red-600"}
        />
        <MetricCard label="接口版本" value={status.apiVersion || "暂无信息"} />
        <MetricCard label="数据规范版本" value={status.schemaVersion || "暂无信息"} />
      </div>

      <div className="overflow-hidden rounded-lg border border-slate-200 bg-white">
        <dl className="divide-y divide-slate-100 text-sm">
          {[
            ["服务状态", status.reachable ? "可访问" : "不可访问"],
            ["数据库状态", status.databaseReady ? "已就绪" : "未就绪"],
            ["当前接口版本", status.apiVersion || "暂无信息"],
            ["数据规范版本", status.schemaVersion || "暂无信息"],
            ["后端类型", backendLabel],
            ["是否必须使用图数据库", yesNo(status.neo4jRequired)],
            ["检查时间", formatCheckedAt(status.checkedAt)],
          ].map(([label, value]) => (
            <div key={label} className="grid grid-cols-[minmax(9rem,0.45fr)_1fr] gap-4 px-4 py-3">
              <dt className="text-xs text-slate-500">{label}</dt>
              <dd className="min-w-0 break-words text-xs font-medium text-slate-700">{value}</dd>
            </div>
          ))}
        </dl>
      </div>
    </div>
  );
}
