import type { OntologyEdge, OntologyNode, PositionedOntologyNode } from "../types/ontology";
import {
  ONTOLOGY_LANE_LABELS,
  ONTOLOGY_LANE_ORDER,
  assignAllOntologyLanes,
  getLaneConfig,
  isEmphasizedNode,
  isTechnicalSupportNode,
} from "./ontologyLaneConfig";
import { buildLaneNodeLists } from "./ontologyOverviewBuilder";
import type {
  CollapsedOntologyEdge,
  LaneGeometry,
  NodePorts,
  OntologyLaneId,
  OntologyLayoutResult,
  Point,
  PortAssignment,
} from "./ontologyGraphTypes";

export const LAYOUT = {
  canvasPadding: 24,
  laneHeaderWidth: 190,
  laneContentPaddingX: 32,
  laneContentPaddingY: 36,
  laneGap: 16,
  nodeWidth: 148,
  emphasizedNodeWidth: 172,
  nodeHeight: 44,
  nodeGapX: 72,
  nodeGapY: 28,
  maxColumns: 7,
  edgeChannelGap: 14,
  crossLaneGutter: 220,
  edgeLabelHeight: 18,
  reverseRouteGap: 12,
  reverseRouteBase: 18,
  minCanvasWidth: 1600,
} as const;

export function getNodePorts(
  node: PositionedOntologyNode,
  assignments?: Partial<Record<"left" | "right" | "top" | "bottom", number>>,
): NodePorts {
  const left = assignments?.left ?? 0;
  const right = assignments?.right ?? 0;
  const top = assignments?.top ?? 0;
  const bottom = assignments?.bottom ?? 0;
  return {
    left: { x: node.x, y: node.y + node.height / 2 + left },
    right: { x: node.x + node.width, y: node.y + node.height / 2 + right },
    top: { x: node.x + node.width / 2 + top, y: node.y },
    bottom: { x: node.x + node.width / 2 + bottom, y: node.y + node.height },
  };
}

function relationSortKey(edge: CollapsedOntologyEdge): string {
  return edge.relations
    .map((item) => item.relation)
    .sort((a, b) => a.localeCompare(b))
    .join(",");
}

function comparePortEdges(
  a: CollapsedOntologyEdge,
  b: CollapsedOntologyEdge,
  nodeMap: Map<string, PositionedOntologyNode>,
  selfId: string,
): number {
  const aOtherId = a.from === selfId ? a.to : a.from;
  const bOtherId = b.from === selfId ? b.to : b.from;
  const aOther = nodeMap.get(aOtherId);
  const bOther = nodeMap.get(bOtherId);
  const aLane = aOther ? laneIndex(aOther.laneId) : Number.MAX_SAFE_INTEGER;
  const bLane = bOther ? laneIndex(bOther.laneId) : Number.MAX_SAFE_INTEGER;
  const aOrder = aOther?.order ?? Number.MAX_SAFE_INTEGER;
  const bOrder = bOther?.order ?? Number.MAX_SAFE_INTEGER;
  return (
    aLane - bLane ||
    aOrder - bOrder ||
    relationSortKey(a).localeCompare(relationSortKey(b)) ||
    a.id.localeCompare(b.id)
  );
}

