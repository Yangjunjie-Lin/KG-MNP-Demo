import { layerIndex } from "./businessLayerConfig";
import type {
  CollapsedProjectedEdge,
  LayerGeometry,
  Point,
  PortAssignment,
  Rect,
  RoutedProjectedEdge,
  VisualProjection,
} from "./graphTypes";
import { collapsedRelationLabel } from "../i18n/graphChineseResolver";

const EDGE_CHANNEL_GAP = 14;
const ROUTE_CLEARANCE = 6;
const GUTTER_GAP = 24;
const FALLBACK_STUB = 10;

export type RouteSide = "left" | "right" | "top" | "bottom";

export interface RouteGutter {
  left: number;
  right: number;
  top: number;
  bottom: number;
}

export interface OrthogonalRouteOptions {
  obstacles?: readonly Rect[];
  sourceSide?: RouteSide;
  targetSide?: RouteSide;
  clearance?: number;
  gutter?: Partial<RouteGutter>;
  channel?: number;
}

interface PortCandidate {
  point: Point;
  side: RouteSide;
  penalty: number;
}

interface EndpointCandidate {
  source: PortCandidate;
  target: PortCandidate;
  penalty: number;
}

function samePoint(a: Point, b: Point): boolean {
  return a.x === b.x && a.y === b.y;
}

function normalizePoints(points: readonly Point[]): Point[] {
  const result: Point[] = [];
  for (const point of points) {
    if (result.length && samePoint(result[result.length - 1], point)) continue;
    result.push({ ...point });

    while (result.length >= 3) {
      const a = result[result.length - 3];
      const b = result[result.length - 2];
      const c = result[result.length - 1];
      const collinear =
        (a.x === b.x && b.x === c.x) ||
        (a.y === b.y && b.y === c.y);
      if (!collinear) break;
      result.splice(result.length - 2, 1);
    }
  }
  return result;
}

function segmentDirection(a: Point, b: Point): "H" | "V" {
  if (a.y === b.y && a.x !== b.x) return "H";
  if (a.x === b.x && a.y !== b.y) return "V";
  throw new Error(
    `Geometry error: non-orthogonal or zero-length segment (${a.x},${a.y})->(${b.x},${b.y})`,
  );
}

export function countRouteBends(points: readonly Point[]): number {
  const normalized = normalizePoints(points);
  let bends = 0;
  let previousDirection: "H" | "V" | null = null;
  for (let index = 0; index < normalized.length - 1; index += 1) {
    const direction = segmentDirection(normalized[index], normalized[index + 1]);
    if (previousDirection && previousDirection !== direction) bends += 1;
    previousDirection = direction;
  }
  return bends;
}

function pointsToPath(points: readonly Point[]): string {
  const normalized = normalizePoints(points);
  if (!normalized.length) return "";
  let path = `M ${normalized[0].x} ${normalized[0].y}`;
  for (let index = 1; index < normalized.length; index += 1) {
    const previous = normalized[index - 1];
    const point = normalized[index];
    const direction = segmentDirection(previous, point);
    path += direction === "H" ? ` H ${point.x}` : ` V ${point.y}`;
  }
  return path;
}

function midpoint(a: Point, b: Point): Point {
  return { x: (a.x + b.x) / 2, y: (a.y + b.y) / 2 };
}

function longestHorizontalLabel(points: readonly Point[]): Point {
  let bestLength = -1;
  let best: Point = points[0] ?? { x: 0, y: 0 };
  for (let index = 0; index < points.length - 1; index += 1) {
    const a = points[index];
    const b = points[index + 1];
    if (a.y !== b.y) continue;
    const length = Math.abs(b.x - a.x);
    if (length > bestLength) {
      bestLength = length;
      best = midpoint(a, b);
    }
  }
  if (bestLength < 0) {
    return points[Math.floor(points.length / 2)] ?? { x: 0, y: 0 };
  }
  return best;
}

function segmentIntersectsRectInterior(a: Point, b: Point, rect: Rect): boolean {
  const right = rect.x + rect.width;
  const bottom = rect.y + rect.height;
  if (a.y === b.y) {
    if (a.y <= rect.y || a.y >= bottom) return false;
    const start = Math.max(Math.min(a.x, b.x), rect.x);
    const end = Math.min(Math.max(a.x, b.x), right);
    return start < end;
  }
  if (a.x === b.x) {
    if (a.x <= rect.x || a.x >= right) return false;
    const start = Math.max(Math.min(a.y, b.y), rect.y);
    const end = Math.min(Math.max(a.y, b.y), bottom);
    return start < end;
  }
  return true;
}

