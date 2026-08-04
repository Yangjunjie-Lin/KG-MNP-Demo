import { describe, expect, it } from "vitest";
import { layoutOntologyGraph } from "../ontologyLayout";
import { buildOntologyOverview } from "../ontologyOverviewBuilder";
import {
  isOrthogonalPath,
  pointsAreOrthogonal,
  routeOntologyEdges,
} from "../orthogonalRouter";
import {
  buildCurrentOntologyNodes,
  buildSampleOverviewEdges,
} from "./fixtures";

describe("orthogonalRouter", () => {
  it("emits only M/H/V orthogonal paths", () => {
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

    expect(routed.length).toBeGreaterThan(0);
    for (const edge of routed) {
      expect(isOrthogonalPath(edge.path)).toBe(true);
      expect(edge.path.replace(/\s+/g, "")).not.toMatch(/[CQSTALcqlast]/i);
      expect(pointsAreOrthogonal(edge.points)).toBe(true);
      for (let i = 0; i < edge.points.length - 1; i += 1) {
        const a = edge.points[i];
        const b = edge.points[i + 1];
        expect(a.x === b.x || a.y === b.y).toBe(true);
      }
    }

    const crossChannels = routed
      .filter((edge) => edge.kind === "CROSS_LANE")
      .map((edge) => edge.channel);
    expect(new Set(crossChannels).size).toBe(crossChannels.length);
  });
});
