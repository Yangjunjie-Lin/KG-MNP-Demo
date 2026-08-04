import { useMemo, useState } from "react";
import { Network, RefreshCw, Search, X } from "lucide-react";
import { ApiErrorState, EmptyState, PageSkeleton } from "../components/dataStates";
import {
  moduleLabels,
  ontologyClassLabels,
  ontologyRelationLabels,
  ontologyTypeLabels,
  translateOrUnknown,
  ui,
} from "../i18n/zh-CN";
import { useOntology } from "../query/hooks/useAppQueries";
import type { OntologyEdge, OntologyNode } from "../types/ontology";
import { cn } from "../utils/cn";

const MODULE_COLORS: Record<string, string> = {
  CORE: "#2563eb",
  IDENTITY: "#7c3aed",
  ACCOUNT_BILLING: "#0891b2",
  SERVICE_CONTRACT: "#4f46e5",
  PROCESS: "#0d9488",
  COMPLIANCE: "#059669",
  EVIDENCE_TIME: "#0284c7",
  CODE_LIST: "#64748b",
  ALIGNMENTS: "#475569",
};

const MODULE_BACKGROUNDS: Record<string, string> = {
  CORE: "#dbeafe",
  IDENTITY: "#ede9fe",
  ACCOUNT_BILLING: "#cffafe",
  SERVICE_CONTRACT: "#e0e7ff",
  PROCESS: "#ccfbf1",
  COMPLIANCE: "#d1fae5",
  EVIDENCE_TIME: "#e0f2fe",
  CODE_LIST: "#f1f5f9",
  ALIGNMENTS: "#f8fafc",
};

function containsChinese(value: string): boolean {
  return /[\u3400-\u9fff]/u.test(value);
}

function nodeDisplayLabel(node: OntologyNode): string {
  if (containsChinese(node.label)) return node.label;
  return translateOrUnknown(
    ontologyClassLabels,
    node.localName || node.id,
    ui.unknownOntologyClass,
  );
}

function edgeDisplayLabel(edge: OntologyEdge): string {
  if (containsChinese(edge.label)) return edge.label;
  return translateOrUnknown(
    ontologyRelationLabels,
    edge.relation,
    ui.unknownOntologyRelation,
  );
}

