import { useMemo, useState } from "react";
import { ApiErrorState, EmptyState, PageSkeleton } from "../components/dataStates";
import { UnifiedBusinessGraph } from "../components/unified-graph/UnifiedBusinessGraph";
import { ui } from "../i18n/zh-CN";
import { useOntology } from "../query/hooks/useAppQueries";
import type { UnifiedGraphMode } from "../unified-graph/graphTypes";
import { cn } from "../utils/cn";

const VIEW_MODES: Array<{ id: UnifiedGraphMode; label: string }> = [
  { id: "BUSINESS_OVERVIEW", label: "业务总览" },
  { id: "COMPLETE_ONTOLOGY", label: "完整本体" },
];

export function OntologyBrowser() {
  const query = useOntology();
  const [viewMode, setViewMode] = useState<UnifiedGraphMode>("BUSINESS_OVERVIEW");

  const data = query.data;
  const nodes = useMemo(
    () =>
      (data?.nodes ?? []).map((node) => ({
        id: node.id,
        label: node.label,
        localName: node.localName,
        module: node.module,
        type: node.type,
      })),
    [data?.nodes],
  );
  const edges = useMemo(
    () =>
      (data?.edges ?? []).map((edge, index) => ({
        id: `${edge.from}->${edge.to}:${edge.relation}:${index}`,
        from: edge.from,
        to: edge.to,
        relation: edge.relation,
        label: edge.label,
        presentationType: "ONTOLOGY" as const,
      })),
    [data?.edges],
  );

  if (query.isLoading) return <PageSkeleton />;
  if (query.isError) {
    return <ApiErrorState error={query.error} onRetry={() => void query.refetch()} />;
  }
  if (!data || nodes.length === 0) return <EmptyState message="暂无本体图数据" />;

  const nav = (
    <div className="space-y-0.5">
      <div className="mb-2 px-1 text-[10px] font-semibold tracking-wider text-slate-400">
        {ui.ontologyViewNav}
      </div>
      {VIEW_MODES.map((mode) => (
        <button
          key={mode.id}
          type="button"
          onClick={() => setViewMode(mode.id)}
          className={cn(
            "mb-0.5 w-full rounded px-2 py-1.5 text-left text-xs transition-colors",
            viewMode === mode.id
              ? "bg-blue-50 font-medium text-blue-700"
              : "text-slate-600 hover:bg-slate-50",
          )}
        >
          {mode.label}
        </button>
      ))}
    </div>
  );

  return (
    <div className="flex h-full min-w-0 flex-col overflow-hidden lg:flex-row">
      <aside className="hidden w-[190px] flex-shrink-0 overflow-y-auto border-r border-slate-200 bg-white p-3 lg:block">
        {nav}
      </aside>

      <div className="border-b border-slate-200 bg-white p-3 lg:hidden">
        <label className="block text-xs text-slate-500">
          {ui.ontologyViewNav}
          <select
            className="mt-1 w-full rounded border border-slate-200 px-2 py-1.5 text-sm text-slate-700"
            value={viewMode}
            onChange={(event) => setViewMode(event.target.value as UnifiedGraphMode)}
          >
            {VIEW_MODES.map((mode) => (
              <option key={mode.id} value={mode.id}>
                {mode.label}
              </option>
            ))}
          </select>
        </label>
      </div>

      <section className="relative min-w-0 flex-1 overflow-hidden bg-slate-50">
        <UnifiedBusinessGraph
          mode={viewMode}
          nodes={nodes}
          edges={edges}
          testId={
            viewMode === "BUSINESS_OVERVIEW"
              ? "ontology-overview-graph-root"
              : "ontology-complete-graph-root"
          }
          graphTestId={
            viewMode === "BUSINESS_OVERVIEW"
              ? "ontology-overview-graph"
              : "ontology-complete-graph"
          }
        />
      </section>
    </div>
  );
}
