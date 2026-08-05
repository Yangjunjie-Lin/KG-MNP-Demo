import { describe, expect, it } from "vitest";
import {
  ONTOLOGY_LANE_ORDER,
  assignAllOntologyLanes,
  assignOntologyLane,
} from "../ontologyLaneConfig";
import { buildCurrentOntologyNodes } from "./fixtures";
import type { OntologyEdge, OntologyNode } from "../../types/ontology";

function node(
  localName: string,
  module: string,
  id = `urn:test:${localName}`,
): OntologyNode {
  return {
    id,
    localName,
    label: localName,
    module,
    type: "Class",
    definition: "",
  };
}

function edge(from: string, to: string, relation = "relatesTo"): OntologyEdge {
  return { from, to, relation, label: relation };
}

describe("ontologyLaneConfig", () => {
  it("maps every current ontology node to exactly one lane", () => {
    const nodes = buildCurrentOntologyNodes();
    const { assignments, unmapped } = assignAllOntologyLanes(nodes, []);

    expect(unmapped).toEqual([]);
    expect(assignments.size).toBe(nodes.length);

    const seen = new Set<string>();
    for (const nodeItem of nodes) {
      if (nodeItem.localName === "MappingRecord" || nodeItem.localName === "CodeListEntry") {
        continue;
      }
      const lane = assignOntologyLane(nodeItem);
      expect(lane, nodeItem.localName).not.toBeNull();
      expect(seen.has(nodeItem.id)).toBe(false);
      seen.add(nodeItem.id);
    }
  });

  it("keeps five lanes and no duplicate overview membership by lane assignment", () => {
    expect(ONTOLOGY_LANE_ORDER).toHaveLength(5);
    const nodes = buildCurrentOntologyNodes();
    const { assignments } = assignAllOntologyLanes(nodes, []);
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

  it("assigns technical nodes connected only to account layer into account layer", () => {
    const account = node("BillingAccount", "ACCOUNT_BILLING");
    const technical = node("CodeListEntry", "CODE_LIST");
    const { assignments, assignmentMeta } = assignAllOntologyLanes(
      [account, technical],
      [edge(technical.id, account.id)],
    );
    expect(assignments.get(technical.id)).toBe("ACCOUNT_BILLING");
    expect(assignmentMeta.get(technical.id)?.reason).toBe("TECHNICAL_ADJACENCY");
  });

  it("prefers majority neighbor lane for technical nodes", () => {
    const a1 = node("TelecomAccount", "ACCOUNT_BILLING");
    const a2 = node("Bill", "ACCOUNT_BILLING");
    const c1 = node("EligibilityRule", "COMPLIANCE");
    const technical = node("MappingRecord", "CORE");
    const { assignments } = assignAllOntologyLanes(
      [a1, a2, c1, technical],
      [
        edge(technical.id, a1.id),
        edge(technical.id, a2.id),
        edge(technical.id, c1.id),
      ],
    );
    expect(assignments.get(technical.id)).toBe("ACCOUNT_BILLING");
  });

  it("breaks neighbor ties using fixed lane order", () => {
    const identity = node("Subscriber", "IDENTITY");
    const account = node("BillingAccount", "ACCOUNT_BILLING");
    const technical = node("CodeListEntry", "CODE_LIST");
    const { assignments } = assignAllOntologyLanes(
      [identity, account, technical],
      [edge(technical.id, identity.id), edge(technical.id, account.id)],
    );
    expect(assignments.get(technical.id)).toBe("USER_IDENTITY");
  });

  it("falls back to qualification when technical node has no mapped neighbors", () => {
    const technical = node("CodeListEntry", "CODE_LIST");
    const { assignments, assignmentMeta, technicalFallbackCount } =
      assignAllOntologyLanes([technical], []);
    expect(assignments.get(technical.id)).toBe("QUALIFICATION_COMPLIANCE");
    expect(assignmentMeta.get(technical.id)?.reason).toBe("TECHNICAL_FALLBACK");
    expect(technicalFallbackCount).toBe(1);
  });

  it("is stable under shuffled node and edge order", () => {
    const nodes = [
      node("Subscriber", "IDENTITY"),
      node("BillingAccount", "ACCOUNT_BILLING"),
      node("CodeListEntry", "CODE_LIST"),
      node("MappingRecord", "CORE"),
    ];
    const edges = [
      edge(nodes[2].id, nodes[1].id),
      edge(nodes[3].id, nodes[0].id),
    ];
    const a = assignAllOntologyLanes(nodes, edges);
    const b = assignAllOntologyLanes([...nodes].reverse(), [...edges].reverse());
    expect([...a.assignments.entries()].sort()).toEqual(
      [...b.assignments.entries()].sort(),
    );
    expect([...a.assignmentMeta.entries()].sort()).toEqual(
      [...b.assignmentMeta.entries()].sort(),
    );
  });
});
