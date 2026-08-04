import type { PositionedOntologyNode } from "../types/ontology";
import type {
  GeometryViolation,
  LaneGeometry,
  Point,
  RoutedOntologyEdge,
} from "./ontologyGraphTypes";

export interface Rect {
  x: number;
  y: number;
  width: number;
  height: number;
}

export interface Segment {
  a: Point;
  b: Point;
}

export function pointInsideRect(point: Point, rect: Rect, padding = 0): boolean {
  return (
    point.x > rect.x + padding &&
    point.x < rect.x + rect.width - padding &&
    point.y > rect.y + padding &&
    point.y < rect.y + rect.height - padding
  );
}

function orientation(p: Point, q: Point, r: Point): number {
  const value = (q.y - p.y) * (r.x - q.x) - (q.x - p.x) * (r.y - q.y);
  if (value === 0) return 0;
  return value > 0 ? 1 : 2;
}

function onSegment(p: Point, q: Point, r: Point): boolean {
  return (
    q.x <= Math.max(p.x, r.x) &&
    q.x >= Math.min(p.x, r.x) &&
    q.y <= Math.max(p.y, r.y) &&
    q.y >= Math.min(p.y, r.y)
  );
}

function segmentsIntersect(s1: Segment, s2: Segment): boolean {
  const o1 = orientation(s1.a, s1.b, s2.a);
  const o2 = orientation(s1.a, s1.b, s2.b);
  const o3 = orientation(s2.a, s2.b, s1.a);
  const o4 = orientation(s2.a, s2.b, s1.b);

  if (o1 !== o2 && o3 !== o4) return true;
  if (o1 === 0 && onSegment(s1.a, s2.a, s1.b)) return true;
  if (o2 === 0 && onSegment(s1.a, s2.b, s1.b)) return true;
  if (o3 === 0 && onSegment(s2.a, s1.a, s2.b)) return true;
  if (o4 === 0 && onSegment(s2.a, s1.b, s2.b)) return true;
  return false;
}

export function segmentIntersectsRect(segment: Segment, rect: Rect): boolean {
  const corners: Point[] = [
    { x: rect.x, y: rect.y },
    { x: rect.x + rect.width, y: rect.y },
    { x: rect.x + rect.width, y: rect.y + rect.height },
    { x: rect.x, y: rect.y + rect.height },
  ];
  const edges: Segment[] = [
    { a: corners[0], b: corners[1] },
    { a: corners[1], b: corners[2] },
    { a: corners[2], b: corners[3] },
    { a: corners[3], b: corners[0] },
  ];
  if (pointInsideRect(segment.a, rect) || pointInsideRect(segment.b, rect)) {
    return true;
  }
  return edges.some((edge) => segmentsIntersect(segment, edge));
}

function segmentDirection(segment: Segment): "H" | "V" | null {
  if (segment.a.y === segment.b.y && segment.a.x !== segment.b.x) return "H";
  if (segment.a.x === segment.b.x && segment.a.y !== segment.b.y) return "V";
  return null;
}

function overlapLength1D(
  a0: number,
  a1: number,
  b0: number,
  b1: number,
): number {
  const start = Math.max(Math.min(a0, a1), Math.min(b0, b1));
  const end = Math.min(Math.max(a0, a1), Math.max(b0, b1));
  return Math.max(0, end - start);
}

/** Same-direction collinear segments overlapping by more than threshold. */
export function segmentsOverlap(
  s1: Segment,
  s2: Segment,
  threshold = 4,
): boolean {
  const d1 = segmentDirection(s1);
  const d2 = segmentDirection(s2);
  if (!d1 || !d2 || d1 !== d2) return false;

  if (d1 === "H") {
    if (s1.a.y !== s2.a.y) return false;
    return overlapLength1D(s1.a.x, s1.b.x, s2.a.x, s2.b.x) > threshold;
  }

  if (s1.a.x !== s2.a.x) return false;
  return overlapLength1D(s1.a.y, s1.b.y, s2.a.y, s2.b.y) > threshold;
}

export function edgeSegments(edge: RoutedOntologyEdge): Segment[] {
  const segments: Segment[] = [];
  for (let i = 0; i < edge.points.length - 1; i += 1) {
    segments.push({ a: edge.points[i], b: edge.points[i + 1] });
  }
  return segments;
}

function nodeRect(node: PositionedOntologyNode): Rect {
  return { x: node.x, y: node.y, width: node.width, height: node.height };
}

function isEndpointTouch(
  segment: Segment,
  rect: Rect,
  endpoint: Point,
): boolean {
  const onBoundary =
    (Math.abs(endpoint.x - rect.x) <= 1 &&
      endpoint.y >= rect.y - 1 &&
      endpoint.y <= rect.y + rect.height + 1) ||
    (Math.abs(endpoint.x - (rect.x + rect.width)) <= 1 &&
      endpoint.y >= rect.y - 1 &&
      endpoint.y <= rect.y + rect.height + 1) ||
    (Math.abs(endpoint.y - rect.y) <= 1 &&
      endpoint.x >= rect.x - 1 &&
      endpoint.x <= rect.x + rect.width + 1) ||
    (Math.abs(endpoint.y - (rect.y + rect.height)) <= 1 &&
      endpoint.x >= rect.x - 1 &&
      endpoint.x <= rect.x + rect.width + 1);

  if (!onBoundary) return false;
  const other = segment.a === endpoint ? segment.b : segment.a;
  return !pointInsideRect(other, rect, 1);
}

