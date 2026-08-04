import { Network, X } from "lucide-react";
import { apiConfig } from "../../../api/config";
import {
  ontologyTypeLabels,
  translateOrUnknown,
  ui,
} from "../../i18n/zh-CN";
import { ONTOLOGY_LANE_LABELS } from "../../ontology/ontologyLaneConfig";
import type { OntologyEdge, PositionedOntologyNode } from "../../types/ontology";

interface OntologyNodeDetailsProps {
  node: PositionedOntologyNode | null;
  edges: OntologyEdge[];
  nodeLabel: (node: PositionedOntologyNode) => string;
  edgeLabel: (edge: OntologyEdge) => string;
  relatedNodes: PositionedOntologyNode[];
  onClose: () => void;
}

export function OntologyNodeDetails({
  node,
  edges,
  nodeLabel,
  edgeLabel,
  relatedNodes,
  onClose,
}: OntologyNodeDetailsProps) {
  if (!node) {
    return (
      <div
        className="mt-12 text-center text-xs text-slate-400"
        data-testid="ontology-node-details"
      >
        <Network size={28} className="mx-auto mb-2 opacity-30" />
        {ui.ontologySelectNodeHint}
      </div>
    );
  }

  const outgoing = edges.filter((edge) => edge.from === node.id);
  const incoming = edges.filter((edge) => edge.to === node.id);
  const related = edges.filter(
    (edge) => edge.from === node.id || edge.to === node.id,
  );

  return (
    <div className="space-y-3 text-xs" data-testid="ontology-node-details">
      <div className="flex items-start justify-between gap-2">
        <div className="min-w-0">
          <div className="mb-1 break-words text-sm font-semibold text-slate-800">
            {nodeLabel(node)}
          </div>
          <span className="inline-flex rounded bg-slate-100 px-1.5 py-0.5 text-xs font-medium text-slate-700">
            {ONTOLOGY_LANE_LABELS[node.laneId]}
          </span>
        </div>
        <button
          type="button"
          aria-label="关闭详情"
          onClick={onClose}
          className="text-slate-400 hover:text-slate-600"
        >
          <X size={14} />
        </button>
      </div>

      <dl className="space-y-2 border-t border-slate-100 pt-3">
        <div>
          <dt className="mb-0.5 text-[10px] tracking-wide text-slate-400">类型</dt>
          <dd className="text-slate-700">
            {translateOrUnknown(ontologyTypeLabels, node.type, ui.unknownOntologyClass)}
          </dd>
        </div>
        <div>
          <dt className="mb-0.5 text-[10px] tracking-wide text-slate-400">
            {ui.ontologyBusinessLayer}
          </dt>
          <dd className="text-slate-700">{ONTOLOGY_LANE_LABELS[node.laneId]}</dd>
        </div>
        <div>
          <dt className="mb-0.5 text-[10px] tracking-wide text-slate-400">
            {ui.ontologyInOverview}
          </dt>
          <dd className="text-slate-700">
            {node.overview ? ui.ontologyYes : ui.ontologyNo}
          </dd>
        </div>
        <div>
          <dt className="mb-0.5 text-[10px] tracking-wide text-slate-400">
            {ui.ontologyOutgoingCount}
          </dt>
          <dd className="text-slate-700">{outgoing.length}</dd>
        </div>
        <div>
          <dt className="mb-0.5 text-[10px] tracking-wide text-slate-400">
            {ui.ontologyIncomingCount}
          </dt>
          <dd className="text-slate-700">{incoming.length}</dd>
        </div>
        <div>
          <dt className="mb-1 text-[10px] tracking-wide text-slate-400">
            {ui.ontologyRelatedConcepts}
          </dt>
          <dd className="space-y-1">
            {relatedNodes.length === 0 ? (
              <span className="text-slate-400">暂无关联概念</span>
            ) : (
              relatedNodes.map((item) => (
                <div key={item.id} className="text-slate-700">
                  {nodeLabel(item)}
                </div>
              ))
            )}
          </dd>
        </div>
        <div>
          <dt className="mb-1 text-[10px] tracking-wide text-slate-400">
            {ui.ontologyRelationList}
          </dt>
          <dd className="space-y-1">
            {related.length === 0 ? (
              <span className="text-slate-400">暂无相关关系</span>
            ) : (
              related.map((edge) => (
                <div
                  key={`${edge.from}|${edge.relation}|${edge.to}`}
                  className="text-blue-700"
                >
                  {edgeLabel(edge)}
                </div>
              ))
            )}
          </dd>
        </div>
        {apiConfig.technicalViewEnabled ? (
          <div>
            <dt className="mb-0.5 text-[10px] tracking-wide text-slate-400">
              技术标识
            </dt>
            <dd className="break-all text-slate-500">
              {node.localName} · {node.module} · {node.id}
            </dd>
          </div>
        ) : null}
      </dl>
    </div>
  );
}
