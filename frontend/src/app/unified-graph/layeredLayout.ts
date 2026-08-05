import { resolveGraphChineseLabel } from "../i18n/graphChineseResolver";
import {
  BUSINESS_WORLD,
  computeLayerGeometries,
  layerIndex,
} from "./businessLayerConfig";
import {
  ALL_CORE_ROLES,
  CORE_ROLE_LABELS,
  ROLE_LAYER,
  STRUCTURAL_RELATIONS,
  anchorToCenter,
  getCoreRoleDefinitions,
} from "./businessRoleConfig";
import {
  assignNodeRoles,
  extensionCountByRole,
  mappingCountByRole,
  projectOntologyEdges,
} from "./graphProjection";
import type {
  BusinessLayerId,
  BusinessRoleId,
  CollapsedProjectedEdge,
  GraphBuildInputEdge,
  GraphBuildInputNode,
  GraphProjectionResult,
  ProjectedGraphEdge,
  SharedEdgeBus,
  UnifiedGraphMode,
  VisualProjection,
} from "./graphTypes";

function collapseEdges(edges: ProjectedGraphEdge[]): CollapsedProjectedEdge[] {
  const groups = new Map<string, ProjectedGraphEdge[]>();
  for (const edge of edges) {
    const key = `${edge.sourceProjectionId}|${edge.targetProjectionId}`;
    const bucket = groups.get(key) ?? [];
    bucket.push(edge);
    groups.set(key, bucket);
  }
  return [...groups.keys()]
    .sort((a, b) => a.localeCompare(b))
    .map((key) => {
      const bucket = groups.get(key) ?? [];
      const [from, to] = key.split("|");
      const relationIds = bucket
        .map((item) => item.relationId)
        .sort((a, b) => a.localeCompare(b));
      return {
        id: `${from}->${to}:${relationIds.join("+")}`,
        from,
        to,
        edges: bucket,
      };
    });
}

function buildCoreRoleNodes(input: {
  mappingCounts: Map<BusinessRoleId, number>;
  extensionCounts: Map<BusinessRoleId, number>;
  activeRoleIds?: Set<BusinessRoleId>;
}): VisualProjection[] {
  return getCoreRoleDefinitions()
    .sort((a, b) => layerIndex(a.layerId) - layerIndex(b.layerId) || a.id.localeCompare(b.id))
    .map((role, order) => {
      const { cx, cy } = anchorToCenter(role.anchor);
      const size = role.size;
      return {
        projectionId: `role:${role.id}`,
        sourceNodeId: `role:${role.id}`,
        roleId: role.id,
        layerId: role.layerId,
        kind: "CORE_ROLE" as const,
        labelZh: role.labelZh,
        mappedCount: input.mappingCounts.get(role.id) ?? 0,
        extensionCount: input.extensionCounts.get(role.id) ?? 0,
        state: input.activeRoleIds?.has(role.id) ? "ACTIVE" : "DEFAULT",
        x: cx - size.width / 2,
        y: cy - size.height / 2,
        width: size.width,
        height: size.height,
        order,
      };
    });
}

