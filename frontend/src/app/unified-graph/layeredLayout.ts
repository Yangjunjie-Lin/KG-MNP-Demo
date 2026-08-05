import { resolveGraphChineseLabel } from "../i18n/graphChineseResolver";
import {
  BUSINESS_WORLD,
  computeLayerGeometries,
  layerIndex,
} from "./businessLayerConfig";
import {
  CANONICAL_BUSES,
  CANONICAL_CANVAS,
  CANONICAL_EDGES,
  CANONICAL_LAYERS,
} from "./canonicalDiagramConfig";
import {
  ALL_CORE_ROLES,
  ROLE_LAYER,
  STRUCTURAL_RELATIONS,
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
  NodeState,
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
  roleStates?: Map<BusinessRoleId, NodeState>;
  dimInactive?: boolean;
}): VisualProjection[] {
  return getCoreRoleDefinitions()
    .sort((a, b) => layerIndex(a.layerId) - layerIndex(b.layerId) || a.id.localeCompare(b.id))
    .map((role, order) => {
      const state = input.roleStates?.get(role.id);
      return {
        projectionId: `role:${role.id}`,
        sourceNodeId: `role:${role.id}`,
        roleId: role.id,
        layerId: role.layerId,
        kind: "CORE_ROLE" as const,
        labelZh: role.labelZh,
        mappedCount: input.mappingCounts.get(role.id) ?? 0,
        extensionCount: input.extensionCounts.get(role.id) ?? 0,
        state:
          state ??
          (input.activeRoleIds?.has(role.id)
            ? "ACTIVE"
            : input.dimInactive
              ? "DIMMED"
              : "DEFAULT"),
        x: role.x,
        y: role.y,
        width: role.size.width,
        height: role.size.height,
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

function buildStructuralEdges(input: {
  roleNodes: VisualProjection[];
  dimInactive?: boolean;
}): ProjectedGraphEdge[] {
  const byRole = new Map(
    input.roleNodes
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
      state:
        input.dimInactive &&
        (from.state === "DIMMED" || to.state === "DIMMED")
          ? ("DIMMED" as const)
          : to.state && to.state !== "DEFAULT"
            ? to.state
            : from.state,
    };
  });
}

function buildCanonicalBuses(): SharedEdgeBus[] {
  return CANONICAL_BUSES.map((bus) => ({
    id: bus.id,
    trunkPath: bus.path,
    branchPaths: Object.fromEntries(
      CANONICAL_EDGES.filter((edge) => edge.busId === bus.id).map((edge) => [
        edge.id,
        edge.path,
      ]),
    ),
    sourceEdgeIds: [...bus.edgeIds],
    labelZh: "",
    labelX: 0,
    labelY: 0,
  }));
}

function canonicalLayerGeometries() {
  return CANONICAL_LAYERS.map((layer) => ({
    id: layer.id,
    label: layer.titleZh,
    x: layer.x,
    y: layer.y,
    width: layer.width,
    height: layer.height,
    contentX: layer.contentX,
    contentY: layer.y,
    contentWidth: layer.x + layer.width - layer.contentX,
    contentHeight: layer.height,
    routeBottomY: layer.y + layer.height,
  }));
}

function canonicalRoleActivity(input: {
  nodes: GraphBuildInputNode[];
  assignments: ReturnType<typeof assignNodeRoles>["assignments"];
  activeNodeIds?: Set<string>;
}): {
  activeRoleIds: Set<BusinessRoleId>;
  roleStates: Map<BusinessRoleId, NodeState>;
} {
  const activeRoleIds = new Set<BusinessRoleId>();
  const roleStates = new Map<BusinessRoleId, NodeState>();
  const priority: NodeState[] = [
    "BLOCK",
    "WARN",
    "PASS",
    "CURRENT",
    "ACTIVE",
    "DEFAULT",
  ];
  for (const node of input.nodes) {
    if (input.activeNodeIds && !input.activeNodeIds.has(node.id)) continue;
    const assignment = input.assignments.get(node.id);
    if (!assignment) continue;
    for (const roleId of assignment.roles) {
      activeRoleIds.add(roleId);
      const next = node.state ?? "ACTIVE";
      const current = roleStates.get(roleId);
      if (!current || priority.indexOf(next) < priority.indexOf(current)) {
        roleStates.set(roleId, next);
      }
    }
  }
  return { activeRoleIds, roleStates };
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

  const canonicalMode = input.mode !== "COMPLETE_ONTOLOGY";
  if (canonicalMode) {
    const activity = canonicalRoleActivity({
      nodes: input.nodes,
      assignments,
      activeNodeIds: input.activeNodeIds,
    });
    const dimInactive = input.mode !== "BUSINESS_OVERVIEW";
    nodes = buildCoreRoleNodes({
      mappingCounts,
      extensionCounts,
      activeRoleIds: dimInactive ? activity.activeRoleIds : undefined,
      roleStates: dimInactive ? activity.roleStates : undefined,
      dimInactive,
    });
    edges = buildStructuralEdges({ roleNodes: nodes, dimInactive });
    buses = buildCanonicalBuses();
  } else {
    nodes = buildCompleteNodes({ nodes: input.nodes, assignments });
    if (input.activeNodeIds) {
      nodes = nodes.map((node) => {
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
      projections: nodes,
      presentationType: "ONTOLOGY",
    });
    edges = projected.edges;
    dangling = projected.dangling;
  }

  const layers = canonicalMode
    ? canonicalLayerGeometries()
    : computeLayerGeometries();
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
    worldWidth: canonicalMode ? CANONICAL_CANVAS.width : BUSINESS_WORLD.width,
    worldHeight: canonicalMode ? CANONICAL_CANVAS.height : BUSINESS_WORLD.height,
    contentRight: canonicalMode
      ? CANONICAL_CANVAS.width - 24
      : Math.min(BUSINESS_WORLD.width - 24, Math.max(contentRight, 1400)),
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
    extensionNodeCount: canonicalMode
      ? 0
      : nodes.filter((node) => node.kind === "EXTENSION").length,
    coreRoleCount: ALL_CORE_ROLES.length,
  };
}
