import type {
  CanonicalBusinessNode,
  CanonicalPort,
  CanonicalSharedBus,
  CanonicalStructuralEdge,
} from "./canonicalDiagramTypes";
import {
  canonicalPathEndpoints,
  canonicalPathSubpaths,
} from "./canonicalPath";
import type { Point } from "./graphTypes";

export interface CanonicalEdgeEndpointValidation {
  edgeId: string;
  sourceConnected: boolean;
  targetConnected: boolean;
  sourceDistance: number;
  targetDistance: number;
}

export interface CanonicalEdgeEndpointValidationInput {
  edges: readonly CanonicalStructuralEdge[];
  nodes: readonly CanonicalBusinessNode[];
  buses?: readonly CanonicalSharedBus[];
  tolerance?: number;
}

interface Segment {
  start: Point;
  end: Point;
}

function pointToSegmentDistance(point: Point, segment: Segment): number {
  const dx = segment.end.x - segment.start.x;
  const dy = segment.end.y - segment.start.y;
  const lengthSquared = dx * dx + dy * dy;
  if (lengthSquared === 0) {
    return Math.hypot(point.x - segment.start.x, point.y - segment.start.y);
  }

  const projected =
    ((point.x - segment.start.x) * dx +
      (point.y - segment.start.y) * dy) /
    lengthSquared;
  const t = Math.max(0, Math.min(1, projected));
  return Math.hypot(
    point.x - (segment.start.x + t * dx),
    point.y - (segment.start.y + t * dy),
  );
}

function nodePortSegment(
  node: CanonicalBusinessNode,
  port: CanonicalPort,
): Segment {
  if (port === "LEFT") {
    return {
      start: { x: node.x, y: node.y },
      end: { x: node.x, y: node.y + node.height },
    };
  }
  if (port === "RIGHT") {
    return {
      start: { x: node.x + node.width, y: node.y },
      end: { x: node.x + node.width, y: node.y + node.height },
    };
  }
  if (port === "TOP") {
    return {
      start: { x: node.x, y: node.y },
      end: { x: node.x + node.width, y: node.y },
    };
  }
  return {
    start: { x: node.x, y: node.y + node.height },
    end: { x: node.x + node.width, y: node.y + node.height },
  };
}

function distanceToNodePort(
  point: Point,
  node: CanonicalBusinessNode | undefined,
  port: CanonicalPort,
): number {
  if (!node) return Number.POSITIVE_INFINITY;
  return pointToSegmentDistance(point, nodePortSegment(node, port));
}

function pathSegments(path: string): Segment[] {
  const result: Segment[] = [];
  for (const points of canonicalPathSubpaths(path)) {
    for (let index = 1; index < points.length; index += 1) {
      result.push({ start: points[index - 1], end: points[index] });
    }
  }
  return result;
}

function distanceToPath(point: Point, path: string): number {
  const segments = pathSegments(path);
  if (segments.length === 0) return Number.POSITIVE_INFINITY;
  return Math.min(
    ...segments.map((segment) => pointToSegmentDistance(point, segment)),
  );
}

function subpathsAreConnected(path: string, tolerance: number): boolean {
  const subpaths = canonicalPathSubpaths(path);
  if (subpaths.length === 0 || subpaths.some((points) => points.length < 2)) {
    return false;
  }
  for (let index = 1; index < subpaths.length; index += 1) {
    const previous = subpaths[index - 1];
    const current = subpaths[index];
    if (
      Math.hypot(
        previous[previous.length - 1].x - current[0].x,
        previous[previous.length - 1].y - current[0].y,
      ) > tolerance
    ) {
      return false;
    }
  }
  return true;
}

