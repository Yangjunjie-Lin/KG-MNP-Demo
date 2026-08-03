import { useEffect, useMemo, useState } from "react";
import { Network, Search, X } from "lucide-react";
import { ModuleTag } from "../components/StatusBadges";
import { cn } from "../utils/cn";
import {
  moduleLabels,
  ontologyClassLabels,
  ontologyRelationLabels,
  ontologyTypeLabels,
  translateOrUnknown,
  ui,
} from "../i18n/zh-CN";
import { getEdges, getModules, getNodes } from "../services/ontologyService";
import type { OntologyEdge, OntologyModule, OntologyNode } from "../types/ontology";

const MODULE_COLORS: Record<string, string> = {
  Core: "#2563eb",
  Identity: "#7c3aed",
  AccountBilling: "#0891b2",
  Contract: "#4f46e5",
  MNPProcess: "#0d9488",
  Eligibility: "#059669",
  Evidence: "#0891b2",
  Rules: "#7c3aed",
  Regulatory: "#1e40af",
};

const MODULE_BG: Record<string, string> = {
  Core: "#dbeafe",
  Identity: "#ede9fe",
  AccountBilling: "#cffafe",
  Contract: "#e0e7ff",
  MNPProcess: "#ccfbf1",
  Eligibility: "#d1fae5",
  Evidence: "#cffafe",
  Rules: "#ede9fe",
  Regulatory: "#e0e7ff",
};

function nodeDisplayLabel(n: OntologyNode): string {
  return translateOrUnknown(
    ontologyClassLabels,
    n.localName || n.id,
    ui.unknownOntologyClass,
  );
}

function edgeDisplayLabel(e: OntologyEdge): string {
  return translateOrUnknown(
    ontologyRelationLabels,
    e.relation,
    ui.unknownOntologyRelation,
  );
}

function moduleDisplayLabel(moduleId: string): string {
  return translateOrUnknown(moduleLabels, moduleId, ui.unknownModule);
}

