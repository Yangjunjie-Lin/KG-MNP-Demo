import { layerIndex } from "./businessLayerConfig";
import type {
  CollapsedProjectedEdge,
  LayerGeometry,
  Point,
  PortAssignment,
  RoutedProjectedEdge,
  VisualProjection,
} from "./graphTypes";
import { collapsedRelationLabel } from "../i18n/graphChineseResolver";

const EDGE_CHANNEL_GAP = 14;
const REVERSE_ROUTE_GAP = 12;
const REVERSE_ROUTE_BASE = 18;

function pointsToPath(points: Point[]): string {
  if (!points.length) return "";
  let path = `M ${points[0].x} ${points[0].y}`;
  for (let i = 1; i < points.length; i += 1) {
    const prev = points[i - 1];
    const point = points[i];
    if (point.y === prev.y) path += ` H ${point.x}`;
    else if (point.x === prev.x) path += ` V ${point.y}`;
    else path += ` H ${point.x} V ${point.y}`;
  }
  return path;
}

function orthogonalize(points: Point[]): Point[] {
  if (!points.length) return points;
  const result: Point[] = [points[0]];
  for (let i = 1; i < points.length; i += 1) {
    const prev = result[result.length - 1];
    const next = points[i];
    if (prev.x === next.x && prev.y === next.y) continue;
    if (prev.x !== next.x && prev.y !== next.y) {
      result.push({ x: next.x, y: prev.y });
    }
    result.push(next);
  }
  return result;
}

function midpoint(a: Point, b: Point): Point {
  return { x: (a.x + b.x) / 2, y: (a.y + b.y) / 2 };
}

function longestHorizontalLabel(points: Point[]): Point {
  let bestLen = -1;
  let best: Point = points[0] ?? { x: 0, y: 0 };
  for (let i = 0; i < points.length - 1; i += 1) {
    const a = points[i];
    const b = points[i + 1];
    if (a.y !== b.y) continue;
    const len = Math.abs(b.x - a.x);
    if (len > bestLen) {
      bestLen = len;
      best = midpoint(a, b);
    }
  }
  if (bestLen < 0) {
    return points[Math.floor(points.length / 2)] ?? { x: 0, y: 0 };
  }
  return best;
}

export function getNodePorts(
  node: VisualProjection,
  offsets?: Partial<Record<"left" | "right" | "top" | "bottom", number>>,
) {
  const left = offsets?.left ?? 0;
  const right = offsets?.right ?? 0;
  const top = offsets?.top ?? 0;
  const bottom = offsets?.bottom ?? 0;
  return {
    left: { x: node.x, y: node.y + node.height / 2 + left },
    right: { x: node.x + node.width, y: node.y + node.height / 2 + right },
    top: { x: node.x + node.width / 2 + top, y: node.y },
    bottom: { x: node.x + node.width / 2 + bottom, y: node.y + node.height },
  };
}

function relationSortKey(edge: CollapsedProjectedEdge): string {
  return edge.edges
    .map((item) => item.relationId)
    .sort((a, b) => a.localeCompare(b))
    .join(",");
}

function compareEdges(
  a: CollapsedProjectedEdge,
  b: CollapsedProjectedEdge,
  nodes: Map<string, VisualProjection>,
): number {
  const aFrom = nodes.get(a.from);
  const aTo = nodes.get(a.to);
  const bFrom = nodes.get(b.from);
  const bTo = nodes.get(b.to);
  if (!aFrom || !aTo || !bFrom || !bTo) return a.id.localeCompare(b.id);
  return (
    layerIndex(aFrom.layerId) - layerIndex(bFrom.layerId) ||
    layerIndex(aTo.layerId) - layerIndex(bTo.layerId) ||
    aFrom.order - bFrom.order ||
    aTo.order - bTo.order ||
    relationSortKey(a).localeCompare(relationSortKey(b)) ||
    a.id.localeCompare(b.id)
  );
}

