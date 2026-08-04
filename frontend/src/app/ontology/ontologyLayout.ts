import type { OntologyNode, PositionedOntologyNode } from "../types/ontology";
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
  LaneGeometry,
  NodePorts,
  OntologyLaneId,
  OntologyLayoutResult,
  Point,
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
  nodeGapX: 320,
  nodeGapY: 28,
  maxColumns: 7,
  edgeChannelGap: 16,
  crossLaneGutter: 320,
  edgeLabelHeight: 18,
  reverseRouteGap: 14,
  reverseRouteBase: 18,
  minCanvasWidth: 1600,
} as const;

export function getNodePorts(node: PositionedOntologyNode): NodePorts {
  return {
    left: { x: node.x, y: node.y + node.height / 2 },
    right: { x: node.x + node.width, y: node.y + node.height / 2 },
    top: { x: node.x + node.width / 2, y: node.y },
    bottom: { x: node.x + node.width / 2, y: node.y + node.height },
  };
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
  overview: boolean,
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

export function layoutOntologyGraph(
  nodes: OntologyNode[],
  options: {
    overview: boolean;
    laneFilter?: OntologyLaneId;
  },
): OntologyLayoutResult {
  const { assignments } = assignAllOntologyLanes(nodes);
  const laneNodes = buildLaneNodeLists(nodes, assignments);

  const lanesToLayout = options.laneFilter
    ? [options.laneFilter]
    : ONTOLOGY_LANE_ORDER;

  const contentX = LAYOUT.canvasPadding + LAYOUT.laneHeaderWidth;
  const positioned: PositionedOntologyNode[] = [];
  const lanes: LaneGeometry[] = [];

  let y = LAYOUT.canvasPadding;
  let maxContentRight = contentX;

  for (const laneId of lanesToLayout) {
    const list = laneNodes.get(laneId) ?? [];
    const displayNodes = options.overview
      ? list.filter((node) =>
          getLaneConfig(laneId).overviewNodeOrder.includes(node.localName),
        ).sort((a, b) => {
          const order = getLaneConfig(laneId).overviewNodeOrder;
          return order.indexOf(a.localName) - order.indexOf(b.localName);
        })
      : list;

    const height = computeLaneHeight(Math.max(displayNodes.length, 1));
    const placed = placeNodesInLane(laneId, displayNodes, y, contentX, options.overview);
    positioned.push(...placed);

    const contentWidth =
      LAYOUT.laneContentPaddingX * 2 +
      LAYOUT.maxColumns * LAYOUT.emphasizedNodeWidth +
      Math.max(0, LAYOUT.maxColumns - 1) * LAYOUT.nodeGapX;

    const laneWidth = LAYOUT.laneHeaderWidth + contentWidth;
    const reverseChannels = Math.max(8, displayNodes.length + 2);
    const routeBottomY =
      y +
      height +
      LAYOUT.reverseRouteBase +
      reverseChannels * LAYOUT.reverseRouteGap;

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

    maxContentRight = Math.max(maxContentRight, LAYOUT.canvasPadding + laneWidth);
    y = routeBottomY + LAYOUT.laneGap;
  }

  const width = Math.max(
    LAYOUT.minCanvasWidth,
    maxContentRight + LAYOUT.crossLaneGutter + LAYOUT.canvasPadding,
  );
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
