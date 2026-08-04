import { describe, expect, it } from "vitest";
import {
  ONTOLOGY_LANE_ORDER,
  assignAllOntologyLanes,
  assignOntologyLane,
} from "../ontologyLaneConfig";
import { buildCurrentOntologyNodes } from "./fixtures";

describe("ontologyLaneConfig", () => {
  it("maps every current ontology node to exactly one lane", () => {
    const nodes = buildCurrentOntologyNodes();
    const { assignments, unmapped } = assignAllOntologyLanes(nodes);

    expect(unmapped).toEqual([]);
    expect(assignments.size).toBe(nodes.length);

    const seen = new Set<string>();
    for (const node of nodes) {
      const lane = assignOntologyLane(node);
      expect(lane, node.localName).not.toBeNull();
      expect(seen.has(node.id)).toBe(false);
      seen.add(node.id);
    }
  });

  it("keeps five lanes and no duplicate overview membership by lane assignment", () => {
    expect(ONTOLOGY_LANE_ORDER).toHaveLength(5);
    const nodes = buildCurrentOntologyNodes();
    const { assignments } = assignAllOntologyLanes(nodes);
    const byLane = new Map<string, string[]>();
    for (const [id, lane] of assignments) {
      const list = byLane.get(lane) ?? [];
      list.push(id);
      byLane.set(lane, list);
    }
    for (const lane of ONTOLOGY_LANE_ORDER) {
      expect(byLane.get(lane)?.length ?? 0).toBeGreaterThan(0);
    }
  });
});