function pathAvoidsObstacles(
  points: readonly Point[],
  obstacles: readonly Rect[],
): boolean {
  for (let index = 0; index < points.length - 1; index += 1) {
    for (const obstacle of obstacles) {
      if (segmentIntersectsRectInterior(points[index], points[index + 1], obstacle)) {
        return false;
      }
    }
  }
  return true;
}

function sourceDirectionMatches(points: readonly Point[], side?: RouteSide): boolean {
  if (!side) return true;
  const [source, next] = points;
  if (!source || !next) return false;
  if (side === "left") return source.y === next.y && next.x < source.x;
  if (side === "right") return source.y === next.y && next.x > source.x;
  if (side === "top") return source.x === next.x && next.y < source.y;
  return source.x === next.x && next.y > source.y;
}

function targetDirectionMatches(points: readonly Point[], side?: RouteSide): boolean {
  if (!side) return true;
  const previous = points[points.length - 2];
  const target = points[points.length - 1];
  if (!previous || !target) return false;
  if (side === "left") return previous.y === target.y && previous.x < target.x;
  if (side === "right") return previous.y === target.y && previous.x > target.x;
  if (side === "top") return previous.x === target.x && previous.y < target.y;
  return previous.x === target.x && previous.y > target.y;
}

function pathLength(points: readonly Point[]): number {
  let length = 0;
  for (let index = 0; index < points.length - 1; index += 1) {
    length +=
      Math.abs(points[index + 1].x - points[index].x) +
      Math.abs(points[index + 1].y - points[index].y);
  }
  return length;
}

function validPath(
  rawPoints: readonly Point[],
  options: OrthogonalRouteOptions,
  requiredBends?: number,
): Point[] | null {
  const points = normalizePoints(rawPoints);
  if (points.length < 2) return null;
  let bends: number;
  try {
    bends = countRouteBends(points);
  } catch {
    return null;
  }
  if (requiredBends !== undefined && bends !== requiredBends) return null;
  if (bends > 4) return null;
  if (!sourceDirectionMatches(points, options.sourceSide)) return null;
  if (!targetDirectionMatches(points, options.targetSide)) return null;
  if (!pathAvoidsObstacles(points, options.obstacles ?? [])) return null;
  return points;
}

function bestPath(
  candidates: readonly (Point[] | null)[],
): Point[] | null {
  const paths = candidates.filter((path): path is Point[] => Boolean(path));
  paths.sort(
    (a, b) =>
      pathLength(a) - pathLength(b) ||
      pointsToPath(a).localeCompare(pointsToPath(b)),
  );
  return paths[0] ?? null;
}

export function routeDirect(
  source: Point,
  target: Point,
  options: OrthogonalRouteOptions = {},
): Point[] | null {
  if (source.x !== target.x && source.y !== target.y) return null;
  return validPath([source, target], options, 0);
}

export function routeSingleElbow(
  source: Point,
  target: Point,
  options: OrthogonalRouteOptions = {},
): Point[] | null {
  return bestPath([
    validPath(
      [source, { x: target.x, y: source.y }, target],
      options,
      1,
    ),
    validPath(
      [source, { x: source.x, y: target.y }, target],
      options,
      1,
    ),
  ]);
}

function distinctNumbers(values: readonly number[]): number[] {
  return [...new Set(values.filter(Number.isFinite))];
}

export function routeDoubleElbow(
  source: Point,
  target: Point,
  options: OrthogonalRouteOptions = {},
): Point[] | null {
  const clearance = options.clearance ?? ROUTE_CLEARANCE;
  const obstacles = options.obstacles ?? [];
  const xRails = distinctNumbers([
    (source.x + target.x) / 2,
    ...obstacles.flatMap((obstacle) => [
      obstacle.x - clearance,
      obstacle.x + obstacle.width + clearance,
    ]),
  ]);
  const yRails = distinctNumbers([
    (source.y + target.y) / 2,
    ...obstacles.flatMap((obstacle) => [
      obstacle.y - clearance,
      obstacle.y + obstacle.height + clearance,
    ]),
  ]);
  return bestPath([
    ...xRails.map((x) =>
      validPath(
        [source, { x, y: source.y }, { x, y: target.y }, target],
        options,
        2,
      ),
    ),
    ...yRails.map((y) =>
      validPath(
        [source, { x: source.x, y }, { x: target.x, y }, target],
        options,
        2,
      ),
    ),
  ]);
}