function validateEdge(input: {
  edge: CanonicalStructuralEdge;
  nodeById: ReadonlyMap<string, CanonicalBusinessNode>;
  busById: ReadonlyMap<string, CanonicalSharedBus>;
  tolerance: number;
}): CanonicalEdgeEndpointValidation {
  const { edge, nodeById, busById, tolerance } = input;
  const source = nodeById.get(edge.sourceRole);
  const target = nodeById.get(edge.targetRole);
  let sourceDistance = Number.POSITIVE_INFINITY;
  let targetDistance = Number.POSITIVE_INFINITY;
  let sourceConnected = false;
  let targetConnected = false;

  try {
    const edgeSubpaths = canonicalPathSubpaths(edge.path);
    const edgeIsContinuous =
      edgeSubpaths.length === 1 && edgeSubpaths[0].length >= 2;
    const endpoints = canonicalPathEndpoints(edge.path);
    targetDistance = distanceToNodePort(endpoints.end, target, edge.targetPort);
    targetConnected =
      edgeIsContinuous &&
      edge.toRole === edge.targetRole &&
      targetDistance <= tolerance;

    if (!edge.busId) {
      sourceDistance = distanceToNodePort(
        endpoints.start,
        source,
        edge.sourcePort,
      );
      sourceConnected =
        edgeIsContinuous &&
        edge.fromRole === edge.sourceRole &&
        sourceDistance <= tolerance;
    } else {
      const bus = busById.get(edge.busId);
      if (bus) {
        const busEndpoints = canonicalPathEndpoints(bus.path);
        const busSource = nodeById.get(bus.sourceRole);
        const busSourceDistance = distanceToNodePort(
          busEndpoints.start,
          busSource,
          bus.sourcePort,
        );
        const branchDistance = distanceToPath(endpoints.start, bus.path);
        sourceDistance = Math.max(busSourceDistance, branchDistance);
        sourceConnected =
          edge.fromRole === edge.sourceRole &&
          edgeIsContinuous &&
          bus.sourceRole === edge.sourceRole &&
          bus.sourcePort === edge.sourcePort &&
          bus.edgeIds.includes(edge.id) &&
          subpathsAreConnected(bus.path, tolerance) &&
          sourceDistance <= tolerance;
      }
    }
  } catch {
    // Invalid paths are reported as disconnected endpoints with infinite distance.
  }

  return {
    edgeId: edge.id,
    sourceConnected,
    targetConnected,
    sourceDistance,
    targetDistance,
  };
}

export function validateCanonicalEdgeEndpoints(
  input: CanonicalEdgeEndpointValidationInput,
): CanonicalEdgeEndpointValidation[];
export function validateCanonicalEdgeEndpoints(
  edges: readonly CanonicalStructuralEdge[],
  nodes: readonly CanonicalBusinessNode[],
  buses?: readonly CanonicalSharedBus[],
  tolerance?: number,
): CanonicalEdgeEndpointValidation[];
export function validateCanonicalEdgeEndpoints(
  inputOrEdges:
    | CanonicalEdgeEndpointValidationInput
    | readonly CanonicalStructuralEdge[],
  nodesArgument: readonly CanonicalBusinessNode[] = [],
  busesArgument: readonly CanonicalSharedBus[] = [],
  toleranceArgument = 2,
): CanonicalEdgeEndpointValidation[] {
  const isEdgeArray = (
    value:
      | CanonicalEdgeEndpointValidationInput
      | readonly CanonicalStructuralEdge[],
  ): value is readonly CanonicalStructuralEdge[] => Array.isArray(value);
  const input: CanonicalEdgeEndpointValidationInput = isEdgeArray(inputOrEdges)
    ? {
        edges: inputOrEdges,
        nodes: nodesArgument,
        buses: busesArgument,
        tolerance: toleranceArgument,
      }
    : inputOrEdges;
  const tolerance = input.tolerance ?? 2;
  const nodeById = new Map(input.nodes.map((node) => [node.id, node]));
  const busById = new Map((input.buses ?? []).map((bus) => [bus.id, bus]));

  return input.edges.map((edge) =>
    validateEdge({ edge, nodeById, busById, tolerance }),
  );
}