export function assignNodePorts(
  nodes: VisualProjection[],
  edges: CollapsedProjectedEdge[],
): PortAssignment[] {
  const nodeMap = new Map(nodes.map((node) => [node.projectionId, node]));
  const byNodeSide = new Map<string, CollapsedProjectedEdge[]>();

  const sideFor = (
    node: VisualProjection,
    other: VisualProjection,
  ): PortAssignment["side"] => {
    if (node.layerId !== other.layerId) {
      return layerIndex(node.layerId) < layerIndex(other.layerId)
        ? "bottom"
        : "top";
    }
    if (node.x + node.width <= other.x) return "right";
    if (other.x + other.width <= node.x) return "left";
    return "bottom";
  };

  for (const edge of edges) {
    const from = nodeMap.get(edge.from);
    const to = nodeMap.get(edge.to);
    if (!from || !to) continue;
    for (const node of [from, to]) {
      const other = node.projectionId === from.projectionId ? to : from;
      const side = sideFor(node, other);
      const key = `${node.projectionId}|${side}`;
      const bucket = byNodeSide.get(key) ?? [];
      bucket.push(edge);
      byNodeSide.set(key, bucket);
    }
  }

  const assignments: PortAssignment[] = [];
  for (const [key, bucket] of [...byNodeSide.entries()].sort(([a], [b]) =>
    a.localeCompare(b),
  )) {
    const [nodeId, side] = key.split("|") as [string, PortAssignment["side"]];
    const node = nodeMap.get(nodeId);
    if (!node) continue;
    const ordered = [...bucket].sort((a, b) => compareEdges(a, b, nodeMap));
    const unique: CollapsedProjectedEdge[] = [];
    const seen = new Set<string>();
    for (const edge of ordered) {
      if (seen.has(edge.id)) continue;
      seen.add(edge.id);
      unique.push(edge);
    }
    const usable =
      side === "left" || side === "right" ? node.height - 12 : node.width - 20;
    unique.forEach((edge, index) => {
      assignments.push({
        edgeId: edge.id,
        nodeId,
        side,
        offset: ((index + 1) / (unique.length + 1) - 0.5) * usable,
      });
    });
  }
  return assignments;
}

function portOffsetLookup(assignments: PortAssignment[]): Map<string, number> {
  const map = new Map<string, number>();
  for (const item of assignments) {
    map.set(`${item.edgeId}|${item.nodeId}|${item.side}`, item.offset);
  }
  return map;
}

function portFor(
  edgeId: string,
  node: VisualProjection,
  side: "left" | "right" | "top" | "bottom",
  offsets: Map<string, number>,
): Point {
  const offset = offsets.get(`${edgeId}|${node.projectionId}|${side}`) ?? 0;
  return getNodePorts(node, { [side]: offset })[side];
}

function allocateDistinct(preferred: number, used: number[], gap = 4): number {
  let value = preferred;
  for (let guard = 0; guard < 400; guard += 1) {
    if (!used.some((item) => Math.abs(item - value) < gap)) {
      used.push(value);
      return value;
    }
    value += gap;
  }
  used.push(value);
  return value;
}

function routeIntra(
  edgeId: string,
  source: VisualProjection,
  target: VisualProjection,
  lane: LayerGeometry,
  slot: number,
  offsets: Map<string, number>,
  usedRails: number[],
): Point[] {
  const leaveSide =
    source.x + source.width <= target.x
      ? "right"
      : target.x + target.width <= source.x
        ? "left"
        : "bottom";
  const arriveSide =
    leaveSide === "right" ? "left" : leaveSide === "left" ? "right" : "top";
  const leave = portFor(edgeId, source, leaveSide, offsets);
  const arrive = portFor(edgeId, target, arriveSide, offsets);
  // Keep intra-layer buses inside the layer bottom band to avoid next-layer nodes.
  const busY = Math.min(
    lane.y + lane.height - 10 - slot * REVERSE_ROUTE_GAP,
    Math.max(source.y + source.height, target.y + target.height) + 14 + slot * 4,
  );
  const exitX = allocateDistinct(
    leaveSide === "right" ? leave.x + 8 + slot * 4 : leave.x - 8 - slot * 4,
    usedRails,
  );
  const entryX = allocateDistinct(
    arriveSide === "left" ? arrive.x - 8 - slot * 4 : arrive.x + 8 + slot * 4,
    usedRails,
  );
  return orthogonalize([
    leave,
    { x: exitX, y: leave.y },
    { x: exitX, y: busY },
    { x: entryX, y: busY },
    { x: entryX, y: arrive.y },
    arrive,
  ]);
}

function routeCrossDown(
  edgeId: string,
  source: VisualProjection,
  target: VisualProjection,
  channel: number,
  offsets: Map<string, number>,
): Point[] {
  const leave = portFor(edgeId, source, "bottom", offsets);
  const arrive = portFor(edgeId, target, "top", offsets);
  const leaveStub = leave.y + 8 + channel * 3;
  const arriveStub = arrive.y - 8 - channel * 3;
  // Prefer vertical corridor between centers to avoid side gutters when going down.
  const midX = allocateDistinct(
    (leave.x + arrive.x) / 2 + channel * EDGE_CHANNEL_GAP * 0.25,
    [],
  );
  return orthogonalize([
    leave,
    { x: leave.x, y: leaveStub },
    { x: midX, y: leaveStub },
    { x: midX, y: arriveStub },
    { x: arrive.x, y: arriveStub },
    arrive,
  ]);
}

