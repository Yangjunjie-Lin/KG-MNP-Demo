import { describe, expect, it } from "vitest";
import { mockOntologyEdges, mockOntologyNodes } from "../../../mocks/fixtures/mockOntology";
import { buildUnifiedGraph } from "../layeredLayout";
import { routeProjectedEdges } from "../orthogonalRouter";
import { isOrthogonalPath } from "../orthogonalRouter";
import {
  summarizeGeometryViolations,
  validateUnifiedGraphGeometry,
} from "../graphGeometry";
import { ALL_CORE_ROLES } from "../businessRoleConfig";
import { BUSINESS_LAYER_ORDER } from "../businessLayerConfig";

describe("unified graph projection", () => {
  it("maps every mock ontology node and routes orthogonal edges", () => {
    const graph = buildUnifiedGraph({
      mode: "COMPLETE_ONTOLOGY",
      nodes: mockOntologyNodes.map((node) => ({
        id: node.id,
        label: node.label,
        localName: node.localName,
        module: node.module,
      })),
      edges: mockOntologyEdges.map((edge, index) => ({
        id: `${edge.from}-${edge.to}-${index}`,
        from: edge.from,
        to: edge.to,
        relation: edge.relation,
        label: edge.label,
      })),
    });

    expect(graph.unmappedNodeIds).toEqual([]);
    expect(graph.danglingEdges).toEqual([]);
    expect(graph.silentlyDroppedNodes).toEqual([]);
    expect(graph.coreRoleCount).toBe(ALL_CORE_ROLES.length);
    expect(graph.layers.map((layer) => layer.id)).toEqual(BUSINESS_LAYER_ORDER);

    const routed = routeProjectedEdges({
      nodes: graph.nodes,
      collapsedEdges: graph.collapsedEdges,
      layers: graph.layers,
      contentRight: graph.contentRight,
    });
    expect(routed.length).toBe(graph.collapsedEdges.length);
    for (const edge of routed) {
      expect(isOrthogonalPath(edge.path)).toBe(true);
    }

    const violations = validateUnifiedGraphGeometry({
      nodes: graph.nodes,
      edges: routed,
      layers: graph.layers,
      buses: graph.buses,
      danglingEdgeCount: graph.danglingEdges.length,
    });
    expect(summarizeGeometryViolations(violations).danglingEdge).toBe(0);
  });

  it("builds business overview with fixed core roles", () => {
    const graph = buildUnifiedGraph({
      mode: "BUSINESS_OVERVIEW",
      nodes: mockOntologyNodes.map((node) => ({
        id: node.id,
        label: node.label,
        localName: node.localName,
        module: node.module,
      })),
      edges: [],
    });
    expect(graph.nodes.filter((node) => node.kind === "CORE_ROLE")).toHaveLength(
      ALL_CORE_ROLES.length,
    );
    expect(graph.buses.length).toBe(1);
  });
});
