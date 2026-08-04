import { describe, expect, it } from "vitest";
import { validateGraphGeometry } from "../ontologyGeometry";
import { layoutOntologyGraph } from "../ontologyLayout";
import { buildOntologyOverview } from "../ontologyOverviewBuilder";
import { routeOntologyEdges } from "../orthogonalRouter";
import {
  buildCurrentOntologyNodes,
  buildSampleOverviewEdges,
} from "./fixtures";

describe("ontologyGeometry", () => {
  it("reports zero geometry violations for overview layout", () => {
    const nodes = buildCurrentOntologyNodes();
    const edges = buildSampleOverviewEdges(nodes);
    const overview = buildOntologyOverview(nodes, edges);
    const layout = layoutOntologyGraph(nodes, { overview: true });
    const routed = routeOntologyEdges({
      nodes: layout.nodes,
      collapsedEdges: overview.collapsedEdges,
      lanes: layout.lanes,
      contentRight: layout.contentRight,
    });

    const violations = validateGraphGeometry({
      nodes: layout.nodes,
      edges: routed,
      lanes: layout.lanes,
      contentRight: layout.contentRight,
    });

    const throughNode = violations.filter((item) => item.kind === "edge-through-node");
    const overlaps = violations.filter((item) => item.kind === "segment-overlap");
    const labels = violations.filter((item) => item.kind === "label-inside-node");
    const outside = violations.filter((item) => item.kind === "node-outside-lane");
    const channels = violations.filter((item) => item.kind === "duplicate-cross-channel");

    expect(throughNode).toEqual([]);
    expect(overlaps).toEqual([]);
    expect(labels).toEqual([]);
    expect(outside).toEqual([]);
    expect(channels).toEqual([]);
    expect(violations).toEqual([]);
  });
});