export function OntologyBrowser() {
  const query = useOntology();
  const [selectedNodeId, setSelectedNodeId] = useState<string | null>(null);
  const [selectedModule, setSelectedModule] = useState<string | null>(null);
  const [searchTerm, setSearchTerm] = useState("");

  const data = query.data;
  const nodes = data?.nodes ?? [];
  const edges = data?.edges ?? [];
  const modules = data?.modules ?? [];
  const moduleNames = useMemo(
    () => new Map(modules.map((module) => [module.id, module.label])),
    [modules],
  );
  const moduleDisplayLabel = (moduleId: string): string => {
    const backendLabel = moduleNames.get(moduleId) ?? "";
    return containsChinese(backendLabel)
      ? backendLabel
      : translateOrUnknown(moduleLabels, moduleId, ui.unknownModule);
  };
  const selectedNode = nodes.find((node) => node.id === selectedNodeId) ?? null;

  const visibleNodes = useMemo(
    () =>
      nodes.filter((node) => {
        const normalizedSearch = searchTerm.trim();
        return (
          (!selectedModule || node.module === selectedModule) &&
          (!normalizedSearch ||
            nodeDisplayLabel(node).includes(normalizedSearch) ||
            moduleDisplayLabel(node.module).includes(normalizedSearch))
        );
      }),
    [nodes, selectedModule, searchTerm, moduleNames],
  );
  const visibleNodeIds = useMemo(
    () => new Set(visibleNodes.map((node) => node.id)),
    [visibleNodes],
  );
  const nodeMap = useMemo(
    () => new Map(nodes.map((node) => [node.id, node])),
    [nodes],
  );
  const localNameMap = useMemo(
    () => new Map(nodes.map((node) => [node.localName, node])),
    [nodes],
  );
  const edgeLabelMap = useMemo(
    () => new Map(edges.map((edge) => [edge.relation, edgeDisplayLabel(edge)])),
    [edges],
  );
  const canvasWidth = Math.max(860, ...nodes.map((node) => node.x + 180));
  const canvasHeight = Math.max(560, ...nodes.map((node) => node.y + 70));

  if (query.isLoading) return <PageSkeleton />;
  if (query.isError) {
    return <ApiErrorState error={query.error} onRetry={() => void query.refetch()} />;
  }
  if (!data || nodes.length === 0) return <EmptyState message="暂无本体图数据" />;

  return (
    <div className="flex h-full min-w-0 overflow-x-hidden">
      <aside className="w-48 flex-shrink-0 overflow-y-auto border-r border-slate-200 bg-white p-3">
        <div className="mb-2 px-1 text-[10px] font-semibold tracking-wider text-slate-400">
          本体模块
        </div>
        <button
          type="button"
          onClick={() => setSelectedModule(null)}
          className={cn(
            "mb-0.5 w-full rounded px-2 py-1.5 text-left text-xs transition-colors",
            !selectedModule
              ? "bg-blue-50 font-medium text-blue-700"
              : "text-slate-600 hover:bg-slate-50",
          )}
        >
          全部模块
        </button>
        {modules.map((module) => (
          <button
            key={module.id}
            type="button"
            onClick={() => setSelectedModule(module.id === selectedModule ? null : module.id)}
            className={cn(
              "mb-0.5 flex w-full items-center gap-1.5 rounded px-2 py-1.5 text-left text-xs transition-colors",
              selectedModule === module.id
                ? "bg-blue-50 font-medium text-blue-700"
                : "text-slate-600 hover:bg-slate-50",
            )}
          >
            <span
              className="h-2 w-2 flex-shrink-0 rounded-full"
              style={{ backgroundColor: MODULE_COLORS[module.id] ?? "#94a3b8" }}
            />
            <span className="min-w-0 break-words">{moduleDisplayLabel(module.id)}</span>
          </button>
        ))}

        <div className="mt-4 border-t border-slate-100 pt-3">
          <div className="mb-2 px-1 text-[10px] font-semibold tracking-wider text-slate-400">
            语义路径
          </div>
          {data.keyPaths.length === 0 ? (
            <div className="px-1 text-[10px] text-slate-400">暂无语义路径</div>
          ) : (
            data.keyPaths.map((path) => {
              const source = localNameMap.get(path.sourceClass);
              const target = localNameMap.get(path.targetClass);
              return (
                <div
                  key={path.id}
                  className="border-b border-slate-50 px-1 py-1 text-[10px] leading-relaxed text-slate-500 last:border-0"
                >
                  {source ? nodeDisplayLabel(source) : ui.unknownOntologyClass}
                  {" → "}
                  {edgeLabelMap.get(path.predicate) ?? ui.unknownOntologyRelation}
                  {" → "}
                  {target ? nodeDisplayLabel(target) : ui.unknownOntologyClass}
                </div>
              );
            })
          )}
        </div>
      </aside>

      <section className="relative min-w-0 flex-1 overflow-auto bg-slate-50">
        <div className="sticky left-3 top-3 z-10 flex w-[calc(100%-1.5rem)] min-w-0 items-center gap-2">
          <label className="flex max-w-xs min-w-0 flex-1 items-center gap-1.5 rounded-md border border-slate-200 bg-white px-3 py-1.5 shadow-sm">
            <Search size={12} className="flex-shrink-0 text-slate-400" />
            <span className="sr-only">搜索本体概念</span>
            <input
              type="search"
              placeholder={ui.searchOntology}
              value={searchTerm}
              onChange={(event) => setSearchTerm(event.target.value)}
              className="w-full min-w-0 bg-transparent text-xs text-slate-700 outline-none placeholder:text-slate-400"
            />
          </label>
          {query.isFetching && (
            <span role="status" className="flex items-center gap-1 rounded bg-white px-2 py-1 text-xs text-slate-400 shadow-sm">
              <RefreshCw size={11} className="animate-spin" />正在刷新…
            </span>
          )}
        </div>

        <svg
          viewBox={`0 0 ${canvasWidth} ${canvasHeight}`}
          style={{ width: canvasWidth, height: canvasHeight }}
          aria-label="本体关系图"
        >
          <defs>
            <marker id="arrow-ontology" markerWidth="7" markerHeight="7" refX="6" refY="2.5" orient="auto">
              <path d="M0,0 L0,5 L7,2.5 z" fill="#cbd5e1" />
            </marker>
          </defs>
          {edges.map((edge) => {
            const from = nodeMap.get(edge.from);
            const to = nodeMap.get(edge.to);
            if (!from || !to) return null;
            const edgeVisible = visibleNodeIds.has(from.id) && visibleNodeIds.has(to.id);
            const fromLabel = nodeDisplayLabel(from);
            const toLabel = nodeDisplayLabel(to);
            const fromWidth = Math.max(110, fromLabel.length * 13 + 16);
            const toWidth = Math.max(110, toLabel.length * 13 + 16);
            const middleX = (from.x + fromWidth / 2 + to.x + toWidth / 2) / 2;
            const middleY = (from.y + to.y) / 2;
            return (
              <g key={`${edge.from}|${edge.relation}|${edge.to}`} opacity={edgeVisible ? 1 : 0.12}>
                <line
                  x1={from.x + fromWidth}
                  y1={from.y + 14}
                  x2={to.x}
                  y2={to.y + 14}
                  stroke="#cbd5e1"
                  strokeWidth="1.25"
                  markerEnd="url(#arrow-ontology)"
                />
                <text x={middleX} y={middleY + 8} fontSize="8" fill="#64748b" textAnchor="middle">
                  {edgeDisplayLabel(edge)}
                </text>
              </g>
            );
          })}
          {nodes.map((node) => {
            const visible = visibleNodeIds.has(node.id);
            const selected = selectedNode?.id === node.id;
            const label = nodeDisplayLabel(node);
            const width = Math.max(110, label.length * 13 + 16);
            const color = MODULE_COLORS[node.module] ?? "#475569";
            return (
              <g
                key={node.id}
                role="button"
                tabIndex={0}
                onClick={() => setSelectedNodeId(selected ? null : node.id)}
                onKeyDown={(event) => {
                  if (event.key === "Enter" || event.key === " ") {
                    event.preventDefault();
                    setSelectedNodeId(selected ? null : node.id);
                  }
                }}
                className="cursor-pointer outline-none"
                opacity={visible ? 1 : 0.15}
              >
                <rect
                  x={node.x}
                  y={node.y}
                  width={width}
                  height={28}
                  rx={4}
                  fill={MODULE_BACKGROUNDS[node.module] ?? "#f8fafc"}
                  stroke={selected ? color : "#cbd5e1"}
                  strokeWidth={selected ? 2 : 1}
                />
                <text
                  x={node.x + width / 2}
                  y={node.y + 18}
                  fontSize="11"
                  fontWeight="500"
                  fill={color}
                  textAnchor="middle"
                >
                  {label}
                </text>
              </g>
            );
          })}
        </svg>
      </section>

      <aside className="w-64 flex-shrink-0 overflow-y-auto border-l border-slate-200 bg-white p-4">
        {selectedNode ? (
          <div className="space-y-3 text-xs">
            <div className="flex items-start justify-between gap-2">
              <div className="min-w-0">
                <div className="mb-1 break-words text-sm font-semibold text-slate-800">
                  {nodeDisplayLabel(selectedNode)}
                </div>
                <span
                  className="inline-flex rounded px-1.5 py-0.5 text-xs font-medium"
                  style={{
                    color: MODULE_COLORS[selectedNode.module] ?? "#475569",
                    backgroundColor: MODULE_BACKGROUNDS[selectedNode.module] ?? "#f1f5f9",
                  }}
                >
                  {moduleDisplayLabel(selectedNode.module)}
                </span>
              </div>
              <button
                type="button"
                aria-label="关闭详情"
                onClick={() => setSelectedNodeId(null)}
                className="text-slate-400 hover:text-slate-600"
              >
                <X size={14} />
              </button>
            </div>
            <dl className="space-y-2 border-t border-slate-100 pt-3">
              <div>
                <dt className="mb-0.5 text-[10px] tracking-wide text-slate-400">类型</dt>
                <dd className="text-slate-700">
                  {translateOrUnknown(ontologyTypeLabels, selectedNode.type, ui.unknownOntologyClass)}
                </dd>
              </div>
              <div>
                <dt className="mb-1 text-[10px] tracking-wide text-slate-400">相关关系</dt>
                <dd className="space-y-1">
                  {edges.filter((edge) => edge.from === selectedNode.id || edge.to === selectedNode.id).length === 0 ? (
                    <span className="text-slate-400">暂无相关关系</span>
                  ) : (
                    edges
                      .filter((edge) => edge.from === selectedNode.id || edge.to === selectedNode.id)
                      .map((edge) => (
                        <div key={`${edge.from}|${edge.relation}|${edge.to}`} className="text-blue-700">
                          {edgeDisplayLabel(edge)}
                        </div>
                      ))
                  )}
                </dd>
              </div>
            </dl>
          </div>
        ) : (
          <div className="mt-12 text-center text-xs text-slate-400">
            <Network size={28} className="mx-auto mb-2 opacity-30" />
            点击图中节点查看本体类详情
          </div>
        )}
      </aside>
    </div>
  );
}