function buildCompleteNodes(input: {
  nodes: GraphBuildInputNode[];
  assignments: ReturnType<typeof assignNodeRoles>["assignments"];
}): VisualProjection[] {
  const projections: VisualProjection[] = [];
  const byLayer = new Map<BusinessLayerId, Array<{
    node: GraphBuildInputNode;
    roleId: BusinessRoleId | null;
    projectionSuffix: string;
  }>>();

  for (const layerId of [
    "USER_IDENTITY",
    "ACCOUNT_BILLING",
    "SERVICE_OFFERING",
    "PORTABILITY_PROCESS",
    "QUALIFICATION_COMPLIANCE",
  ] as BusinessLayerId[]) {
    byLayer.set(layerId, []);
  }

  const seenProjection = new Set<string>();
  for (const node of [...input.nodes].sort((a, b) => a.id.localeCompare(b.id))) {
    const assignment = input.assignments.get(node.id);
    if (!assignment) continue;

    if (assignment.roles.length) {
      for (const roleId of assignment.roles) {
        const projectionId = `${node.id}::${roleId}`;
        if (seenProjection.has(projectionId)) continue;
        seenProjection.add(projectionId);
        byLayer.get(ROLE_LAYER[roleId])?.push({
          node,
          roleId,
          projectionSuffix: roleId,
        });
      }
      continue;
    }

    const projectionId = `${node.id}::ext`;
    if (seenProjection.has(projectionId)) continue;
    seenProjection.add(projectionId);
    byLayer.get(assignment.layerId)?.push({
      node,
      roleId: null,
      projectionSuffix: "ext",
    });
  }

  let order = 0;
  const layers = computeLayerGeometries();
  const contentX = layers[0]?.contentX ?? 240;
  const maxCols = 7;
  const gapX = 28;
  const gapY = 16;

  for (const layer of layers) {
    const items = [...(byLayer.get(layer.id) ?? [])].sort((a, b) => {
      const aRole = a.roleId ? ALL_CORE_ROLES.indexOf(a.roleId) : 999;
      const bRole = b.roleId ? ALL_CORE_ROLES.indexOf(b.roleId) : 999;
      return (
        aRole - bRole ||
        a.node.id.localeCompare(b.node.id) ||
        a.projectionSuffix.localeCompare(b.projectionSuffix)
      );
    });

    items.forEach((item, index) => {
      const col = index % maxCols;
      const row = Math.floor(index / maxCols);
      const width = 142;
      const height = 46;
      const x = contentX + 16 + col * (width + gapX);
      const y = layer.y + 28 + row * (height + gapY);
      projections.push({
        projectionId: `${item.node.id}::${item.projectionSuffix}`,
        sourceNodeId: item.node.id,
        roleId: item.roleId,
        layerId: layer.id,
        kind: item.roleId ? "PROJECTION" : "EXTENSION",
        labelZh: resolveGraphChineseLabel({
          apiLabelZh: item.node.label,
          localName: item.node.localName,
          kind: "class",
        }),
        localName: item.node.localName,
        state: item.node.state ?? "DEFAULT",
        x,
        y,
        width,
        height,
        order: order++,
      });
    });
  }

  return projections;
}

function buildStructuralEdges(
  roleNodes: VisualProjection[],
): ProjectedGraphEdge[] {
  const byRole = new Map(
    roleNodes
      .filter((node) => node.roleId)
      .map((node) => [node.roleId as BusinessRoleId, node]),
  );
  return STRUCTURAL_RELATIONS.map((relation) => {
    const from = byRole.get(relation.fromRole);
    const to = byRole.get(relation.toRole);
    if (!from || !to) {
      throw new Error(
        `Structural edge missing endpoint: ${relation.id} ${relation.fromRole}->${relation.toRole}`,
      );
    }
    return {
      id: relation.id,
      sourceProjectionId: from.projectionId,
      targetProjectionId: to.projectionId,
      relationId: relation.id,
      labelZh: relation.labelZh,
      sourceEdgeIds: [relation.id],
      presentationType: "STRUCTURAL" as const,
    };
  });
}

function buildServiceBus(nodes: VisualProjection[]): SharedEdgeBus | null {
  const source = nodes.find(
    (node) => node.roleId === "MOBILE_NUMBER_IDENTITY",
  );
  const targets = (
    [
      "TARIFF_PLAN",
      "CONTRACT",
      "BROADBAND",
      "VALUE_ADDED_SERVICE",
      "USER_RIGHT",
    ] as BusinessRoleId[]
  )
    .map((roleId) => nodes.find((node) => node.roleId === roleId))
    .filter((node): node is VisualProjection => Boolean(node));
  if (!source || targets.length < 3) return null;

  const sourceBottom = {
    x: source.x + source.width / 2,
    y: source.y + source.height,
  };
  const trunkY = Math.max(...targets.map((t) => t.y)) - 28;
  const leftX = Math.min(...targets.map((t) => t.x + t.width / 2));
  const rightX = Math.max(...targets.map((t) => t.x + t.width / 2));
  const trunkPath = `M ${sourceBottom.x} ${sourceBottom.y} V ${trunkY} H ${leftX}`;
  const branchPaths: Record<string, string> = {
    trunk: `M ${leftX} ${trunkY} H ${rightX}`,
  };
  const sourceEdgeIds: string[] = [];
  for (const target of targets) {
    const tx = target.x + target.width / 2;
    const ty = target.y;
    branchPaths[target.projectionId] = `M ${tx} ${trunkY} V ${ty}`;
    sourceEdgeIds.push(`struct-bus-${target.roleId}`);
  }
  return {
    id: "service-offering-bus",
    trunkPath: `${trunkPath} H ${rightX}`,
    branchPaths,
    sourceEdgeIds,
    labelZh: "业务关联",
    labelX: (leftX + rightX) / 2,
    labelY: trunkY - 8,
  };
}

