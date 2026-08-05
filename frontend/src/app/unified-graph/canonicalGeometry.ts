import type {
  CanonicalBusinessDiagramConfig,
  CanonicalBusinessNode,
} from "./canonicalDiagramTypes";
import { canonicalPathSubpaths } from "./canonicalPath";
import type { Point, Rect } from "./graphTypes";

interface Segment {
  a: Point;
  b: Point;
}

export interface CanonicalGeometryViolation {
  kind:
    | "NODE_OVERLAP"
    | "NODE_OUTSIDE_CANVAS"
    | "EDGE_THROUGH_NODE"
    | "UNEXPECTED_OVERLAP"
    | "LABEL_INSIDE_NODE"
    | "SHARED_BUS_DUPLICATE";
  subject: string;
}

export interface CanonicalGeometryDiagnostics {
  violations: CanonicalGeometryViolation[];
  edgeThroughNode: number;
  unexpectedOverlap: number;
  labelInsideNode: number;
  nodeOverlap: number;
  nodeOutsideCanvas: number;
  sharedBusDuplicate: number;
  total: number;
}

function segments(path: string): Segment[] {
  return canonicalPathSubpaths(path).flatMap((points) =>
    points.slice(1).map((point, index) => ({
      a: points[index],
      b: point,
    })),
  );
}

function rectsOverlap(a: Rect, b: Rect): boolean {
  return (
    Math.max(a.x, b.x) < Math.min(a.x + a.width, b.x + b.width) &&
    Math.max(a.y, b.y) < Math.min(a.y + a.height, b.y + b.height)
  );
}

function pointInsideNode(point: Point, node: CanonicalBusinessNode): boolean {
  return (
    point.x > node.x &&
    point.x < node.x + node.width &&
    point.y > node.y &&
    point.y < node.y + node.height
  );
}

function segmentCrossesNode(
  segment: Segment,
  node: CanonicalBusinessNode,
): boolean {
  if (segment.a.y === segment.b.y) {
    if (segment.a.y <= node.y || segment.a.y >= node.y + node.height) {
      return false;
    }
    const [low, high] = [segment.a.x, segment.b.x].sort((a, b) => a - b);
    return Math.max(low, node.x) < Math.min(high, node.x + node.width);
  }
  if (segment.a.x <= node.x || segment.a.x >= node.x + node.width) {
    return false;
  }
  const [low, high] = [segment.a.y, segment.b.y].sort((a, b) => a - b);
  return Math.max(low, node.y) < Math.min(high, node.y + node.height);
}

function segmentOverlapLength(a: Segment, b: Segment): number {
  const aHorizontal = a.a.y === a.b.y;
  const bHorizontal = b.a.y === b.b.y;
  if (aHorizontal !== bHorizontal) return 0;
  if (aHorizontal) {
    if (a.a.y !== b.a.y) return 0;
    const [a0, a1] = [a.a.x, a.b.x].sort((x, y) => x - y);
    const [b0, b1] = [b.a.x, b.b.x].sort((x, y) => x - y);
    return Math.max(0, Math.min(a1, b1) - Math.max(a0, b0));
  }
  if (a.a.x !== b.a.x) return 0;
  const [a0, a1] = [a.a.y, a.b.y].sort((x, y) => x - y);
  const [b0, b1] = [b.a.y, b.b.y].sort((x, y) => x - y);
  return Math.max(0, Math.min(a1, b1) - Math.max(a0, b0));
}

export function validateCanonicalDiagramGeometry(
  config: CanonicalBusinessDiagramConfig,
): CanonicalGeometryDiagnostics {
  const violations: CanonicalGeometryViolation[] = [];
  const add = (kind: CanonicalGeometryViolation["kind"], subject: string) => {
    if (!violations.some((item) => item.kind === kind && item.subject === subject)) {
      violations.push({ kind, subject });
    }
  };

  config.nodes.forEach((node, index) => {
    if (
      node.x < 0 ||
      node.y < 0 ||
      node.x + node.width > config.canvas.width ||
      node.y + node.height > config.canvas.height
    ) {
      add("NODE_OUTSIDE_CANVAS", node.id);
    }
    for (const other of config.nodes.slice(index + 1)) {
      if (rectsOverlap(node, other)) {
        add("NODE_OVERLAP", `${node.id}|${other.id}`);
      }
    }
  });

  const pathByEdge = new Map(
    config.edges.map((edge) => [edge.id, segments(edge.path)]),
  );
  for (const edge of config.edges) {
    for (const node of config.nodes) {
      if (node.id === edge.sourceRole || node.id === edge.targetRole) continue;
      if (pathByEdge.get(edge.id)?.some((segment) => segmentCrossesNode(segment, node))) {
        add("EDGE_THROUGH_NODE", `${edge.id}|${node.id}`);
      }
    }
    const label = { x: edge.labelX, y: edge.labelY };
    for (const node of config.nodes) {
      if (pointInsideNode(label, node)) {
        add("LABEL_INSIDE_NODE", `${edge.id}|${node.id}`);
      }
    }
  }

  config.edges.forEach((edge, index) => {
    for (const other of config.edges.slice(index + 1)) {
      const sharesRole = [edge.sourceRole, edge.targetRole].some((role) =>
        [other.sourceRole, other.targetRole].includes(role),
      );
      if (sharesRole || (edge.busId && edge.busId === other.busId)) continue;
      const overlaps = pathByEdge
        .get(edge.id)
        ?.some((first) =>
          pathByEdge
            .get(other.id)
            ?.some((second) => segmentOverlapLength(first, second) > 2),
        );
      if (overlaps) add("UNEXPECTED_OVERLAP", `${edge.id}|${other.id}`);
    }
  });

  const busIds = new Set<string>();
  for (const bus of config.buses) {
    if (busIds.has(bus.id)) add("SHARED_BUS_DUPLICATE", bus.id);
    busIds.add(bus.id);
    for (const node of config.nodes) {
      if (node.id === bus.sourceRole) continue;
      if (segments(bus.path).some((segment) => segmentCrossesNode(segment, node))) {
        add("EDGE_THROUGH_NODE", `${bus.id}|${node.id}`);
      }
    }
  }

  const count = (kind: CanonicalGeometryViolation["kind"]) =>
    violations.filter((item) => item.kind === kind).length;
  return {
    violations,
    edgeThroughNode: count("EDGE_THROUGH_NODE"),
    unexpectedOverlap: count("UNEXPECTED_OVERLAP"),
    labelInsideNode: count("LABEL_INSIDE_NODE"),
    nodeOverlap: count("NODE_OVERLAP"),
    nodeOutsideCanvas: count("NODE_OUTSIDE_CANVAS"),
    sharedBusDuplicate: count("SHARED_BUS_DUPLICATE"),
    total: violations.length,
  };
}
