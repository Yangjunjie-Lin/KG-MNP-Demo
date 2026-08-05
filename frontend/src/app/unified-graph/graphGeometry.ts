import type {
  GeometryViolation,
  GraphGeometryDiagnostics,
  LayerGeometry,
  Point,
  RoutedProjectedEdge,
  SharedEdgeBus,
  VisualProjection,
} from "./graphTypes";
import { isOrthogonalPath } from "./orthogonalRouter";

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
  const o3 = orientation(s2.a, s1.a, s2.b);
  const o4 = orientation(s2.a, s1.b, s2.b);
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

export function segmentsOverlap(
  s1: Segment,
  s2: Segment,
  threshold = 4,
): boolean {
  const horizontal =
    s1.a.y === s1.b.y && s2.a.y === s2.b.y && Math.abs(s1.a.y - s2.a.y) < 0.5;
  const vertical =
    s1.a.x === s1.b.x && s2.a.x === s2.b.x && Math.abs(s1.a.x - s2.a.x) < 0.5;
  if (horizontal) {
    return overlapLength1D(s1.a.x, s1.b.x, s2.a.x, s2.b.x) > threshold;
  }
  if (vertical) {
    return overlapLength1D(s1.a.y, s1.b.y, s2.a.y, s2.b.y) > threshold;
  }
  return false;
}

function pathToSegments(points: Point[]): Segment[] {
  const segments: Segment[] = [];
  for (let i = 0; i < points.length - 1; i += 1) {
    segments.push({ a: points[i], b: points[i + 1] });
  }
  return segments;
}

function inflate(rect: Rect, padding: number): Rect {
  return {
    x: rect.x - padding,
    y: rect.y - padding,
    width: rect.width + padding * 2,
    height: rect.height + padding * 2,
  };
}

export function validateUnifiedGraphGeometry(input: {
  nodes: VisualProjection[];
  edges: RoutedProjectedEdge[];
  layers: LayerGeometry[];
  buses?: SharedEdgeBus[];
  danglingEdgeCount?: number;
}): GeometryViolation[] {
  const violations: GeometryViolation[] = [];
  const layerById = new Map(input.layers.map((layer) => [layer.id, layer]));
  const nodeIds = new Set<string>();

  for (const node of input.nodes) {
    if (nodeIds.has(node.projectionId)) {
      violations.push({
        kind: "DUPLICATE_NODE_ID",
        message: `Duplicate projection id ${node.projectionId}`,
      });
    }
    nodeIds.add(node.projectionId);

    const layer = layerById.get(node.layerId);
    if (!layer) {
      violations.push({
        kind: "NODE_OUTSIDE_LAYER",
        message: `Node ${node.projectionId} missing layer ${node.layerId}`,
      });
      continue;
    }
    const inside =
      node.x >= layer.x - 4 &&
      node.y >= layer.y - 4 &&
      node.x + node.width <= layer.x + layer.width + 4 &&
      node.y + node.height <= layer.y + layer.height + 28;
    if (!inside) {
      violations.push({
        kind: "NODE_OUTSIDE_LAYER",
        message: `Node ${node.projectionId} outside layer ${node.layerId}`,
        details: { node, layer },
      });
    }
  }

  for (const edge of input.edges) {
    if (!isOrthogonalPath(edge.path)) {
      violations.push({
        kind: "NON_ORTHOGONAL_PATH",
        message: `Edge ${edge.id} is not orthogonal`,
      });
    }
    if (!nodeIds.has(edge.from) || !nodeIds.has(edge.to)) {
      violations.push({
        kind: "DANGLING_EDGE",
        message: `Edge ${edge.id} has missing endpoint`,
        details: { from: edge.from, to: edge.to },
      });
    }

    if (edge.presentationType === "STRUCTURAL") continue;

    const segments = pathToSegments(edge.points);
    for (const node of input.nodes) {
      if (
        node.projectionId === edge.from ||
        node.projectionId === edge.to
      ) {
        continue;
      }
      const rect = inflate(node, -1);
      for (const segment of segments) {
        // Ignore short stubs near endpoints.
        const length = Math.hypot(segment.a.x - segment.b.x, segment.a.y - segment.b.y);
        if (length < 12) continue;
        if (segmentIntersectsRect(segment, rect)) {
          violations.push({
            kind: "EDGE_THROUGH_NODE",
            message: `Edge ${edge.id} intersects node ${node.projectionId}`,
          });
          break;
        }
      }
    }

    const labelPoint = { x: edge.labelX, y: edge.labelY };
    for (const node of input.nodes) {
      if (node.projectionId === edge.from || node.projectionId === edge.to) continue;
      if (pointInsideRect(labelPoint, node, 2)) {
        violations.push({
          kind: "LABEL_INSIDE_NODE",
          message: `Label of ${edge.id} inside node ${node.projectionId}`,
        });
      }
    }
  }

  for (let i = 0; i < input.edges.length; i += 1) {
    for (let j = i + 1; j < input.edges.length; j += 1) {
      const a = input.edges[i];
      const b = input.edges[j];
      if (
        a.presentationType === "STRUCTURAL" ||
        b.presentationType === "STRUCTURAL"
      ) {
        continue;
      }
      // Shared endpoints naturally share stubs; ignore those pairs.
      if (
        a.from === b.from ||
        a.from === b.to ||
        a.to === b.from ||
        a.to === b.to
      ) {
        continue;
      }
      const aSegs = pathToSegments(a.points);
      const bSegs = pathToSegments(b.points);
      for (const s1 of aSegs) {
        for (const s2 of bSegs) {
          if (segmentsOverlap(s1, s2, 4)) {
            violations.push({
              kind: "SEGMENT_OVERLAP",
              message: `Edges ${a.id} and ${b.id} overlap`,
            });
          }
        }
      }
    }
  }

  const pathCounts = new Map<string, number>();
  for (const edge of input.edges) {
    if (edge.presentationType === "STRUCTURAL") continue;
    pathCounts.set(edge.path, (pathCounts.get(edge.path) ?? 0) + 1);
  }
  for (const [path, count] of pathCounts) {
    if (count > 1) {
      violations.push({
        kind: "DUPLICATE_CROSS_CHANNEL",
        message: `Duplicate path rendered ${count} times`,
        details: { path },
      });
    }
  }

  const busIds = new Set<string>();
  for (const bus of input.buses ?? []) {
    if (busIds.has(bus.id)) {
      violations.push({
        kind: "SHARED_BUS_DUPLICATED",
        message: `Shared bus ${bus.id} duplicated`,
      });
    }
    busIds.add(bus.id);
  }

  if ((input.danglingEdgeCount ?? 0) > 0) {
    violations.push({
      kind: "DANGLING_EDGE",
      message: `Dangling edge count ${input.danglingEdgeCount}`,
    });
  }

  return violations;
}

export function summarizeGeometryViolations(
  violations: GeometryViolation[],
): GraphGeometryDiagnostics {
  const count = (kind: string) =>
    violations.filter((item) => item.kind === kind).length;
  return {
    total: violations.length,
    edgeThroughNode: count("EDGE_THROUGH_NODE"),
    segmentOverlap: count("SEGMENT_OVERLAP"),
    labelInsideNode: count("LABEL_INSIDE_NODE"),
    nodeOutsideLayer: count("NODE_OUTSIDE_LAYER"),
    duplicateCrossChannel: count("DUPLICATE_CROSS_CHANNEL"),
    sharedBusDuplicated: count("SHARED_BUS_DUPLICATED"),
    danglingEdge: count("DANGLING_EDGE"),
    duplicateNodeId: count("DUPLICATE_NODE_ID"),
  };
}