export function assignNodePorts(
  nodes: PositionedOntologyNode[],
  edges: CollapsedOntologyEdge[],
): PortAssignment[] {
  const nodeMap = new Map(nodes.map((node) => [node.id, node]));
  const byNodeSide = new Map<string, CollapsedOntologyEdge[]>();

  const sideFor = (
    node: PositionedOntologyNode,
    other: PositionedOntologyNode,
  ): PortAssignment["side"] => {
    if (node.laneId !== other.laneId) {
      return laneIndex(node.laneId) < laneIndex(other.laneId) ? "bottom" : "top";
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
      const other = node.id === from.id ? to : from;
      const side = sideFor(node, other);
      const key = `${node.id}|${side}`;
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
    const seen = new Set<string>();
    const ordered: CollapsedOntologyEdge[] = [];
    for (const edge of [...bucket].sort((a, b) =>
      comparePortEdges(a, b, nodeMap, nodeId),
    )) {
      if (seen.has(edge.id)) continue;
      seen.add(edge.id);
      ordered.push(edge);
    }
    const edgeCount = ordered.length;
    const usableLength =
      side === "left" || side === "right"
        ? node.height - 12
        : node.width - 20;
    ordered.forEach((edge, index) => {
      assignments.push({
        edgeId: edge.id,
        nodeId,
        side,
        offset: ((index + 1) / (edgeCount + 1) - 0.5) * usableLength,
      });
    });
  }

  return assignments;
}

export function portOffsetLookup(
  assignments: PortAssignment[],
): Map<string, number> {
  const map = new Map<string, number>();
  for (const item of assignments) {
    map.set(`${item.edgeId}|${item.nodeId}|${item.side}`, item.offset);
  }
  return map;
}

function intervalsOverlap(a: [number, number], b: [number, number]): boolean {
  return a[0] <= b[1] && b[0] <= a[1];
}

export function assignIntervalChannels(
  edges: CollapsedOntologyEdge[],
  nodeMap: Map<string, PositionedOntologyNode>,
): Map<string, number> {
  const result = new Map<string, number>();

  const decorated = edges
    .map((edge) => {
      const source = nodeMap.get(edge.from);
      const target = nodeMap.get(edge.to);
      if (!source || !target || source.laneId !== target.laneId) return null;
      const sameCol = Math.abs(source.x - target.x) < 1;
      const forward = source.order < target.order && !sameCol;
      const interval: [number, number] = [
        Math.min(source.order, target.order),
        Math.max(source.order, target.order),
      ];
      return { edge, source, forward, interval };
    })
    .filter((item): item is NonNullable<typeof item> => item !== null)
    .sort(
      (a, b) =>
        laneIndex(a.source.laneId) - laneIndex(b.source.laneId) ||
        Number(a.forward) - Number(b.forward) ||
        a.interval[0] - b.interval[0] ||
        a.interval[1] - b.interval[1] ||
        relationSortKey(a.edge).localeCompare(relationSortKey(b.edge)) ||
        a.edge.id.localeCompare(b.edge.id),
    );

  type Active = { interval: [number, number]; channel: number };
  const activeByGroup = new Map<string, Active[]>();

  for (const item of decorated) {
    const groupKey = `${item.source.laneId}|${item.forward ? "F" : "R"}`;
    const active = activeByGroup.get(groupKey) ?? [];
    const used = new Set(
      active
        .filter((entry) => intervalsOverlap(entry.interval, item.interval))
        .map((entry) => entry.channel),
    );
    let channel = 0;
    while (used.has(channel)) channel += 1;
    active.push({ interval: item.interval, channel });
    activeByGroup.set(groupKey, active);
    result.set(item.edge.id, channel);
  }

  return result;
}

export function calculateRequiredIntraLaneChannels(
  edges: CollapsedOntologyEdge[],
  nodeMap: Map<string, PositionedOntologyNode>,
  laneId: OntologyLaneId,
): number {
  const laneEdges = edges.filter((edge) => {
    const from = nodeMap.get(edge.from);
    const to = nodeMap.get(edge.to);
    return Boolean(from && to && from.laneId === laneId && to.laneId === laneId);
  });
  if (laneEdges.length === 0) return 2;

  let forward = 0;
  let reverse = 0;
  for (const edge of laneEdges) {
    const from = nodeMap.get(edge.from);
    const to = nodeMap.get(edge.to);
    if (!from || !to) continue;
    const sameCol = Math.abs(from.x - to.x) < 1;
    if (from.order < to.order && !sameCol) forward += 1;
    else reverse += 1;
  }
  // Geometry uses unique slots per edge; reserve that many bus lines.
  return Math.max(1, forward) + Math.max(1, reverse);
}

function computeLaneHeight(nodeCount: number): number {
  const rows = Math.max(1, Math.ceil(nodeCount / LAYOUT.maxColumns));
  return (
    LAYOUT.laneContentPaddingY * 2 +
    rows * LAYOUT.nodeHeight +
    Math.max(0, rows - 1) * LAYOUT.nodeGapY
  );
}

function placeNodesInLane(
  laneId: OntologyLaneId,
  nodes: OntologyNode[],
  laneY: number,
  contentX: number,
): PositionedOntologyNode[] {
  const config = getLaneConfig(laneId);
  const overviewSet = new Set(config.overviewNodeOrder);

  return nodes.map((node, index) => {
    const col = index % LAYOUT.maxColumns;
    const row = Math.floor(index / LAYOUT.maxColumns);
    const emphasized = isEmphasizedNode(laneId, node.localName);
    const width = emphasized ? LAYOUT.emphasizedNodeWidth : LAYOUT.nodeWidth;
    const cellWidth = LAYOUT.emphasizedNodeWidth;
    const x =
      contentX +
      LAYOUT.laneContentPaddingX +
      col * (cellWidth + LAYOUT.nodeGapX);
    const y =
      laneY +
      LAYOUT.laneContentPaddingY +
      row * (LAYOUT.nodeHeight + LAYOUT.nodeGapY);

    return {
      ...node,
      laneId,
      x,
      y,
      width,
      height: LAYOUT.nodeHeight,
      order: index,
      overview: overviewSet.has(node.localName),
      technicalSupport: isTechnicalSupportNode(node),
    };
  });
}

function selectDisplayNodes(
  laneId: OntologyLaneId,
  list: OntologyNode[],
  overview: boolean,
): OntologyNode[] {
  if (!overview) return list;
  return list
    .filter((node) =>
      getLaneConfig(laneId).overviewNodeOrder.includes(node.localName),
    )
    .sort((a, b) => {
      const order = getLaneConfig(laneId).overviewNodeOrder;
      return order.indexOf(a.localName) - order.indexOf(b.localName);
    });
}

export function layoutOntologyGraph(
  nodes: OntologyNode[],
  collapsedEdges: CollapsedOntologyEdge[] = [],
  options: {
    overview: boolean;
    laneFilter?: OntologyLaneId;
    allEdges?: OntologyEdge[];
  } = { overview: true },
): OntologyLayoutResult {
  const { assignments } = assignAllOntologyLanes(nodes, options.allEdges ?? []);
  const laneNodes = buildLaneNodeLists(nodes, assignments);
  const lanesToLayout = options.laneFilter
    ? [options.laneFilter]
    : ONTOLOGY_LANE_ORDER;

  const contentX = LAYOUT.canvasPadding + LAYOUT.laneHeaderWidth;

  // Pass 1: place nodes at provisional Y=0 origins to obtain orders/x.
  const displayByLane = new Map<OntologyLaneId, OntologyNode[]>();
  const provisionalNodes: PositionedOntologyNode[] = [];
  for (const laneId of lanesToLayout) {
    const displayNodes = selectDisplayNodes(
      laneId,
      laneNodes.get(laneId) ?? [],
      options.overview,
    );
    displayByLane.set(laneId, displayNodes);
    provisionalNodes.push(
      ...placeNodesInLane(laneId, displayNodes, 0, contentX),
    );
  }

  const provisionalMap = new Map(
    provisionalNodes.map((node) => [node.id, node]),
  );
  const channelCountByLane = new Map<OntologyLaneId, number>();
  for (const laneId of lanesToLayout) {
    channelCountByLane.set(
      laneId,
      calculateRequiredIntraLaneChannels(
        collapsedEdges,
        provisionalMap,
        laneId,
      ),
    );
  }

  // Pass 2: pack lanes vertically with reserved route bands.
  const positioned: PositionedOntologyNode[] = [];
  const lanes: LaneGeometry[] = [];
  let y = LAYOUT.canvasPadding;
  let maxContentRight = contentX;

  for (const laneId of lanesToLayout) {
    const displayNodes = displayByLane.get(laneId) ?? [];
    const height = computeLaneHeight(Math.max(displayNodes.length, 1));
    const placed = placeNodesInLane(laneId, displayNodes, y, contentX);
    positioned.push(...placed);

    const effectiveColumns = Math.min(
      LAYOUT.maxColumns,
      Math.max(1, displayNodes.length),
    );
    const contentWidth =
      LAYOUT.laneContentPaddingX * 2 +
      effectiveColumns * LAYOUT.emphasizedNodeWidth +
      Math.max(0, effectiveColumns - 1) * LAYOUT.nodeGapX;
    const laneWidth = LAYOUT.laneHeaderWidth + contentWidth;

    const routeChannelCount = channelCountByLane.get(laneId) ?? 1;
    const routeBandHeight =
      LAYOUT.reverseRouteBase +
      Math.max(1, routeChannelCount) * LAYOUT.reverseRouteGap +
      12;
    const routeBottomY = y + height + routeBandHeight;

    lanes.push({
      id: laneId,
      label: ONTOLOGY_LANE_LABELS[laneId],
      x: LAYOUT.canvasPadding,
      y,
      width: laneWidth,
      height,
      contentX,
      contentY: y,
      contentWidth,
      contentHeight: height,
      routeBottomY,
    });

    maxContentRight = Math.max(
      maxContentRight,
      LAYOUT.canvasPadding + laneWidth,
    );
    y = routeBottomY + LAYOUT.laneGap;
  }

  const rawWidth =
    maxContentRight + LAYOUT.crossLaneGutter + LAYOUT.canvasPadding;
  const width = Math.max(LAYOUT.minCanvasWidth, Math.min(2200, rawWidth));
  const height = y + LAYOUT.canvasPadding;

  return {
    nodes: positioned,
    lanes,
    width,
    height,
    contentRight: maxContentRight,
  };
}

export function laneIndex(laneId: OntologyLaneId): number {
  return ONTOLOGY_LANE_ORDER.indexOf(laneId);
}

export function midpoint(a: Point, b: Point): Point {
  return { x: (a.x + b.x) / 2, y: (a.y + b.y) / 2 };
}