export function OntologyBrowser() {
  const [nodes, setNodes] = useState<OntologyNode[]>([]);
  const [edges, setEdges] = useState<OntologyEdge[]>([]);
  const [modules, setModules] = useState<OntologyModule[]>([]);
  const [selectedNode, setSelectedNode] = useState<OntologyNode | null>(null);
  const [selectedModule, setSelectedModule] = useState<string | null>(null);
  const [searchTerm, setSearchTerm] = useState("");

  useEffect(() => {
    void (async () => {
      const [n, e, m] = await Promise.all([getNodes(), getEdges(), getModules()]);
      setNodes(n);
      setEdges(e);
      setModules(m);
    })();
  }, []);

  const visibleNodes = useMemo(
    () =>
      nodes.filter((n) => {
        const label = nodeDisplayLabel(n);
        const moduleLabel = moduleDisplayLabel(n.module);
        return (
          (!selectedModule || n.module === selectedModule) &&
          (!searchTerm ||
            label.includes(searchTerm) ||
            moduleLabel.includes(searchTerm))
        );
      }),
    [nodes, selectedModule, searchTerm],
  );

  const nodeMap = useMemo(
    () => Object.fromEntries(nodes.map((n) => [n.id, n])),
    [nodes],
  );

  return (
    <div className="flex h-full min-w-0 overflow-x-hidden">
      <div className="w-44 border-r border-slate-200 bg-white flex-shrink-0 overflow-y-auto p-3">
        <div className="text-[10px] text-slate-400 font-semibold tracking-wider mb-2 px-1">
          本体模块
        </div>
        <button
          type="button"
          onClick={() => setSelectedModule(null)}
          className={cn(
            "w-full text-left text-xs px-2 py-1.5 rounded mb-0.5 transition-colors",
            !selectedModule
              ? "bg-blue-50 text-blue-700 font-medium"
              : "text-slate-600 hover:bg-slate-50",
          )}
        >
          全部模块
        </button>
        {modules.map((m) => (
          <button
            key={m.id}
            type="button"
            onClick={() => setSelectedModule(m.id === selectedModule ? null : m.id)}
            className={cn(
              "w-full text-left text-xs px-2 py-1.5 rounded mb-0.5 transition-colors flex items-center gap-1.5",
              selectedModule === m.id
                ? "bg-blue-50 text-blue-700 font-medium"
                : "text-slate-600 hover:bg-slate-50",
            )}
          >
            <span
              className="w-2 h-2 rounded-full flex-shrink-0"
              style={{ backgroundColor: MODULE_COLORS[m.id] || "#94a3b8" }}
            />
            {moduleDisplayLabel(m.id)}
          </button>
        ))}
        <div className="mt-4 border-t border-slate-100 pt-3">
          <div className="text-[10px] text-slate-400 font-semibold tracking-wider mb-2 px-1">
            语义路径
          </div>
          {[
            "携转案件 → 资格评估 → 资格结论",
            "资格评估 → 证据记录",
            "阻塞原因 → 处理动作",
            "资格规则 → 监管条款",
          ].map((p) => (
            <div
              key={p}
              className="text-[10px] text-slate-500 px-1 py-1 leading-relaxed border-b border-slate-50 last:border-0"
            >
              {p}
            </div>
          ))}
        </div>
      </div>

      <div className="flex-1 bg-slate-50 relative overflow-hidden min-w-0">
        <div className="absolute top-3 left-3 right-3 flex items-center gap-2 z-10 min-w-0">
          <div className="flex items-center gap-1.5 bg-white border border-slate-200 rounded-md px-3 py-1.5 shadow-sm flex-1 max-w-xs min-w-0">
            <Search size={12} className="text-slate-400 flex-shrink-0" />
            <input
              type="text"
              placeholder={ui.searchOntology}
              value={searchTerm}
              onChange={(e) => setSearchTerm(e.target.value)}
              className="text-xs bg-transparent outline-none text-slate-700 placeholder-slate-400 w-full min-w-0"
            />
          </div>
          <div className="hidden md:flex items-center gap-1.5 flex-wrap min-w-0">
            {modules.slice(0, 5).map((m) => (
              <div key={m.id} className="flex items-center gap-1 text-[10px] text-slate-500">
                <span
                  className="w-2 h-2 rounded-full"
                  style={{ backgroundColor: MODULE_COLORS[m.id] }}
                />
                {moduleDisplayLabel(m.id)}
              </div>
            ))}
          </div>
        </div>
        <svg viewBox="0 0 860 560" className="w-full h-full">
          <defs>
            <marker id="arrow-onto" markerWidth="7" markerHeight="7" refX="6" refY="2.5" orient="auto">
              <path d="M0,0 L0,5 L7,2.5 z" fill="#cbd5e1" />
            </marker>
          </defs>
          {edges.map((e, i) => {
            const from = nodeMap[e.from];
            const to = nodeMap[e.to];
            if (!from || !to) return null;
            const fromVisible =
              !selectedModule ||
              from.module === selectedModule ||
              to.module === selectedModule;
            if (!fromVisible) return null;
            const fromLabel = nodeDisplayLabel(from);
            const toLabel = nodeDisplayLabel(to);
            const fromWidth = Math.max(110, fromLabel.length * 13 + 16);
            const toWidth = Math.max(110, toLabel.length * 13 + 16);
            const mx = (from.x + fromWidth / 2 + to.x + toWidth / 2) / 2;
            const my = (from.y + to.y) / 2;
            return (
              <g key={i}>
                <line
                  x1={from.x + fromWidth}
                  y1={from.y + 14}
                  x2={to.x}
                  y2={to.y + 14}
                  stroke="#e2e8f0"
                  strokeWidth="1.5"
                  markerEnd="url(#arrow-onto)"
                />
                <text x={mx} y={my + 8} fontSize="8" fill="#94a3b8" textAnchor="middle">
                  {edgeDisplayLabel(e)}
                </text>
              </g>
            );
          })}
          {nodes.map((n) => {
            const visible = visibleNodes.some((v) => v.id === n.id);
            const isSelected = selectedNode?.id === n.id;
            const label = nodeDisplayLabel(n);
            const nodeWidth = Math.max(110, label.length * 13 + 16);
            return (
              <g
                key={n.id}
                onClick={() => setSelectedNode(isSelected ? null : n)}
                className="cursor-pointer"
                style={{ opacity: visible ? 1 : 0.2 }}
              >
                <rect
                  x={n.x}
                  y={n.y}
                  width={nodeWidth}
                  height={28}
                  rx={4}
                  fill={MODULE_BG[n.module] || "#f8fafc"}
                  stroke={isSelected ? MODULE_COLORS[n.module] : "#e2e8f0"}
                  strokeWidth={isSelected ? 2 : 1}
                />
                <text
                  x={n.x + nodeWidth / 2}
                  y={n.y + 18}
                  fontSize="11"
                  fontWeight="500"
                  fill={MODULE_COLORS[n.module] || "#475569"}
                  textAnchor="middle"
                >
                  {label}
                </text>
              </g>
            );
          })}
        </svg>
      </div>

      <div className="w-64 border-l border-slate-200 bg-white overflow-y-auto flex-shrink-0 p-4">
        {selectedNode ? (
          <div className="text-xs space-y-3">
            <div className="flex items-start justify-between gap-2">
              <div className="min-w-0">
                <div className="font-semibold text-slate-800 text-sm mb-1 break-words">
                  {nodeDisplayLabel(selectedNode)}
                </div>
                <ModuleTag module={selectedNode.module} />
              </div>
              <button
                type="button"
                onClick={() => setSelectedNode(null)}
                className="text-slate-300 hover:text-slate-500"
              >
                <X size={14} />
              </button>
            </div>
            <div className="space-y-2 border-t border-slate-100 pt-3">
              {[
                {
                  label: "类型",
                  value: translateOrUnknown(
                    ontologyTypeLabels,
                    selectedNode.type,
                    ui.unknownOntologyClass,
                  ),
                },
                {
                  label: "模块",
                  value: moduleDisplayLabel(selectedNode.module),
                },
                {
                  label: "本地名称",
                  value: nodeDisplayLabel(selectedNode),
                },
              ].map((f) => (
                <div key={f.label}>
                  <div className="text-[10px] text-slate-400 tracking-wide mb-0.5">{f.label}</div>
                  <div className="text-slate-700 break-all">{f.value}</div>
                </div>
              ))}
              <div>
                <div className="text-[10px] text-slate-400 tracking-wide mb-1">定义</div>
                <div className="text-slate-600 leading-relaxed">{selectedNode.definition}</div>
              </div>
              <div>
                <div className="text-[10px] text-slate-400 tracking-wide mb-1">相关关系</div>
                {edges
                  .filter((e) => e.from === selectedNode.id || e.to === selectedNode.id)
                  .map((e) => (
                    <div
                      key={e.relation + e.from + e.to}
                      className="text-[10px] text-blue-600 py-0.5"
                    >
                      {edgeDisplayLabel(e)}
                    </div>
                  ))}
              </div>
            </div>
          </div>
        ) : (
          <div className="text-center text-slate-400 text-xs mt-12">
            <Network size={28} className="mx-auto mb-2 opacity-30" />
            点击图中节点查看
            <br />
            本体类详情
          </div>
        )}
      </div>
    </div>
  );
}
