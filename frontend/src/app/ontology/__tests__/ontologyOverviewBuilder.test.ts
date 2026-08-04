import { describe, expect, it } from "vitest";
import {
  OVERVIEW_RELATION_ALLOWLIST,
  getLaneConfig,
} from "../ontologyLaneConfig";
import {
  buildOntologyOverview,
  collapseParallelEdges,
} from "../ontologyOverviewBuilder";
import {
  buildCurrentOntologyNodes,
  buildSampleOverviewEdges,
} from "./fixtures";

describe("ontologyOverviewBuilder", () => {
  it("only includes overviewNodeOrder nodes and whitelist edges", () => {
    const nodes = buildCurrentOntologyNodes();
    const edges = buildSampleOverviewEdges(nodes);
    const overview = buildOntologyOverview(nodes, edges);

    const allowedNames = new Set(
      [
        "USER_IDENTITY",
        "ACCOUNT_BILLING",
        "SERVICE_OFFERING",
        "PORTABILITY_PROCESS",
        "QUALIFICATION_COMPLIANCE",
      ].flatMap((laneId) =>
        getLaneConfig(
          laneId as
            | "USER_IDENTITY"
            | "ACCOUNT_BILLING"
            | "SERVICE_OFFERING"
            | "PORTABILITY_PROCESS"
            | "QUALIFICATION_COMPLIANCE",
        ).overviewNodeOrder,
      ),
    );

    for (const node of overview.overviewNodes) {
      expect(allowedNames.has(node.localName)).toBe(true);
    }

    const overviewIds = new Set(overview.overviewNodes.map((node) => node.id));
    expect(new Set(overview.overviewNodes.map((node) => node.id)).size).toBe(
      overview.overviewNodes.length,
    );

    for (const edge of overview.overviewEdges) {
      expect(overviewIds.has(edge.from)).toBe(true);
      expect(overviewIds.has(edge.to)).toBe(true);
      expect(OVERVIEW_RELATION_ALLOWLIST.has(edge.relation)).toBe(true);
    }

    expect(overview.secondaryRelationCount).toBe(
      edges.length - overview.whitelistRelationCount,
    );
    expect(overview.overviewNodes.some((node) => node.localName === "SafetyCheck")).toBe(
      false,
    );
  });

  it("collapses parallel edges but keeps reverse edges separate", () => {
    const nodes = buildCurrentOntologyNodes();
    const a = nodes.find((node) => node.localName === "Subscriber")!;
    const b = nodes.find((node) => node.localName === "PhoneNumber")!;
    const edges = [
      { from: a.id, to: b.id, relation: "ownsPhoneNumber", label: "持有号码" },
      { from: a.id, to: b.id, relation: "hasPhoneNumber", label: "关联号码" },
      { from: b.id, to: a.id, relation: "ownedBy", label: "归属订户" },
    ];
    const collapsed = collapseParallelEdges(edges);
    expect(collapsed).toHaveLength(2);
    const forward = collapsed.find((edge) => edge.from === a.id && edge.to === b.id)!;
    expect(forward.relations).toHaveLength(2);
    const reverse = collapsed.find((edge) => edge.from === b.id && edge.to === a.id)!;
    expect(reverse.relations).toHaveLength(1);
  });
});
