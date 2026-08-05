import { describe, expect, it } from "vitest";
import {
  LAYOUT,
  assignIntervalChannels,
  layoutOntologyGraph,
} from "../ontologyLayout";
import { buildOntologyOverview } from "../ontologyOverviewBuilder";
import { routeOntologyEdges } from "../orthogonalRouter";
import {
  buildCurrentOntologyNodes,
  buildSampleOverviewEdges,
} from "./fixtures";
import type { CollapsedOntologyEdge } from "../ontologyGraphTypes";
import type { PositionedOntologyNode } from "../../types/ontology";

describe("ontologyLayout", () => {
  it("is deterministic and order-independent", () => {
    const nodes = buildCurrentOntologyNodes();
    const edges = buildSampleOverviewEdges(nodes);
    const overview = buildOntologyOverview(nodes, edges);

    const layoutA = layoutOntologyGraph(nodes, overview.collapsedEdges, {
      overview: true,
      allEdges: edges,
    });
    const layoutB = layoutOntologyGraph(nodes, overview.collapsedEdges, {
      overview: true,
      allEdges: edges,
    });
    expect(layoutA).toEqual(layoutB);

    const shuffled = [...nodes].sort((a, b) => b.localName.localeCompare(a.localName));
    const layoutShuffled = layoutOntologyGraph(
      shuffled,
      overview.collapsedEdges,
      { overview: true, allEdges: edges },
    );
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
    expect(LAYOUT.nodeGapX).toBeLessThanOrEqual(100);
    expect(layoutA.width).toBeGreaterThanOrEqual(1600);
    expect(layoutA.width).toBeLessThanOrEqual(2200);
  });

  it("builds overview and routes under 50ms", () => {
    const nodes = buildCurrentOntologyNodes();
    const edges = buildSampleOverviewEdges(nodes);
    const started = performance.now();
    const overview = buildOntologyOverview(nodes, edges);
    const layout = layoutOntologyGraph(nodes, overview.collapsedEdges, {
      overview: true,
      allEdges: edges,
    });
    routeOntologyEdges({
      nodes: layout.nodes,
      collapsedEdges: overview.collapsedEdges,
      lanes: layout.lanes,
      contentRight: layout.contentRight,
    });
    const elapsed = performance.now() - started;
    expect(elapsed).toBeLessThan(50);
  });

  it("assigns intersecting intervals to different channels", () => {
    const nodes: PositionedOntologyNode[] = [
      fakeNode("a", 0),
      fakeNode("b", 1),
      fakeNode("c", 2),
      fakeNode("d", 3),
    ];
    const nodeMap = new Map(nodes.map((node) => [node.id, node]));
    const edges: CollapsedOntologyEdge[] = [
      collapsed("a", "c"),
      collapsed("b", "d"),
    ];
    const channels = assignIntervalChannels(edges, nodeMap);
    expect(channels.get(edges[0].id)).not.toBe(channels.get(edges[1].id));
  });

  it("reuses channels for non-overlapping intervals", () => {
    const nodes: PositionedOntologyNode[] = [
      fakeNode("a", 0),
      fakeNode("b", 1),
      fakeNode("c", 2),
      fakeNode("d", 3),
    ];
    const nodeMap = new Map(nodes.map((node) => [node.id, node]));
    const edges: CollapsedOntologyEdge[] = [
      collapsed("a", "b"),
      collapsed("c", "d"),
    ];
    const channels = assignIntervalChannels(edges, nodeMap);
    expect(channels.get(edges[0].id)).toBe(channels.get(edges[1].id));
  });

  it("keeps channel assignment stable under shuffled input order", () => {
    const nodes: PositionedOntologyNode[] = [
      fakeNode("a", 0),
      fakeNode("b", 1),
      fakeNode("c", 2),
      fakeNode("d", 3),
      fakeNode("e", 4),
    ];
    const nodeMap = new Map(nodes.map((node) => [node.id, node]));
    const edges: CollapsedOntologyEdge[] = [
      collapsed("a", "c"),
      collapsed("b", "d"),
      collapsed("c", "e"),
    ];
    const first = assignIntervalChannels(edges, nodeMap);
    const second = assignIntervalChannels([...edges].reverse(), nodeMap);
    expect([...first.entries()].sort()).toEqual([...second.entries()].sort());
  });
});

function fakeNode(id: string, order: number): PositionedOntologyNode {
  return {
    id,
    localName: id,
    label: id,
    module: "ACCOUNT_BILLING",
    type: "Class",
    definition: "",
    laneId: "ACCOUNT_BILLING",
    x: order * 220,
    y: 0,
    width: 148,
    height: 44,
    order,
    overview: true,
    technicalSupport: false,
  };
}

function collapsed(from: string, to: string): CollapsedOntologyEdge {
  return {
    id: `${from}->${to}:rel`,
    from,
    to,
    relations: [{ from, to, relation: "rel", label: "rel" }],
  };
}
