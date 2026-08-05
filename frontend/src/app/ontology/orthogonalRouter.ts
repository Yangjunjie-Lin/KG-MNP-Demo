import type { PositionedOntologyNode } from "../types/ontology";
import type {
  CollapsedOntologyEdge,
  LaneGeometry,
  OntologyLaneId,
  Point,
  RoutedOntologyEdge,
} from "./ontologyGraphTypes";
import {
  LAYOUT,
  assignIntervalChannels,
  assignNodePorts,
  getNodePorts,
  laneIndex,
  midpoint,
  portOffsetLookup,
} from "./ontologyLayout";

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

function portFor(
  edgeId: string,
  node: PositionedOntologyNode,
  side: "left" | "right" | "top" | "bottom",
  offsets: Map<string, number>,
): Point {
  const offset = offsets.get(`${edgeId}|${node.id}|${side}`) ?? 0;
  return getNodePorts(node, { [side]: offset })[side];
}

function sameColumn(a: PositionedOntologyNode, b: PositionedOntologyNode): boolean {
  return Math.abs(a.x - b.x) < 1;
}

function isForward(source: PositionedOntologyNode, target: PositionedOntologyNode): boolean {
  return source.order < target.order;
}

function pickSides(
  source: PositionedOntologyNode,
  target: PositionedOntologyNode,
): { leaveSide: "left" | "right"; arriveSide: "left" | "right" } {
  if (sameColumn(source, target)) {
    return { leaveSide: "right", arriveSide: "right" };
  }
  if (source.x <= target.x) {
    return { leaveSide: "right", arriveSide: "left" };
  }
  return { leaveSide: "left", arriveSide: "right" };
}

function preferredStubX(
  node: PositionedOntologyNode,
  side: "left" | "right",
  slot: number,
): number {
  const inset = 6 + slot * 4;
  const cellRight = node.x + LAYOUT.emphasizedNodeWidth;
  return side === "right" ? cellRight + inset : node.x - inset;
}

function allocateDistinctX(preferred: number, used: number[]): number {
  let x = preferred;
  const minGap = 4;
  for (let guard = 0; guard < 500; guard += 1) {
    if (!used.some((value) => Math.abs(value - x) < minGap)) {
      used.push(x);
      return x;
    }
    x += minGap;
  }
  used.push(x);
  return x;
}

function busYFor(
  lane: LaneGeometry,
  channel: number,
  band: "forward" | "reverse",
  forwardChannelCount: number,
): number {
  const forwardBand = Math.max(1, forwardChannelCount);
  if (band === "forward") {
    return (
      lane.y +
      lane.height +
      LAYOUT.reverseRouteBase +
      channel * LAYOUT.reverseRouteGap
    );
  }
  return (
    lane.y +
    lane.height +
    LAYOUT.reverseRouteBase +
    forwardBand * LAYOUT.reverseRouteGap +
    channel * LAYOUT.reverseRouteGap
  );
}

function routeIntraSideGap(
  edgeId: string,
  source: PositionedOntologyNode,
  target: PositionedOntologyNode,
  exitX: number,
  entryX: number,
  busSlot: number,
  lane: LaneGeometry,
  offsets: Map<string, number>,
  forwardChannelCount: number,
  band: "forward" | "reverse",
): Point[] {
  const { leaveSide, arriveSide } = pickSides(source, target);
  const leave = portFor(edgeId, source, leaveSide, offsets);
  const arrive = portFor(edgeId, target, arriveSide, offsets);
  const busY = busYFor(lane, busSlot, band, forwardChannelCount);
  return orthogonalize([
    leave,
    { x: exitX, y: leave.y },
    { x: exitX, y: busY },
    { x: entryX, y: busY },
    { x: entryX, y: arrive.y },
    arrive,
  ]);
}

