import type { OntologyEdge, OntologyNode } from "../types/ontology";
import {
  ONTOLOGY_LANE_CONFIGS,
  ONTOLOGY_LANE_ORDER,
  OVERVIEW_RELATION_ALLOWLIST,
  assignAllOntologyLanes,
  getLaneConfig,
  isTechnicalSupportNode,
} from "./ontologyLaneConfig";
import type {
  CollapsedOntologyEdge,
  OntologyLaneId,
  OntologyOverviewGraph,
} from "./ontologyGraphTypes";

function nodeDisplaySortKey(node: OntologyNode): string {
  return node.label || node.localName;
}

export function collapseParallelEdges(edges: OntologyEdge[]): CollapsedOntologyEdge[] {
  const groups = new Map<string, OntologyEdge[]>();
  for (const edge of edges) {
    const key = `${edge.from}|${edge.to}`;
    const bucket = groups.get(key);
    if (bucket) {
      bucket.push(edge);
    } else {
      groups.set(key, [edge]);
    }
  }

  const collapsed: CollapsedOntologyEdge[] = [];
  const sortedKeys = [...groups.keys()].sort((a, b) => a.localeCompare(b));
  for (const key of sortedKeys) {
    const relations = groups.get(key) ?? [];
    const [from, to] = key.split("|");
    const relationNames = relations
      .map((item) => item.relation)
      .sort((a, b) => a.localeCompare(b));
    collapsed.push({
      id: `${from}->${to}:${relationNames.join("+")}`,
      from,
      to,
      relations,
    });
  }
  return collapsed;
}

export function buildLaneNodeLists(
  nodes: OntologyNode[],
  assignments: Map<string, OntologyLaneId>,
): Map<OntologyLaneId, OntologyNode[]> {
  const byLane = new Map<OntologyLaneId, OntologyNode[]>();
  for (const laneId of ONTOLOGY_LANE_ORDER) {
    byLane.set(laneId, []);
  }

  for (const node of nodes) {
    const laneId = assignments.get(node.id);
    if (!laneId) continue;
    byLane.get(laneId)?.push(node);
  }

  for (const laneId of ONTOLOGY_LANE_ORDER) {
    const config = getLaneConfig(laneId);
    const overviewIndex = new Map(
      config.overviewNodeOrder.map((name, index) => [name, index]),
    );
    const laneNodes = byLane.get(laneId) ?? [];
    laneNodes.sort((a, b) => {
      const aOverview = overviewIndex.has(a.localName);
      const bOverview = overviewIndex.has(b.localName);
      if (aOverview && bOverview) {
        return (
          (overviewIndex.get(a.localName) ?? 0) -
          (overviewIndex.get(b.localName) ?? 0)
        );
      }
      if (aOverview !== bOverview) return aOverview ? -1 : 1;

      const aTech = isTechnicalSupportNode(a);
      const bTech = isTechnicalSupportNode(b);
      if (aTech !== bTech) return aTech ? 1 : -1;

      return nodeDisplaySortKey(a).localeCompare(nodeDisplaySortKey(b), "zh");
    });
    byLane.set(laneId, laneNodes);
  }

  return byLane;
}

export function buildOntologyOverview(
  nodes: OntologyNode[],
  edges: OntologyEdge[],
): OntologyOverviewGraph {
  const { assignments, unmapped } = assignAllOntologyLanes(nodes);
  const allLaneNodes = buildLaneNodeLists(nodes, assignments);

  const overviewLocalNames = new Set(
    ONTOLOGY_LANE_CONFIGS.flatMap((config) => config.overviewNodeOrder),
  );

  const overviewNodes: OntologyNode[] = [];
  const overviewNodeIds = new Set<string>();

  for (const laneId of ONTOLOGY_LANE_ORDER) {
    const config = getLaneConfig(laneId);
    const byLocalName = new Map(
      (allLaneNodes.get(laneId) ?? []).map((node) => [node.localName, node]),
    );
    for (const localName of config.overviewNodeOrder) {
      const node = byLocalName.get(localName);
      if (!node) continue;
      if (overviewNodeIds.has(node.id)) continue;
      overviewNodes.push(node);
      overviewNodeIds.add(node.id);
    }
  }

  const whitelistEdges = edges.filter(
    (edge) =>
      overviewNodeIds.has(edge.from) &&
      overviewNodeIds.has(edge.to) &&
      OVERVIEW_RELATION_ALLOWLIST.has(edge.relation),
  );

  const secondaryRelationCount = edges.length - whitelistEdges.length;

  return {
    overviewNodes,
    overviewEdges: whitelistEdges,
    collapsedEdges: collapseParallelEdges(whitelistEdges),
    allLaneNodes,
    unmappedNodes: unmapped,
    secondaryRelationCount,
    whitelistRelationCount: whitelistEdges.length,
  };
}

export function getDetailNodesForLane(
  laneId: OntologyLaneId,
  allLaneNodes: Map<OntologyLaneId, OntologyNode[]>,
): OntologyNode[] {
  return [...(allLaneNodes.get(laneId) ?? [])];
}

export function getDetailEdgesForLane(
  laneId: OntologyLaneId,
  nodes: OntologyNode[],
  edges: OntologyEdge[],
): OntologyEdge[] {
  const ids = new Set(nodes.map((node) => node.id));
  return edges.filter((edge) => ids.has(edge.from) && ids.has(edge.to));
}