function moveOutward(point: Point, side: RouteSide | undefined, distance: number): Point {
  if (side === "left") return { x: point.x - distance, y: point.y };
  if (side === "right") return { x: point.x + distance, y: point.y };
  if (side === "top") return { x: point.x, y: point.y - distance };
  if (side === "bottom") return { x: point.x, y: point.y + distance };
  return point;
}

function obstacleBounds(
  source: Point,
  target: Point,
  obstacles: readonly Rect[],
): RouteGutter {
  return {
    left: Math.min(source.x, target.x, ...obstacles.map((rect) => rect.x)),
    right: Math.max(
      source.x,
      target.x,
      ...obstacles.map((rect) => rect.x + rect.width),
    ),
    top: Math.min(source.y, target.y, ...obstacles.map((rect) => rect.y)),
    bottom: Math.max(
      source.y,
      target.y,
      ...obstacles.map((rect) => rect.y + rect.height),
    ),
  };
}

export function routeWithGutter(
  source: Point,
  target: Point,
  options: OrthogonalRouteOptions = {},
): Point[] | null {
  const obstacles = options.obstacles ?? [];
  const bounds = obstacleBounds(source, target, obstacles);
  const channel = options.channel ?? 0;
  const channelOffset = channel * EDGE_CHANNEL_GAP;
  const gutter: RouteGutter = {
    left: (options.gutter?.left ?? bounds.left - GUTTER_GAP) - channelOffset,
    right: (options.gutter?.right ?? bounds.right + GUTTER_GAP) + channelOffset,
    top: (options.gutter?.top ?? bounds.top - GUTTER_GAP) - channelOffset,
    bottom: (options.gutter?.bottom ?? bounds.bottom + GUTTER_GAP) + channelOffset,
  };
  // Channel separation belongs on the outer gutter. Growing the endpoint stubs
  // by the global edge index can push a late edge through a neighbouring node.
  const stubDistance = FALLBACK_STUB;
  const sourceStub = moveOutward(source, options.sourceSide, stubDistance);
  const targetStub = moveOutward(target, options.targetSide, stubDistance);

  return bestPath([
    ...[gutter.left, gutter.right].map((x) =>
      validPath(
        [
          source,
          sourceStub,
          { x, y: sourceStub.y },
          { x, y: targetStub.y },
          targetStub,
          target,
        ],
        options,
      ),
    ),
    ...[gutter.top, gutter.bottom].map((y) =>
      validPath(
        [
          source,
          sourceStub,
          { x: sourceStub.x, y },
          { x: targetStub.x, y },
          targetStub,
          target,
        ],
        options,
      ),
    ),
  ]);
}

