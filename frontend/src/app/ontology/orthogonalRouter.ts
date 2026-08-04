import type { PositionedOntologyNode } from "../types/ontology";
import type {
  CollapsedOntologyEdge,
  LaneGeometry,
  OntologyLaneId,
  Point,
  RoutedOntologyEdge,
} from "./ontologyGraphTypes";
import { getNodePorts, LAYOUT, laneIndex, midpoint } from "./ontologyLayout";

function pointsToPath(points: Point[]): string {
  if (points.length === 0) return "";
  let path = `M ${points[0].x} ${points[0].y}`;
  for (let i = 1; i < points.length; i += 1) {
    const prev = points[i - 1];
    const point = points[i];
    if (point.y === prev.y) {
      path += ` H ${point.x}`;
    } else if (point.x === prev.x) {
      path += ` V ${point.y}`;
    } else {
      path += ` H ${point.x} V ${point.y}`;
    }
  }
  return path;
}

function orthogonalize(points: Point[]): Point[] {
  if (points.length === 0) return points;
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
    // fallback to geometric midpoint of polyline
    const midIndex = Math.floor(points.length / 2);
    return points[midIndex] ?? { x: 0, y: 0 };
  }
  return best;
}

function relationSortKey(edge: CollapsedOntologyEdge): string {
  return edge.relations
    .map((item) => item.relation)
    .sort((a, b) => a.localeCompare(b))
    .join(",");
}

function compareCrossLane(
  a: CollapsedOntologyEdge,
  b: CollapsedOntologyEdge,
  nodes: Map<string, PositionedOntologyNode>,
): number {
  const aFrom = nodes.get(a.from);
  const aTo = nodes.get(a.to);
  const bFrom = nodes.get(b.from);
  const bTo = nodes.get(b.to);
  if (!aFrom || !aTo || !bFrom || !bTo) return a.id.localeCompare(b.id);

  return (
    laneIndex(aFrom.laneId) - laneIndex(bFrom.laneId) ||
    laneIndex(aTo.laneId) - laneIndex(bTo.laneId) ||
    aFrom.order - bFrom.order ||
    aTo.order - bTo.order ||
    relationSortKey(a).localeCompare(relationSortKey(b)) ||
    a.id.localeCompare(b.id)
  );
}

function compareIntraLane(
  a: CollapsedOntologyEdge,
  b: CollapsedOntologyEdge,
  nodes: Map<string, PositionedOntologyNode>,
): number {
  const aFrom = nodes.get(a.from);
  const aTo = nodes.get(a.to);
  const bFrom = nodes.get(b.from);
  const bTo = nodes.get(b.to);
  if (!aFrom || !aTo || !bFrom || !bTo) return a.id.localeCompare(b.id);
  return (
    aFrom.order - bFrom.order ||
    aTo.order - bTo.order ||
    relationSortKey(a).localeCompare(relationSortKey(b)) ||
    a.id.localeCompare(b.id)
  );
}

function gapSlotX(
  node: PositionedOntologyNode,
  channel: number,
  side: "left" | "right",
): number {
  const half = Math.floor(LAYOUT.nodeGapX / 2);
  const maxSlots = Math.max(1, Math.floor((half - 16) / 8));
  const slot = 8 + (channel % maxSlots) * 8;
  if (side === "right") {
    // Left half of the gap after this node.
    return node.x + LAYOUT.emphasizedNodeWidth + slot;
  }
  // Right half of the gap before this node.
  return node.x - half - slot;
}

function routeForwardIntra(
  source: PositionedOntologyNode,
  target: PositionedOntologyNode,
  channel: number,
  lane: LaneGeometry,
): Point[] {
  const sp = getNodePorts(source);
  const tp = getNodePorts(target);
  const exitX = gapSlotX(source, channel, "right");
  const entryX = gapSlotX(target, channel, "left");
  const busY =
    lane.y +
    lane.height +
    LAYOUT.reverseRouteBase +
    channel * LAYOUT.reverseRouteGap;
  return orthogonalize([
    sp.right,
    { x: exitX, y: sp.right.y },
    { x: exitX, y: busY },
    { x: entryX, y: busY },
    { x: entryX, y: tp.left.y },
    tp.left,
  ]);
}

function routeReverseIntra(
  source: PositionedOntologyNode,
  target: PositionedOntologyNode,
  channel: number,
  lane: LaneGeometry,
): Point[] {
  const sp = getNodePorts(source);
  const tp = getNodePorts(target);
  const exitX = gapSlotX(source, channel, "left");
  const entryX = gapSlotX(target, channel, "right");
  const laneRouteY =
    lane.y +
    lane.height +
    LAYOUT.reverseRouteBase +
    channel * LAYOUT.reverseRouteGap;
  return orthogonalize([
    sp.bottom,
    { x: exitX, y: sp.bottom.y },
    { x: exitX, y: laneRouteY },
    { x: entryX, y: laneRouteY },
    { x: entryX, y: tp.bottom.y },
    tp.bottom,
  ]);
}