export function validateGraphGeometry(input: {
  nodes: PositionedOntologyNode[];
  edges: RoutedOntologyEdge[];
  lanes: LaneGeometry[];
  contentRight: number;
}): GeometryViolation[] {
  const violations: GeometryViolation[] = [];
  const nodeById = new Map(input.nodes.map((node) => [node.id, node]));
  const laneById = new Map(input.lanes.map((lane) => [lane.id, lane]));

  for (const node of input.nodes) {
    const lane = laneById.get(node.laneId);
    if (!lane) {
      violations.push({
        kind: "missing-lane",
        message: `Node ${node.localName} has unknown lane`,
      });
      continue;
    }
    const inside =
      node.x >= lane.contentX - 0.5 &&
      node.y >= lane.y - 0.5 &&
      node.x + node.width <= lane.x + lane.width + 0.5 &&
      node.y + node.height <= lane.y + lane.height + 0.5;
    if (!inside) {
      violations.push({
        kind: "node-outside-lane",
        message: `Node ${node.localName} outside lane ${node.laneId}`,
        details: { nodeId: node.id, laneId: node.laneId },
      });
    }
  }

  for (const edge of input.edges) {
    const source = nodeById.get(edge.from);
    const target = nodeById.get(edge.to);
    if (!source || !target) continue;

    for (const segment of edgeSegments(edge)) {
      for (const node of input.nodes) {
        if (node.id === source.id || node.id === target.id) continue;
        const rect = nodeRect(node);
        if (!segmentIntersectsRect(segment, rect)) continue;
        // Allow tiny endpoint contact only for source/target; others are violations.
        violations.push({
          kind: "edge-through-node",
          message: `Edge ${edge.id} intersects node ${node.localName}`,
          details: { edgeId: edge.id, nodeId: node.id },
        });
      }

      // Endpoints must not enter source/target more than 1px.
      for (const endpointNode of [source, target]) {
        const rect = nodeRect(endpointNode);
        if (
          pointInsideRect(segment.a, rect, 1) ||
          pointInsideRect(segment.b, rect, 1)
        ) {
          if (
            !isEndpointTouch(segment, rect, segment.a) &&
            !isEndpointTouch(segment, rect, segment.b)
          ) {
            violations.push({
              kind: "edge-inside-endpoint",
              message: `Edge ${edge.id} enters node ${endpointNode.localName}`,
              details: { edgeId: edge.id, nodeId: endpointNode.id },
            });
          }
        }
      }
    }

    if (pointInsideRect({ x: edge.labelX, y: edge.labelY }, nodeRect(source)) ||
      pointInsideRect({ x: edge.labelX, y: edge.labelY }, nodeRect(target))) {
      violations.push({
        kind: "label-inside-node",
        message: `Label for ${edge.id} inside endpoint node`,
        details: { edgeId: edge.id },
      });
    }
    for (const node of input.nodes) {
      if (node.id === source.id || node.id === target.id) continue;
      if (pointInsideRect({ x: edge.labelX, y: edge.labelY }, nodeRect(node))) {
        violations.push({
          kind: "label-inside-node",
          message: `Label for ${edge.id} inside node ${node.localName}`,
          details: { edgeId: edge.id, nodeId: node.id },
        });
      }
    }

    if (edge.kind === "CROSS_LANE") {
      const expectedMin = input.contentRight + 24;
      const routeXs = edge.points
        .filter((point, index, all) => {
          if (index === 0 || index === all.length - 1) return false;
          return true;
        })
        .map((point) => point.x);
      const gutterX = routeXs.find((x) => x >= expectedMin - 0.5);
      if (gutterX === undefined) {
        violations.push({
          kind: "cross-lane-channel",
          message: `Cross-lane edge ${edge.id} missing gutter channel`,
          details: { edgeId: edge.id },
        });
      }
    }
  }

  for (let i = 0; i < input.edges.length; i += 1) {
    for (let j = i + 1; j < input.edges.length; j += 1) {
      const a = input.edges[i];
      const b = input.edges[j];
      const segmentsA = edgeSegments(a);
      const segmentsB = edgeSegments(b);
      // Skip port-attachment segments (first/last): multiple edges may share a port.
      for (let ai = 1; ai < segmentsA.length - 1; ai += 1) {
        for (let bi = 1; bi < segmentsB.length - 1; bi += 1) {
          if (segmentsOverlap(segmentsA[ai], segmentsB[bi], 4)) {
            violations.push({
              kind: "segment-overlap",
              message: `Edges ${a.id} and ${b.id} overlap > 4px`,
              details: { edgeA: a.id, edgeB: b.id },
            });
          }
        }
      }
    }
  }

  const crossChannels = input.edges
    .filter((edge) => edge.kind === "CROSS_LANE")
    .map((edge) => edge.channel);
  const unique = new Set(crossChannels);
  if (unique.size !== crossChannels.length) {
    violations.push({
      kind: "duplicate-cross-channel",
      message: "Duplicate cross-lane channels detected",
      details: { channels: crossChannels },
    });
  }

  return violations;
}

export function assertGraphGeometry(
  input: Parameters<typeof validateGraphGeometry>[0],
  mode: "warn" | "throw" = "warn",
): GeometryViolation[] {
  const violations = validateGraphGeometry(input);
  for (const violation of violations) {
    if (mode === "throw") {
      throw new Error(`[ontology-layout] geometry violation: ${violation.message}`);
    }
    console.warn("[ontology-layout] geometry violation", violation);
  }
  return violations;
}
