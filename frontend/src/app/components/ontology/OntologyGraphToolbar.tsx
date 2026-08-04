import { Search, RefreshCw } from "lucide-react";
import { ui } from "../../i18n/zh-CN";

interface OntologyGraphToolbarProps {
  searchTerm: string;
  onSearchChange: (value: string) => void;
  overviewRelationCount: number;
  secondaryRelationCount: number;
  unmappedCount: number;
  isFetching?: boolean;
}

export function OntologyGraphToolbar({
  searchTerm,
  onSearchChange,
  overviewRelationCount,
  secondaryRelationCount,
  unmappedCount,
  isFetching,
}: OntologyGraphToolbarProps) {
  return (
    <div className="sticky left-3 top-3 z-10 flex w-[calc(100%-1.5rem)] min-w-0 flex-wrap items-center gap-2">
      <label className="flex max-w-xs min-w-0 flex-1 items-center gap-1.5 rounded-md border border-slate-200 bg-white px-3 py-1.5 shadow-sm">
        <Search size={12} className="flex-shrink-0 text-slate-400" />
        <span className="sr-only">搜索本体概念</span>
        <input
          type="search"
          placeholder={ui.searchOntology}
          value={searchTerm}
          onChange={(event) => onSearchChange(event.target.value)}
          className="w-full min-w-0 bg-transparent text-xs text-slate-700 outline-none placeholder:text-slate-400"
        />
      </label>
      <div className="flex flex-wrap items-center gap-2 text-[11px] text-slate-500">
        <span className="rounded bg-white px-2 py-1 shadow-sm">
          {ui.ontologyOverviewRelations}：{overviewRelationCount}
        </span>
        <span className="rounded bg-white px-2 py-1 shadow-sm">
          {ui.ontologyCollapsedRelations}：{secondaryRelationCount}
        </span>
        {unmappedCount > 0 ? (
          <span className="rounded bg-amber-50 px-2 py-1 text-amber-700 shadow-sm">
            {ui.ontologyUnmappedConcepts}：{unmappedCount}
          </span>
        ) : null}
      </div>
      {isFetching ? (
        <span
          role="status"
          className="flex items-center gap-1 rounded bg-white px-2 py-1 text-xs text-slate-400 shadow-sm"
        >
          <RefreshCw size={11} className="animate-spin" />
          正在刷新…
        </span>
      ) : null}
    </div>
  );
}