export function getNodePorts(
  node: VisualProjection,
  offsets?: Partial<Record<RouteSide, number>>,
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

  const sideFor = (node: VisualProjection, other: VisualProjection): RouteSide => {
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
    const [nodeId, side] = key.split("|") as [string, RouteSide];
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

function portCandidates(
  edgeId: string,
  node: VisualProjection,
  side: RouteSide,
  offsets: Map<string, number>,
): PortCandidate[] {
  const offset = offsets.get(`${edgeId}|${node.projectionId}|${side}`) ?? 0;
  const assigned = getNodePorts(node, { [side]: offset })[side];
  const centered = getNodePorts(node)[side];
  if (samePoint(assigned, centered)) return [{ point: assigned, side, penalty: 0 }];
  return [
    { point: assigned, side, penalty: 0 },
    { point: centered, side, penalty: 2 },
  ];
}

function preferredSides(
  source: VisualProjection,
  target: VisualProjection,
): [RouteSide, RouteSide] {
  if (source.layerId !== target.layerId) {
    return layerIndex(source.layerId) < layerIndex(target.layerId)
      ? ["bottom", "top"]
      : ["top", "bottom"];
  }
  if (source.x + source.width <= target.x) return ["right", "left"];
  if (target.x + target.width <= source.x) return ["left", "right"];
  const sourceCenterY = source.y + source.height / 2;
  const targetCenterY = target.y + target.height / 2;
  return sourceCenterY <= targetCenterY
    ? ["bottom", "top"]
    : ["top", "bottom"];
}

const ROUTE_SIDES: readonly RouteSide[] = ["left", "right", "top", "bottom"];

function endpointCandidates(
  edgeId: string,
  source: VisualProjection,
  target: VisualProjection,
  offsets: Map<string, number>,
): EndpointCandidate[] {
  const [preferredSource, preferredTarget] = preferredSides(source, target);
  const candidates: EndpointCandidate[] = [];
  for (const sourceSide of ROUTE_SIDES) {
    for (const targetSide of ROUTE_SIDES) {
      for (const sourcePort of portCandidates(edgeId, source, sourceSide, offsets)) {
        for (const targetPort of portCandidates(edgeId, target, targetSide, offsets)) {
          if (samePoint(sourcePort.point, targetPort.point)) continue;
          const sidePenalty =
            (sourceSide === preferredSource ? 0 : 400) +
            (targetSide === preferredTarget ? 0 : 400);
          candidates.push({
            source: sourcePort,
            target: targetPort,
            penalty: sidePenalty + sourcePort.penalty + targetPort.penalty,
          });
        }
      }
    }
  }
  return candidates.sort((a, b) => a.penalty - b.penalty);
}

function inflateRect(rect: Rect, padding: number): Rect {
  return {
    x: rect.x - padding,
    y: rect.y - padding,
    width: rect.width + padding * 2,
    height: rect.height + padding * 2,
  };
}

function selectRoute(
  edgeId: string,
  source: VisualProjection,
  target: VisualProjection,
  endpoints: readonly EndpointCandidate[],
  obstacles: readonly Rect[],
  gutter: RouteGutter,
  channel: number,
): Point[] {
  const stages = [
    routeDirect,
    routeSingleElbow,
    routeDoubleElbow,
    routeWithGutter,
  ] as const;

  for (const route of stages) {
    const candidates: Array<{ points: Point[]; score: number }> = [];
    for (const endpoint of endpoints) {
      const options: OrthogonalRouteOptions = {
        obstacles,
        sourceSide: endpoint.source.side,
        targetSide: endpoint.target.side,
        gutter,
        channel,
      };
      const points = route(endpoint.source.point, endpoint.target.point, options);
      if (!points) continue;
      candidates.push({
        points,
        score: endpoint.penalty + pathLength(points),
      });
    }
    candidates.sort(
      (a, b) =>
        a.score - b.score ||
        pointsToPath(a.points).localeCompare(pointsToPath(b.points)),
    );
    const selected = candidates[0]?.points;
    if (!selected) continue;
    const bendCount = countRouteBends(selected);
    if (bendCount > 4) {
      throw new Error(
        `Geometry error routing edge ${edgeId}: ${bendCount} bends exceeds maximum 4`,
      );
    }
    return selected;
  }

  throw new Error(
    `Geometry error routing edge ${edgeId}: no obstacle-free route with 4 or fewer bends`,
  );
}

function routeSelfLoop(
  node: VisualProjection,
  obstacles: readonly Rect[],
): Point[] {
  const ports = getNodePorts(node);
  const clearances = [10, 16, 22];
  for (const clearance of clearances) {
    const candidates: Array<{
      points: Point[];
      sourceSide: RouteSide;
      targetSide: RouteSide;
    }> = [
      {
        sourceSide: "right",
        targetSide: "top",
        points: [
          ports.right,
          { x: ports.right.x + clearance, y: ports.right.y },
          { x: ports.right.x + clearance, y: ports.top.y - clearance },
          { x: ports.top.x, y: ports.top.y - clearance },
          ports.top,
        ],
      },
      {
        sourceSide: "left",
        targetSide: "top",
        points: [
          ports.left,
          { x: ports.left.x - clearance, y: ports.left.y },
          { x: ports.left.x - clearance, y: ports.top.y - clearance },
          { x: ports.top.x, y: ports.top.y - clearance },
          ports.top,
        ],
      },
      {
        sourceSide: "right",
        targetSide: "bottom",
        points: [
          ports.right,
          { x: ports.right.x + clearance, y: ports.right.y },
          { x: ports.right.x + clearance, y: ports.bottom.y + clearance },
          { x: ports.bottom.x, y: ports.bottom.y + clearance },
          ports.bottom,
        ],
      },
      {
        sourceSide: "left",
        targetSide: "bottom",
        points: [
          ports.left,
          { x: ports.left.x - clearance, y: ports.left.y },
          { x: ports.left.x - clearance, y: ports.bottom.y + clearance },
          { x: ports.bottom.x, y: ports.bottom.y + clearance },
          ports.bottom,
        ],
      },
    ];
    const valid = candidates
      .map((candidate) =>
        validPath(candidate.points, {
          obstacles,
          sourceSide: candidate.sourceSide,
          targetSide: candidate.targetSide,
        }),
      )
      .filter((points): points is Point[] => Boolean(points));
    if (valid.length) return bestPath(valid) ?? valid[0];
  }
  throw new Error(
    `Geometry error routing self-loop at ${node.projectionId}: no local route with 3 bends`,
  );
}

export function routeProjectedEdges(input: {
  nodes: VisualProjection[];
  collapsedEdges: CollapsedProjectedEdge[];
  layers: LayerGeometry[];
  contentRight: number;
}): RoutedProjectedEdge[] {
  const nodeById = new Map(input.nodes.map((node) => [node.projectionId, node]));
  const offsets = portOffsetLookup(
    assignNodePorts(input.nodes, input.collapsedEdges),
  );

  for (const edge of input.collapsedEdges) {
    if (!nodeById.has(edge.from) || !nodeById.has(edge.to)) {
      throw new Error(
        `Cannot route edge ${edge.id}: missing endpoint ${edge.from} or ${edge.to}`,
      );
    }
  }

  const intra = input.collapsedEdges
    .filter((edge) => nodeById.get(edge.from)?.layerId === nodeById.get(edge.to)?.layerId)
    .sort((a, b) => compareEdges(a, b, nodeById));
  const cross = input.collapsedEdges
    .filter((edge) => nodeById.get(edge.from)?.layerId !== nodeById.get(edge.to)?.layerId)
    .sort((a, b) => compareEdges(a, b, nodeById));

  const minNodeX = Math.min(...input.nodes.map((node) => node.x), 0);
  const maxNodeRight = Math.max(
    ...input.nodes.map((node) => node.x + node.width),
    input.contentRight,
  );
  const minLayerX = Math.min(...input.layers.map((layer) => layer.x), minNodeX);
  const maxLayerRight = Math.max(
    ...input.layers.map((layer) => layer.x + layer.width),
    maxNodeRight,
  );
  const minLayerY = Math.min(...input.layers.map((layer) => layer.y), 0);
  const maxLayerBottom = Math.max(
    ...input.layers.map((layer) => layer.y + layer.height),
    ...input.nodes.map((node) => node.y + node.height),
  );
  const gutter: RouteGutter = {
    left: minLayerX - GUTTER_GAP,
    right: maxLayerRight + GUTTER_GAP,
    top: minLayerY - GUTTER_GAP,
    bottom: maxLayerBottom + GUTTER_GAP,
  };

  const routeGroup = (
    edges: readonly CollapsedProjectedEdge[],
    kind: RoutedProjectedEdge["kind"],
  ): RoutedProjectedEdge[] => {
    const nextChannelByLayer = new Map<string, number>();
    return edges.map((edge, index) => {
      const source = nodeById.get(edge.from)!;
      const target = nodeById.get(edge.to)!;
      const channel =
        kind === "INTRA_LAYER"
          ? nextChannelByLayer.get(source.layerId) ?? 0
          : index;
      if (kind === "INTRA_LAYER") {
        nextChannelByLayer.set(source.layerId, channel + 1);
      }
      const obstacles = input.nodes.map((node) =>
        node.projectionId === source.projectionId ||
        node.projectionId === target.projectionId
          ? node
          : inflateRect(node, ROUTE_CLEARANCE),
      );
      const points =
        source.projectionId === target.projectionId
          ? routeSelfLoop(
              source,
              input.nodes
                .filter((node) => node.projectionId !== source.projectionId)
                .map((node) => inflateRect(node, ROUTE_CLEARANCE)),
            )
          : selectRoute(
              edge.id,
              source,
              target,
              endpointCandidates(edge.id, source, target, offsets),
              obstacles,
              gutter,
              channel,
            );
      const labelPoint = longestHorizontalLabel(points);
      const labels = edge.edges.map((item) => item.labelZh);
      return {
        id: edge.id,
        from: edge.from,
        to: edge.to,
        edges: edge.edges,
        points,
        path: pointsToPath(points),
        labelX: labelPoint.x,
        labelY: labelPoint.y - 8,
        labelZh: collapsedRelationLabel(labels),
        kind,
        channel,
        presentationType: edge.edges[0]?.presentationType ?? "ONTOLOGY",
        state: edge.edges[0]?.state,
      };
    });
  };

  return [...routeGroup(intra, "INTRA_LAYER"), ...routeGroup(cross, "CROSS_LAYER")]
    .sort((a, b) => {
      if (a.kind !== b.kind) return a.kind === "INTRA_LAYER" ? -1 : 1;
      return a.id.localeCompare(b.id);
    });
}

export function isOrthogonalPath(path: string): boolean {
  if (!path) return false;
  if (/[CQLASTcqlast]/i.test(path.replace(/\s+/g, ""))) return false;
  return /[MHVmhv]/.test(path);
}
