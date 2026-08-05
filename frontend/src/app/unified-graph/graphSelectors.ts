import type {
  GraphProjectionResult,
  RoutedProjectedEdge,
  VisualProjection,
} from "./graphTypes";
import { BUSINESS_LAYER_ORDER } from "./businessLayerConfig";

export function selectNodeById(
  nodes: VisualProjection[],
  projectionId: string | null,
): VisualProjection | null {
  if (!projectionId) return null;
  return nodes.find((node) => node.projectionId === projectionId) ?? null;
}

export function relatedProjectionIds(
  projectionId: string | null,
  edges: RoutedProjectedEdge[],
): Set<string> {
  if (!projectionId) return new Set();
  const ids = new Set<string>([projectionId]);
  for (const edge of edges) {
    if (edge.from === projectionId) ids.add(edge.to);
    if (edge.to === projectionId) ids.add(edge.from);
  }
  return ids;
}

export function relatedEdgeIds(
  projectionId: string | null,
  edges: RoutedProjectedEdge[],
): Set<string> {
  if (!projectionId) return new Set();
  return new Set(
    edges
      .filter((edge) => edge.from === projectionId || edge.to === projectionId)
      .map((edge) => edge.id),
  );
}

export function layerStats(graph: GraphProjectionResult): Array<{
  layerId: string;
  coreRoleCount: number;
  extensionNodeCount: number;
  nodeTotal: number;
  edgeCount: number;
}> {
  return BUSINESS_LAYER_ORDER.map((layerId) => {
    const layerNodes = graph.nodes.filter((node) => node.layerId === layerId);
    const edgeCount = graph.edges.filter((edge) => {
      const from = graph.nodes.find(
        (node) => node.projectionId === edge.sourceProjectionId,
      );
      const to = graph.nodes.find(
        (node) => node.projectionId === edge.targetProjectionId,
      );
      return from?.layerId === layerId || to?.layerId === layerId;
    }).length;
    return {
      layerId,
      coreRoleCount: layerNodes.filter((node) => node.kind === "CORE_ROLE").length,
      extensionNodeCount: layerNodes.filter((node) => node.kind === "EXTENSION")
        .length,
      nodeTotal: layerNodes.length,
      edgeCount,
    };
  });
}

export function nodeOpacityForSelection(input: {
  projectionId: string;
  selectedId: string | null;
  relatedIds: Set<string>;
  searchMatches: Set<string> | null;
}): number {
  if (input.searchMatches) {
    return input.searchMatches.has(input.projectionId) ? 1 : 0.15;
  }
  if (!input.selectedId) return 1;
  return input.relatedIds.has(input.projectionId) ? 1 : 0.2;
}
