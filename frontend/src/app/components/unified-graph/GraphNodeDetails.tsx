import { BUSINESS_LAYER_LABELS } from "../../unified-graph/businessLayerConfig";
import type { ProjectedGraphEdge, VisualProjection } from "../../unified-graph/graphTypes";

interface GraphNodeDetailsProps {
  node: VisualProjection | null;
  edges: ProjectedGraphEdge[];
  relatedNodes: VisualProjection[];
  onClose: () => void;
}

export function GraphNodeDetails({
  node,
  edges,
  relatedNodes,
  onClose,
}: GraphNodeDetailsProps) {
  if (!node) {
    return (
      <div className="text-sm text-slate-500" data-testid="graph-node-details-empty">
        选择节点查看业务详情
      </div>
    );
  }

  const relatedEdges = edges.filter(
    (edge) =>
      edge.sourceProjectionId === node.projectionId ||
      edge.targetProjectionId === node.projectionId,
  );

  return (
    <section className="space-y-3 text-sm" data-testid="graph-node-details">
      <div data-testid="trace-node-details" className="contents">
      <div className="flex items-start justify-between gap-2">
        <div>
          <h3 className="font-semibold text-slate-800">{node.labelZh}</h3>
          <p className="text-xs text-slate-500">
            {BUSINESS_LAYER_LABELS[node.layerId]}
          </p>
        </div>
        <button
          type="button"
          className="text-xs text-slate-500 hover:text-slate-700"
          onClick={onClose}
        >
          关闭
        </button>
      </div>

      <dl className="grid grid-cols-2 gap-2 text-xs">
        <div>
          <dt className="text-slate-500">节点类型</dt>
          <dd className="font-medium text-slate-800">
            {node.kind === "CORE_ROLE"
              ? "核心业务角色"
              : node.kind === "EXTENSION"
                ? "扩展节点"
                : "本体投影"}
          </dd>
        </div>
        <div>
          <dt className="text-slate-500">节点名称</dt>
          <dd className="font-medium text-slate-800">{node.labelZh}</dd>
        </div>
        <div>
          <dt className="text-slate-500">映射数量</dt>
          <dd className="font-medium text-slate-800">
            {node.mappedCount === 0
              ? "当前无对应本体概念"
              : node.mappedCount ?? 1}
          </dd>
        </div>
        <div>
          <dt className="text-slate-500">关系数量</dt>
          <dd className="font-medium text-slate-800">{relatedEdges.length}</dd>
        </div>
      </dl>

      <div>
        <h4 className="mb-1 text-xs font-semibold text-slate-600">相关关系</h4>
        <ul className="space-y-1 text-xs text-slate-700">
          {relatedEdges.length === 0 ? (
            <li>暂无关系</li>
          ) : (
            relatedEdges.map((edge) => (
              <li key={edge.id}>
                {edge.labelZh}
                {edge.sourceEdgeIds.length > 1
                  ? `（${edge.sourceEdgeIds.length}）`
                  : ""}
              </li>
            ))
          )}
        </ul>
      </div>

      <div>
        <h4 className="mb-1 text-xs font-semibold text-slate-600">相邻节点</h4>
        <ul className="space-y-1 text-xs text-slate-700">
          {relatedNodes.length === 0 ? (
            <li>暂无相邻节点</li>
          ) : (
            relatedNodes.map((item) => <li key={item.projectionId}>{item.labelZh}</li>)
          )}
        </ul>
      </div>
      </div>
    </section>
  );
}
