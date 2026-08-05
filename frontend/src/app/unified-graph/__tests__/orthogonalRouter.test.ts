import { describe, expect, it } from "vitest";
import {
  mockOntologyEdges,
  mockOntologyNodes,
} from "../../../mocks/fixtures/mockOntology";
import type {
  BusinessLayerId,
  CollapsedProjectedEdge,
  LayerGeometry,
  VisualProjection,
} from "../graphTypes";
import {
  countRouteBends,
  routeDirect,
  routeDoubleElbow,
  routeProjectedEdges,
  routeSingleElbow,
  routeWithGutter,
} from "../orthogonalRouter";
import {
  segmentIntersectsRect,
  validateUnifiedGraphGeometry,
} from "../graphGeometry";
import { buildUnifiedGraph } from "../layeredLayout";

function node(
  projectionId: string,
  x: number,
  y: number,
  options: {
    width?: number;
    height?: number;
    layerId?: BusinessLayerId;
  } = {},
): VisualProjection {
  return {
    projectionId,
    sourceNodeId: projectionId,
    roleId: null,
    layerId: options.layerId ?? "USER_IDENTITY",
    kind: "EXTENSION",
    labelZh: projectionId,
    x,
    y,
    width: options.width ?? 80,
    height: options.height ?? 40,
    order: 0,
  };
}

function edge(from: string, to: string): CollapsedProjectedEdge {
  return {
    id: `${from}->${to}`,
    from,
    to,
    edges: [
      {
        id: `${from}->${to}`,
        sourceProjectionId: from,
        targetProjectionId: to,
        relationId: "related-to",
        labelZh: "关联",
        sourceEdgeIds: [`${from}->${to}`],
        presentationType: "ONTOLOGY",
      },
    ],
  };
}

const layers: LayerGeometry[] = [
  {
    id: "USER_IDENTITY",
    label: "User & Identity",
    x: 0,
    y: 0,
    width: 600,
    height: 300,
    contentX: 100,
    contentY: 0,
    contentWidth: 500,
    contentHeight: 300,
    routeBottomY: 318,
  },
];

describe("minimal-bend orthogonal router", () => {
  it("uses a direct path without endpoint stubs when ports align", () => {
    const source = node("source", 0, 20);
    const target = node("target", 200, 20);
    const [routed] = routeProjectedEdges({
      nodes: [source, target],
      collapsedEdges: [edge(source.projectionId, target.projectionId)],
      layers,
      contentRight: 300,
    });

    expect(routed.points).toEqual([
      { x: 80, y: 40 },
      { x: 200, y: 40 },
    ]);
    expect(routed.path).toBe("M 80 40 H 200");
    expect(countRouteBends(routed.points)).toBe(0);
  });

  it("prefers one elbow for an unobstructed diagonal relationship", () => {
    const source = node("source", 0, 0);
    const target = node("target", 200, 100);
    const [routed] = routeProjectedEdges({
      nodes: [source, target],
      collapsedEdges: [edge(source.projectionId, target.projectionId)],
      layers,
      contentRight: 300,
    });

    expect(countRouteBends(routed.points)).toBe(1);
    expect(routed.points).toHaveLength(3);
  });

  it("uses a two-elbow detour when a node blocks the direct path", () => {
    const source = node("source", 0, 0);
    const blocker = node("blocker", 140, -10, { width: 40, height: 60 });
    const target = node("target", 300, 0);
    const [routed] = routeProjectedEdges({
      nodes: [source, blocker, target],
      collapsedEdges: [edge(source.projectionId, target.projectionId)],
      layers,
      contentRight: 400,
    });

    expect(countRouteBends(routed.points)).toBe(2);
    for (let index = 0; index < routed.points.length - 1; index += 1) {
      expect(
        segmentIntersectsRect(
          { a: routed.points[index], b: routed.points[index + 1] },
          blocker,
        ),
      ).toBe(false);
    }
  });

  it("exposes direct, single-elbow, and double-elbow obstacle-aware helpers", () => {
    const source = { x: 0, y: 0 };
    const target = { x: 100, y: 20 };

    expect(routeDirect(source, { x: 100, y: 0 })).toEqual([
      source,
      { x: 100, y: 0 },
    ]);
    expect(
      routeSingleElbow(source, target, {
        sourceSide: "right",
        targetSide: "top",
      }),
    ).toEqual([source, { x: 100, y: 0 }, target]);
    const double = routeDoubleElbow(source, target, {
      sourceSide: "right",
      targetSide: "left",
    });
    expect(double).not.toBeNull();
    expect(countRouteBends(double ?? [])).toBe(2);
  });

  it("uses a gutter only when lower-bend routes are blocked and caps it at four bends", () => {
    const source = { x: 0, y: 0 };
    const target = { x: 100, y: 0 };
    const wall = { x: 40, y: -100, width: 20, height: 200 };
    const options = {
      obstacles: [wall],
      sourceSide: "right" as const,
      targetSide: "left" as const,
      gutter: { left: -20, right: 120, top: -120, bottom: 120 },
    };

    expect(routeDirect(source, target, options)).toBeNull();
    expect(routeSingleElbow(source, target, options)).toBeNull();
    expect(routeDoubleElbow(source, target, options)).toBeNull();

    const gutterRoute = routeWithGutter(source, target, options);
    expect(gutterRoute).not.toBeNull();
    expect(countRouteBends(gutterRoute ?? [])).toBe(4);
  });

  it("throws a clear geometry error when no route of at most four bends exists", () => {
    const source = node("source", 0, 0);
    const enclosingObstacle = node("enclosing", -100, -100, {
      width: 300,
      height: 300,
    });
    const target = node("target", 400, 0);

    expect(() =>
      routeProjectedEdges({
        nodes: [source, enclosingObstacle, target],
        collapsedEdges: [edge(source.projectionId, target.projectionId)],
        layers,
        contentRight: 500,
      }),
    ).toThrow(
      "Geometry error routing edge source->target: no obstacle-free route with 4 or fewer bends",
    );
  });

  it("routes a same-projection relationship as a local three-bend self-loop", () => {
    const self = node("self", 120, 80);
    const [routed] = routeProjectedEdges({
      nodes: [self],
      collapsedEdges: [edge(self.projectionId, self.projectionId)],
      layers,
      contentRight: 300,
    });

    expect(routed.from).toBe("self");
    expect(routed.to).toBe("self");
    expect(countRouteBends(routed.points)).toBe(3);
    expect(routed.path).toMatch(/^M .* [HV] /);
  });

  it("keeps complete-ontology mock routes within the bend cap and outside nodes", () => {
    const graph = buildUnifiedGraph({
      mode: "COMPLETE_ONTOLOGY",
      nodes: mockOntologyNodes.map((item) => ({
        id: item.id,
        label: item.label,
        localName: item.localName,
        module: item.module,
      })),
      edges: mockOntologyEdges.map((item, index) => ({
        id: `${item.from}-${item.to}-${index}`,
        from: item.from,
        to: item.to,
        relation: item.relation,
        label: item.label,
      })),
    });
    const routed = routeProjectedEdges({
      nodes: graph.nodes,
      collapsedEdges: graph.collapsedEdges,
      layers: graph.layers,
      contentRight: graph.contentRight,
    });

    expect(routed.every((item) => countRouteBends(item.points) <= 4)).toBe(true);
    const violations = validateUnifiedGraphGeometry({
      nodes: graph.nodes,
      edges: routed,
      layers: graph.layers,
      buses: graph.buses,
    });
    expect(
      violations.filter((violation) => violation.kind === "EDGE_THROUGH_NODE"),
    ).toEqual([]);
  });
});