function routeCrossLane(
  source: PositionedOntologyNode,
  target: PositionedOntologyNode,
  channel: number,
  contentRight: number,
): Point[] {
  const sp = getNodePorts(source);
  const tp = getNodePorts(target);
  const routeX = contentRight + 24 + channel * LAYOUT.edgeChannelGap;
  const sourceBelow = laneIndex(source.laneId) < laneIndex(target.laneId);
  const leave = sourceBelow ? sp.bottom : sp.top;
  const arrive = sourceBelow ? tp.top : tp.bottom;
  const leaveStub = sourceBelow
    ? leave.y + 10 + channel * 4
    : leave.y - 10 - channel * 4;
  const arriveStub = sourceBelow
    ? arrive.y - 10 - channel * 4
    : arrive.y + 10 + channel * 4;

  return orthogonalize([
    leave,
    { x: leave.x, y: leaveStub },
    { x: routeX, y: leaveStub },
    { x: routeX, y: arriveStub },
    { x: arrive.x, y: arriveStub },
    arrive,
  ]);
}

function edgeLabel(relations: CollapsedOntologyEdge["relations"]): string {
  if (relations.length === 1) {
    return relations[0].label || relations[0].relation;
  }
  return `${relations.length} 项关系`;
}

export function routeOntologyEdges(input: {
  nodes: PositionedOntologyNode[];
  collapsedEdges: CollapsedOntologyEdge[];
  lanes: LaneGeometry[];
  contentRight: number;
}): RoutedOntologyEdge[] {
  const nodeById = new Map(input.nodes.map((node) => [node.id, node]));
  const laneById = new Map(input.lanes.map((lane) => [lane.id, lane]));

  const intra: CollapsedOntologyEdge[] = [];
  const cross: CollapsedOntologyEdge[] = [];

  for (const edge of input.collapsedEdges) {
    const from = nodeById.get(edge.from);
    const to = nodeById.get(edge.to);
    if (!from || !to) continue;
    if (from.laneId === to.laneId) intra.push(edge);
    else cross.push(edge);
  }

  intra.sort((a, b) => compareIntraLane(a, b, nodeById));
  cross.sort((a, b) => compareCrossLane(a, b, nodeById));

  const routed: RoutedOntologyEdge[] = [];
  const channelByLane = new Map<OntologyLaneId, number>();

  for (const edge of intra) {
    const from = nodeById.get(edge.from);
    const to = nodeById.get(edge.to);
    if (!from || !to) continue;
    const lane = laneById.get(from.laneId);
    if (!lane) continue;

    const channel = channelByLane.get(from.laneId) ?? 0;
    channelByLane.set(from.laneId, channel + 1);

    const forward = from.x + from.width <= to.x;
    const points = forward
      ? routeForwardIntra(from, to, channel, lane)
      : routeReverseIntra(from, to, channel, lane);

    const labelPoint = longestHorizontalLabel(points);
    routed.push({
      id: edge.id,
      from: edge.from,
      to: edge.to,
      relations: edge.relations,
      points,
      path: pointsToPath(points),
      labelX: labelPoint.x,
      labelY: labelPoint.y,
      kind: "INTRA_LANE",
      channel,
    });
  }

  cross.forEach((edge, channel) => {
    const from = nodeById.get(edge.from);
    const to = nodeById.get(edge.to);
    if (!from || !to) return;
    const points = routeCrossLane(from, to, channel, input.contentRight);
    const labelPoint = longestHorizontalLabel(points);
    routed.push({
      id: edge.id,
      from: edge.from,
      to: edge.to,
      relations: edge.relations,
      points,
      path: pointsToPath(points),
      labelX: labelPoint.x,
      labelY: labelPoint.y,
      kind: "CROSS_LANE",
      channel,
    });
  });

  // Stable order: by kind then id
  routed.sort((a, b) => {
    if (a.kind !== b.kind) return a.kind === "INTRA_LANE" ? -1 : 1;
    return a.id.localeCompare(b.id);
  });

  return routed;
}

export function collapsedEdgeDisplayLabel(edge: RoutedOntologyEdge): string {
  return edgeLabel(edge.relations);
}

export function isOrthogonalPath(path: string): boolean {
  if (!path) return false;
  if (/[CQLASTcqlast]/i.test(path.replace(/\s+/g, ""))) return false;
  return /[MHVmhv]/.test(path);
}

export function pointsAreOrthogonal(points: Point[]): boolean {
  for (let i = 0; i < points.length - 1; i += 1) {
    const a = points[i];
    const b = points[i + 1];
    if (!(a.x === b.x || a.y === b.y)) return false;
  }
  return true;
}