export function buildUnifiedGraph(input: {
  mode: UnifiedGraphMode;
  nodes: GraphBuildInputNode[];
  edges: GraphBuildInputEdge[];
  activeNodeIds?: Set<string>;
  activeEdgeIds?: Set<string>;
}): GraphProjectionResult {
  const { assignments, unmapped } = assignNodeRoles(input.nodes, input.edges);
  const mappingCounts = mappingCountByRole(assignments);
  const extensionCounts = extensionCountByRole(assignments);

  let nodes: VisualProjection[];
  let edges: ProjectedGraphEdge[];
  let buses: SharedEdgeBus[] = [];
  let dangling: Array<{ id: string; from: string; to: string }> = [];

  if (input.mode === "BUSINESS_OVERVIEW") {
    const activeRoles = new Set<BusinessRoleId>();
    for (const node of input.nodes) {
      const assignment = assignments.get(node.id);
      if (!assignment) continue;
      if (input.activeNodeIds && !input.activeNodeIds.has(node.id)) continue;
      for (const role of assignment.roles) activeRoles.add(role);
    }
    nodes = buildCoreRoleNodes({
      mappingCounts,
      extensionCounts,
      activeRoleIds: input.activeNodeIds ? activeRoles : undefined,
    });
    edges = buildStructuralEdges(nodes).filter((edge) => {
      const def = STRUCTURAL_RELATIONS.find((item) => item.id === edge.id);
      return !def?.group;
    });
    const bus = buildServiceBus(nodes);
    if (bus) buses = [bus];
  } else if (
    input.mode === "ASSESSMENT_TRACE" ||
    input.mode === "HISTORY_TRACE"
  ) {
    const activeNodes = buildCompleteNodes({
      nodes: input.nodes,
      assignments,
    }).map((node) => ({
      ...node,
      state:
        !input.activeNodeIds || input.activeNodeIds.has(node.sourceNodeId)
          ? node.state && node.state !== "DEFAULT"
            ? node.state
            : ("ACTIVE" as const)
          : ("DIMMED" as const),
    }));
    nodes = activeNodes;
    const projected = projectOntologyEdges({
      edges: input.edges,
      projections: activeNodes,
      presentationType: "TRACE",
    });
    edges = projected.edges;
    dangling = projected.dangling;
  } else {
    nodes = buildCompleteNodes({ nodes: input.nodes, assignments });
    if (input.activeNodeIds) {
      nodes = nodes.map((node) => {
        if (node.sourceNodeId.startsWith("role:")) {
          return { ...node, state: "DIMMED" };
        }
        if (input.activeNodeIds?.has(node.sourceNodeId)) {
          return {
            ...node,
            state: node.state && node.state !== "DEFAULT" ? node.state : "ACTIVE",
          };
        }
        return { ...node, state: "DIMMED" };
      });
    }
    const projected = projectOntologyEdges({
      edges: input.edges,
      projections: nodes.filter((node) => !node.sourceNodeId.startsWith("role:")),
      presentationType:
        input.mode === "IMPORT_PREVIEW" ? "IMPORT" : "ONTOLOGY",
    });
    edges = projected.edges;
    dangling = projected.dangling;
  }

  const layers = computeLayerGeometries();
  const collapsedEdges = collapseEdges(edges);
  const contentRight =
    Math.max(...nodes.map((node) => node.x + node.width), 0) + 48;

  return {
    mode: input.mode,
    layers,
    nodes,
    edges,
    collapsedEdges,
    buses,
    worldWidth: BUSINESS_WORLD.width,
    worldHeight: BUSINESS_WORLD.height,
    contentRight: Math.min(BUSINESS_WORLD.width - 24, Math.max(contentRight, 1400)),
    unmappedNodeIds: unmapped,
    danglingEdges: dangling.map((item) => ({
      id: item.id,
      sourceProjectionId: item.from,
      targetProjectionId: item.to,
      relationId: "dangling",
      labelZh: "悬空边",
      sourceEdgeIds: [item.id],
      presentationType: "ONTOLOGY",
    })),
    silentlyDroppedNodes: [],
    silentlyDroppedEdges: [],
    extensionNodeCount: nodes.filter((node) => node.kind === "EXTENSION").length,
    coreRoleCount: ALL_CORE_ROLES.length,
  };
}
