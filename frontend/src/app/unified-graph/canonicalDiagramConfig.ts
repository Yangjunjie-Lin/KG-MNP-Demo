import rawCanonicalDiagramConfig from "../../../../config/canonical_business_diagram_v2.json";
import type {
  CanonicalBusinessDiagramConfig,
  CanonicalBusinessLayer,
  CanonicalBusinessNode,
  CanonicalSharedBus,
  CanonicalStructuralEdge,
} from "./canonicalDiagramTypes";
import type { BusinessLayerId, BusinessRoleId } from "./graphTypes";

export const canonicalDiagramConfig =
  rawCanonicalDiagramConfig as unknown as CanonicalBusinessDiagramConfig;

export const CANONICAL_DIAGRAM_CONFIG = canonicalDiagramConfig;
export const CANONICAL_CANVAS = canonicalDiagramConfig.canvas;
export const CANONICAL_STYLE = canonicalDiagramConfig.style;
export const CANONICAL_LAYERS = canonicalDiagramConfig.layers;
export const CANONICAL_NODES = canonicalDiagramConfig.nodes;
export const CANONICAL_BUSES = canonicalDiagramConfig.buses;
export const CANONICAL_EDGES = canonicalDiagramConfig.edges;
export const CANONICAL_MARKERS = canonicalDiagramConfig.markers;

export const CANONICAL_LAYER_BY_ID: ReadonlyMap<
  BusinessLayerId,
  CanonicalBusinessLayer
> = new Map(CANONICAL_LAYERS.map((layer) => [layer.id, layer]));

export const CANONICAL_NODE_BY_ID: ReadonlyMap<
  BusinessRoleId,
  CanonicalBusinessNode
> = new Map(CANONICAL_NODES.map((node) => [node.id, node]));

export const CANONICAL_EDGE_BY_ID: ReadonlyMap<
  string,
  CanonicalStructuralEdge
> = new Map(CANONICAL_EDGES.map((edge) => [edge.id, edge]));

export const CANONICAL_BUS_BY_ID: ReadonlyMap<string, CanonicalSharedBus> =
  new Map(CANONICAL_BUSES.map((bus) => [bus.id, bus]));

export function getCanonicalLayer(
  layerId: BusinessLayerId,
): CanonicalBusinessLayer {
  const layer = CANONICAL_LAYER_BY_ID.get(layerId);
  if (!layer) throw new Error(`Unknown canonical business layer: ${layerId}`);
  return layer;
}

export function getCanonicalNode(roleId: BusinessRoleId): CanonicalBusinessNode {
  const node = CANONICAL_NODE_BY_ID.get(roleId);
  if (!node) throw new Error(`Unknown canonical business role: ${roleId}`);
  return node;
}

export function getCanonicalEdge(edgeId: string): CanonicalStructuralEdge {
  const edge = CANONICAL_EDGE_BY_ID.get(edgeId);
  if (!edge) throw new Error(`Unknown canonical structural edge: ${edgeId}`);
  return edge;
}

export default canonicalDiagramConfig;