function routeCrossUp(
  edgeId: string,
  source: VisualProjection,
  target: VisualProjection,
  channel: number,
  contentRight: number,
  offsets: Map<string, number>,
  useLeftGutter: boolean,
): Point[] {
  const leave = portFor(edgeId, source, "top", offsets);
  const arrive = portFor(edgeId, target, "bottom", offsets);
  const gutterX = useLeftGutter
    ? 20 + channel * EDGE_CHANNEL_GAP
    : contentRight + 24 + channel * EDGE_CHANNEL_GAP;
  const leaveStub = leave.y - 8 - channel * 3;
  const arriveStub = arrive.y + 8 + channel * 3;
  return orthogonalize([
    leave,
    { x: leave.x, y: leaveStub },
    { x: gutterX, y: leaveStub },
    { x: gutterX, y: arriveStub },
    { x: arrive.x, y: arriveStub },
    arrive,
  ]);
}

export function routeProjectedEdges(input: {
  nodes: VisualProjection[];
  collapsedEdges: CollapsedProjectedEdge[];
  layers: LayerGeometry[];
  contentRight: number;
}): RoutedProjectedEdge[] {
  const nodeById = new Map(input.nodes.map((node) => [node.projectionId, node]));
  const laneById = new Map(input.layers.map((lane) => [lane.id, lane]));
  const offsets = portOffsetLookup(
    assignNodePorts(input.nodes, input.collapsedEdges),
  );

  const intra: CollapsedProjectedEdge[] = [];
  const cross: CollapsedProjectedEdge[] = [];
  for (const edge of input.collapsedEdges) {
    const from = nodeById.get(edge.from);
    const to = nodeById.get(edge.to);
    if (!from || !to) {
      throw new Error(
        `Cannot route edge ${edge.id}: missing endpoint ${edge.from} or ${edge.to}`,
      );
    }
    if (from.layerId === to.layerId) intra.push(edge);
    else cross.push(edge);
  }

  intra.sort((a, b) => compareEdges(a, b, nodeById));
  cross.sort((a, b) => compareEdges(a, b, nodeById));

  const routed: RoutedProjectedEdge[] = [];
  const usedRails = new Map<string, number[]>();
  const slotByEdge = new Map<string, number>();
  const nextSlot = new Map<string, number>();

  for (const edge of intra) {
    const from = nodeById.get(edge.from)!;
    const key = from.layerId;
    const slot = nextSlot.get(key) ?? 0;
    nextSlot.set(key, slot + 1);
    slotByEdge.set(edge.id, slot);
  }

  for (const edge of intra) {
    const from = nodeById.get(edge.from)!;
    const to = nodeById.get(edge.to)!;
    const lane = laneById.get(from.layerId);
    if (!lane) continue;
    const rails = usedRails.get(from.layerId) ?? [];
    const points = routeIntra(
      edge.id,
      from,
      to,
      lane,
      slotByEdge.get(edge.id) ?? 0,
      offsets,
      rails,
    );
    usedRails.set(from.layerId, rails);
    const labelPoint = longestHorizontalLabel(points);
    const labels = edge.edges.map((item) => item.labelZh);
    routed.push({
      id: edge.id,
      from: edge.from,
      to: edge.to,
      edges: edge.edges,
      points,
      path: pointsToPath(points),
      labelX: labelPoint.x,
      labelY: labelPoint.y - 8,
      labelZh: collapsedRelationLabel(labels),
      kind: "INTRA_LAYER",
      channel: slotByEdge.get(edge.id) ?? 0,
      presentationType: edge.edges[0]?.presentationType ?? "ONTOLOGY",
      state: edge.edges[0]?.state,
    });
  }

  cross.forEach((edge, channel) => {
    const from = nodeById.get(edge.from)!;
    const to = nodeById.get(edge.to)!;
    const goingDown = layerIndex(from.layerId) < layerIndex(to.layerId);
    const points = goingDown
      ? routeCrossDown(edge.id, from, to, channel, offsets)
      : routeCrossUp(
          edge.id,
          from,
          to,
          channel,
          input.contentRight,
          offsets,
          channel % 2 === 0,
        );
    const labelPoint = longestHorizontalLabel(points);
    const labels = edge.edges.map((item) => item.labelZh);
    routed.push({
      id: edge.id,
      from: edge.from,
      to: edge.to,
      edges: edge.edges,
      points,
      path: pointsToPath(points),
      labelX: labelPoint.x,
      labelY: labelPoint.y - 8,
      labelZh: collapsedRelationLabel(labels),
      kind: "CROSS_LAYER",
      channel,
      presentationType: edge.edges[0]?.presentationType ?? "ONTOLOGY",
      state: edge.edges[0]?.state,
    });
  });

  routed.sort((a, b) => {
    if (a.kind !== b.kind) return a.kind === "INTRA_LAYER" ? -1 : 1;
    return a.id.localeCompare(b.id);
  });
  return routed;
}

export function isOrthogonalPath(path: string): boolean {
  if (!path) return false;
  if (/[CQLASTcqlast]/i.test(path.replace(/\s+/g, ""))) return false;
  return /[MHVmhv]/.test(path);
}