function routeCrossLane(
  edgeId: string,
  source: PositionedOntologyNode,
  target: PositionedOntologyNode,
  channel: number,
  contentRight: number,
  offsets: Map<string, number>,
): Point[] {
  const sourceBelow = laneIndex(source.laneId) < laneIndex(target.laneId);
  const leaveSide = sourceBelow ? "bottom" : "top";
  const arriveSide = sourceBelow ? "top" : "bottom";
  const leave = portFor(edgeId, source, leaveSide, offsets);
  const arrive = portFor(edgeId, target, arriveSide, offsets);
  const routeX = contentRight + 24 + channel * LAYOUT.edgeChannelGap;
  const leaveStub = sourceBelow
    ? leave.y + 8 + channel * 3
    : leave.y - 8 - channel * 3;
  const arriveStub = sourceBelow
    ? arrive.y - 8 - channel * 3
    : arrive.y + 8 + channel * 3;

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

function countBandSize(
  edges: CollapsedOntologyEdge[],
  nodeById: Map<string, PositionedOntologyNode>,
  predicate: (
    from: PositionedOntologyNode,
    to: PositionedOntologyNode,
  ) => boolean,
): Map<OntologyLaneId, number> {
  const counts = new Map<OntologyLaneId, number>();
  for (const edge of edges) {
    const from = nodeById.get(edge.from);
    const to = nodeById.get(edge.to);
    if (!from || !to || from.laneId !== to.laneId) continue;
    if (!predicate(from, to)) continue;
    counts.set(from.laneId, (counts.get(from.laneId) ?? 0) + 1);
  }
  return counts;
}

export function routeOntologyEdges(input: {
  nodes: PositionedOntologyNode[];
  collapsedEdges: CollapsedOntologyEdge[];
  lanes: LaneGeometry[];
  contentRight: number;
}): RoutedOntologyEdge[] {
  const nodeById = new Map(input.nodes.map((node) => [node.id, node]));
  const laneById = new Map(input.lanes.map((lane) => [lane.id, lane]));
  const offsets = portOffsetLookup(
    assignNodePorts(input.nodes, input.collapsedEdges),
  );

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

  const channelByEdge = assignIntervalChannels(intra, nodeById);
  const forwardCounts = countBandSize(
    intra,
    nodeById,
    (from, to) => isForward(from, to) && !sameColumn(from, to),
  );
  const slotByEdge = new Map<string, number>();
  const nextSlot = new Map<string, number>();
  for (const edge of intra) {
    const from = nodeById.get(edge.from);
    const to = nodeById.get(edge.to);
    if (!from || !to) continue;
    const band =
      isForward(from, to) && !sameColumn(from, to) ? "F" : "R";
    const key = `${from.laneId}|${band}`;
    const slot = nextSlot.get(key) ?? 0;
    nextSlot.set(key, slot + 1);
    slotByEdge.set(edge.id, slot);
  }

  const usedRailX = new Map<OntologyLaneId, number[]>();
  const railByEdge = new Map<string, { exitX: number; entryX: number }>();
  for (const edge of intra) {
    const from = nodeById.get(edge.from);
    const to = nodeById.get(edge.to);
    if (!from || !to) continue;
    const slot = slotByEdge.get(edge.id) ?? 0;
    const useForward = isForward(from, to) && !sameColumn(from, to);
    const stubSlot = useForward
      ? slot
      : slot + (forwardCounts.get(from.laneId) ?? 0);
    const { leaveSide, arriveSide } = pickSides(from, to);
    const used = usedRailX.get(from.laneId) ?? [];
    const exitX = allocateDistinctX(
      preferredStubX(from, leaveSide, stubSlot),
      used,
    );
    const entryX = allocateDistinctX(
      preferredStubX(to, arriveSide, stubSlot),
      used,
    );
    usedRailX.set(from.laneId, used);
    railByEdge.set(edge.id, { exitX, entryX });
  }

  const routed: RoutedOntologyEdge[] = [];

  for (const edge of intra) {
    const from = nodeById.get(edge.from);
    const to = nodeById.get(edge.to);
    if (!from || !to) continue;
    const lane = laneById.get(from.laneId);
    if (!lane) continue;
    const rails = railByEdge.get(edge.id);
    if (!rails) continue;

    const logicalChannel = channelByEdge.get(edge.id) ?? 0;
    const slot = slotByEdge.get(edge.id) ?? 0;
    const forwardChannelCount = Math.max(
      1,
      forwardCounts.get(from.laneId) ?? 1,
    );
    const useForwardSide =
      isForward(from, to) && !sameColumn(from, to);
    const points = routeIntraSideGap(
      edge.id,
      from,
      to,
      rails.exitX,
      rails.entryX,
      slot,
      lane,
      offsets,
      forwardChannelCount,
      useForwardSide ? "forward" : "reverse",
    );

    const labelPoint = longestHorizontalLabel(points);
    routed.push({
      id: edge.id,
      from: edge.from,
      to: edge.to,
      relations: edge.relations,
      points,
      path: pointsToPath(points),
      labelX: labelPoint.x,
      labelY: labelPoint.y - 8,
      kind: "INTRA_LANE",
      channel: logicalChannel,
    });
  }

  cross.forEach((edge, channel) => {
    const from = nodeById.get(edge.from);
    const to = nodeById.get(edge.to);
    if (!from || !to) return;
    const points = routeCrossLane(
      edge.id,
      from,
      to,
      channel,
      input.contentRight,
      offsets,
    );
    const labelPoint = longestHorizontalLabel(points);
    routed.push({
      id: edge.id,
      from: edge.from,
      to: edge.to,
      relations: edge.relations,
      points,
      path: pointsToPath(points),
      labelX: labelPoint.x,
      labelY: labelPoint.y - 8,
      kind: "CROSS_LANE",
      channel,
    });
  });

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

export type { OntologyLaneId };
