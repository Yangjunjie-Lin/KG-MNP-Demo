import { Maximize2, Minus, Plus, RotateCcw } from "lucide-react";
import type { ReactNode } from "react";

interface GraphToolbarProps {
  scale: number;
  onZoomIn: () => void;
  onZoomOut: () => void;
  onFit: () => void;
  onReset: () => void;
  onScale100: () => void;
  searchTerm?: string;
  onSearchChange?: (value: string) => void;
  extra?: ReactNode;
}

export function GraphToolbar({
  scale,
  onZoomIn,
  onZoomOut,
  onFit,
  onReset,
  onScale100,
  searchTerm,
  onSearchChange,
  extra,
}: GraphToolbarProps) {
  return (
    <div
      className="flex flex-wrap items-center gap-2 border-b border-slate-200 bg-white px-3 py-2"
      data-testid="graph-toolbar"
    >
      <button
        type="button"
        className="rounded border border-slate-200 px-2 py-1 text-xs text-slate-700 hover:bg-slate-50"
        onClick={onZoomIn}
      >
        <span className="inline-flex items-center gap-1">
          <Plus size={12} /> 放大
        </span>
      </button>
      <button
        type="button"
        className="rounded border border-slate-200 px-2 py-1 text-xs text-slate-700 hover:bg-slate-50"
        onClick={onZoomOut}
      >
        <span className="inline-flex items-center gap-1">
          <Minus size={12} /> 缩小
        </span>
      </button>
      <button
        type="button"
        className="rounded border border-slate-200 px-2 py-1 text-xs text-slate-700 hover:bg-slate-50"
        onClick={onFit}
      >
        <span className="inline-flex items-center gap-1">
          <Maximize2 size={12} /> 适应画布
        </span>
      </button>
      <button
        type="button"
        className="rounded border border-slate-200 px-2 py-1 text-xs text-slate-700 hover:bg-slate-50"
        onClick={onReset}
      >
        <span className="inline-flex items-center gap-1">
          <RotateCcw size={12} /> 重置视图
        </span>
      </button>
      <button
        type="button"
        className="rounded border border-slate-200 px-2 py-1 text-xs text-slate-700 hover:bg-slate-50"
        onClick={onScale100}
      >
        100%
      </button>
      <span className="text-xs text-slate-500" data-testid="graph-scale-label">
        {Math.round(scale * 100)}%
      </span>
      {onSearchChange ? (
        <input
          className="ml-auto min-w-[160px] rounded border border-slate-200 px-2 py-1 text-xs"
          placeholder="搜索业务概念"
          value={searchTerm ?? ""}
          onChange={(event) => onSearchChange(event.target.value)}
        />
      ) : null}
      {extra}
    </div>
  );
}
