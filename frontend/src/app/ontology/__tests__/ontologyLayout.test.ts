import { describe, expect, it } from "vitest";
import { layoutOntologyGraph } from "../ontologyLayout";
import { buildOntologyOverview } from "../ontologyOverviewBuilder";
import { routeOntologyEdges } from "../orthogonalRouter";
import {
  buildCurrentOntologyNodes,
  buildSampleOverviewEdges,
} from "./fixtures";

describe("ontologyLayout", () => {
  it("is deterministic and order-independent", () => {
    const nodes = buildCurrentOntologyNodes();
    const edges = buildSampleOverviewEdges(nodes);
    const overview = buildOntologyOverview(nodes, edges);

    const layoutA = layoutOntologyGraph(nodes, { overview: true });
    const layoutB = layoutOntologyGraph(nodes, { overview: true });
    expect(layoutA).toEqual(layoutB);

    const shuffled = [...nodes].sort((a, b) => b.localName.localeCompare(a.localName));
    const layoutShuffled = layoutOntologyGraph(shuffled, { overview: true });
    expect(layoutShuffled.nodes.map((node) => ({
      id: node.id,
      x: node.x,
      y: node.y,
      laneId: node.laneId,
      order: node.order,
    }))).toEqual(
      layoutA.nodes.map((node) => ({
        id: node.id,
        x: node.x,
        y: node.y,
        laneId: node.laneId,
        order: node.order,
      })),
    );

    expect(layoutA.lanes.map((lane) => lane.id)).toEqual([
      "USER_IDENTITY",
      "ACCOUNT_BILLING",
      "SERVICE_OFFERING",
      "PORTABILITY_PROCESS",
      "QUALIFICATION_COMPLIANCE",
    ]);
    expect(overview.unmappedNodes).toEqual([]);
  });

  it("builds overview and routes under 50ms", () => {
    const nodes = buildCurrentOntologyNodes();
    const edges = buildSampleOverviewEdges(nodes);
    const started = performance.now();
    const overview = buildOntologyOverview(nodes, edges);
    const layout = layoutOntologyGraph(nodes, { overview: true });
    routeOntologyEdges({
      nodes: layout.nodes,
      collapsedEdges: overview.collapsedEdges,
      lanes: layout.lanes,
      contentRight: layout.contentRight,
    });
    const elapsed = performance.now() - started;
    expect(elapsed).toBeLessThan(50);
  });
});
