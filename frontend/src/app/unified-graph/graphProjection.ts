import mappingConfig from "./business_role_mapping_v1.json";
import {
  BUSINESS_LAYER_ORDER,
  layerIndex,
} from "./businessLayerConfig";
import {
  ALL_CORE_ROLES,
  CORE_ROLE_LABELS,
  ROLE_LAYER,
} from "./businessRoleConfig";
import { resolveGraphChineseLabel } from "../i18n/graphChineseResolver";
import type {
  BusinessLayerId,
  BusinessRoleId,
  GraphBuildInputEdge,
  GraphBuildInputNode,
  ProjectedGraphEdge,
  VisualProjection,
} from "./graphTypes";

type MappingValue = string | string[];

interface MappingFile {
  version: string;
  mapping: Record<string, MappingValue>;
  laneFallback?: Record<string, BusinessLayerId>;
}

const CONFIG = mappingConfig as MappingFile;

const ROLE_SET = new Set<string>(ALL_CORE_ROLES);

function asRoles(value: MappingValue | undefined): BusinessRoleId[] {
  if (!value) return [];
  const list = Array.isArray(value) ? value : [value];
  return list.filter((item): item is BusinessRoleId => ROLE_SET.has(item));
}

export function rolesForLocalName(localName: string): BusinessRoleId[] {
  return asRoles(CONFIG.mapping[localName]);
}

export function layerForModule(module?: string): BusinessLayerId | null {
  if (!module) return null;
  const key = module.trim().toUpperCase().replace(/[^A-Z0-9_]/g, "");
  const fallback = CONFIG.laneFallback ?? {};
  if (fallback[key]) return fallback[key];
  // Tolerate camelCase module names from mock/API (Identity → IDENTITY).
  const compact = key.replace(/_/g, "");
  for (const [raw, lane] of Object.entries(fallback)) {
    if (raw.replace(/_/g, "") === compact) return lane;
  }
  return null;
}

export function inferLayerFromLabel(label: string): BusinessLayerId | null {
  const text = label.trim();
  if (!text) return null;
  if (/用户|身份|实名|号码|订户|证件/.test(text)) return "USER_IDENTITY";
  if (/账户|账单|缴费|欠费|计费/.test(text)) return "ACCOUNT_BILLING";
  if (/套餐|合同|宽带|增值|权益|业务|合约/.test(text)) return "SERVICE_OFFERING";
  if (/携转|授权码|流程|异常|影响|申请/.test(text)) return "PORTABILITY_PROCESS";
  if (/资格|规则|证据|阻塞|检查|合规|监管/.test(text)) {
    return "QUALIFICATION_COMPLIANCE";
  }
  return null;
}

export interface NodeRoleAssignment {
  nodeId: string;
  roles: BusinessRoleId[];
  layerId: BusinessLayerId;
  reason:
    | "EXACT_ROLE"
    | "CANONICAL_ROLE"
    | "MODULE"
    | "ADJACENCY"
    | "LABEL"
    | "EXTENSION_FALLBACK";
}

function pickLayerByScores(
  scores: Map<BusinessLayerId, number>,
): BusinessLayerId | null {
  let best: BusinessLayerId | null = null;
  let bestScore = -1;
  for (const layerId of BUSINESS_LAYER_ORDER) {
    const score = scores.get(layerId) ?? 0;
    if (score > bestScore) {
      bestScore = score;
      best = layerId;
    }
  }
  return bestScore > 0 ? best : null;
}

/**
 * Map every runtime node to roles + layer. Never silently drops nodes.
 */
export function assignNodeRoles(
  nodes: GraphBuildInputNode[],
  edges: GraphBuildInputEdge[] = [],
): {
  assignments: Map<string, NodeRoleAssignment>;
  unmapped: string[];
} {
  const assignments = new Map<string, NodeRoleAssignment>();
  const pending: GraphBuildInputNode[] = [];
  const sorted = [...nodes].sort((a, b) => a.id.localeCompare(b.id));

  for (const node of sorted) {
    if (node.canonicalRole && ROLE_SET.has(node.canonicalRole)) {
      const role = node.canonicalRole;
      assignments.set(node.id, {
        nodeId: node.id,
        roles: [role],
        layerId: node.businessLane ?? ROLE_LAYER[role],
        reason: "CANONICAL_ROLE",
      });
      continue;
    }

    if (node.businessLane && BUSINESS_LAYER_ORDER.includes(node.businessLane)) {
      const roles = rolesForLocalName(node.localName ?? "");
      assignments.set(node.id, {
        nodeId: node.id,
        roles,
        layerId: node.businessLane,
        reason: roles.length ? "EXACT_ROLE" : "EXTENSION_FALLBACK",
      });
      continue;
    }

    const roles = rolesForLocalName(node.localName ?? "");
    if (roles.length) {
      assignments.set(node.id, {
        nodeId: node.id,
        roles,
        layerId: ROLE_LAYER[roles[0]],
        reason: "EXACT_ROLE",
      });
      continue;
    }

    const moduleLayer = layerForModule(node.module);
    if (moduleLayer) {
      assignments.set(node.id, {
        nodeId: node.id,
        roles: [],
        layerId: moduleLayer,
        reason: "MODULE",
      });
      continue;
    }

    pending.push(node);
  }

  const adjacency = new Map<string, string[]>();
  for (const edge of [...edges].sort(
    (a, b) =>
      a.from.localeCompare(b.from) ||
      a.to.localeCompare(b.to) ||
      a.relation.localeCompare(b.relation),
  )) {
    if (!adjacency.has(edge.from)) adjacency.set(edge.from, []);
    if (!adjacency.has(edge.to)) adjacency.set(edge.to, []);
    adjacency.get(edge.from)?.push(edge.to);
    adjacency.get(edge.to)?.push(edge.from);
  }

  let progressed = true;
  while (progressed) {
    progressed = false;
    const still: GraphBuildInputNode[] = [];
    for (const node of [...pending].sort((a, b) => a.id.localeCompare(b.id))) {
      if (assignments.has(node.id)) continue;
      const scores = new Map<BusinessLayerId, number>();
      for (const neighborId of adjacency.get(node.id) ?? []) {
        const neighbor = assignments.get(neighborId);
        if (!neighbor) continue;
        scores.set(neighbor.layerId, (scores.get(neighbor.layerId) ?? 0) + 1);
      }
      const chosen = pickLayerByScores(scores);
      if (!chosen) {
        still.push(node);
        continue;
      }
      assignments.set(node.id, {
        nodeId: node.id,
        roles: [],
        layerId: chosen,
        reason: "ADJACENCY",
      });
      progressed = true;
    }
    pending.length = 0;
    pending.push(...still);
  }

  for (const node of [...pending].sort((a, b) => a.id.localeCompare(b.id))) {
    const labelLayer = inferLayerFromLabel(
      node.label ?? node.localName ?? node.id,
    );
    const layerId = labelLayer ?? "QUALIFICATION_COMPLIANCE";
    assignments.set(node.id, {
      nodeId: node.id,
      roles: [],
      layerId,
      reason: labelLayer ? "LABEL" : "EXTENSION_FALLBACK",
    });
  }

  const unmapped: string[] = [];
  for (const node of sorted) {
    if (!assignments.has(node.id)) unmapped.push(node.id);
  }

  return { assignments, unmapped };
}

export function projectOntologyEdges(input: {
  edges: GraphBuildInputEdge[];
  projections: VisualProjection[];
  presentationType?: ProjectedGraphEdge["presentationType"];
}): {
  edges: ProjectedGraphEdge[];
  dangling: Array<{ id: string; from: string; to: string }>;
} {
  const bySource = new Map<string, VisualProjection[]>();
  for (const projection of input.projections) {
    if (!projection.sourceNodeId) continue;
    const bucket = bySource.get(projection.sourceNodeId) ?? [];
    bucket.push(projection);
    bySource.set(projection.sourceNodeId, bucket);
  }

  const pickProjection = (
    sourceId: string,
    preferredLayer?: BusinessLayerId,
  ): VisualProjection | undefined => {
    const candidates = bySource.get(sourceId) ?? [];
    if (!candidates.length) return undefined;
    if (preferredLayer) {
      const match = candidates.find((item) => item.layerId === preferredLayer);
      if (match) return match;
    }
    return [...candidates].sort(
      (a, b) =>
        layerIndex(a.layerId) - layerIndex(b.layerId) ||
        a.order - b.order ||
        a.projectionId.localeCompare(b.projectionId),
    )[0];
  };

  const projected: ProjectedGraphEdge[] = [];
  const dangling: Array<{ id: string; from: string; to: string }> = [];

  const sortedEdges = [...input.edges].sort(
    (a, b) =>
      a.from.localeCompare(b.from) ||
      a.to.localeCompare(b.to) ||
      a.relation.localeCompare(b.relation) ||
      (a.id ?? "").localeCompare(b.id ?? ""),
  );

  for (const edge of sortedEdges) {
    const edgeId =
      edge.id ?? `${edge.from}->${edge.to}:${edge.relation}`;
    const sourceCandidates = bySource.get(edge.from) ?? [];
    const targetCandidates = bySource.get(edge.to) ?? [];
    if (!sourceCandidates.length || !targetCandidates.length) {
      dangling.push({ id: edgeId, from: edge.from, to: edge.to });
      console.error("[unified-graph] dangling edge", {
        id: edgeId,
        source: edge.from,
        target: edge.to,
      });
      continue;
    }

    // Prefer same-layer pair, else nearest layer distance.
    let bestSource = sourceCandidates[0];
    let bestTarget = targetCandidates[0];
    let bestScore = Number.POSITIVE_INFINITY;
    for (const source of sourceCandidates) {
      for (const target of targetCandidates) {
        const score = Math.abs(
          layerIndex(source.layerId) - layerIndex(target.layerId),
        );
        const tie =
          source.order - target.order ||
          source.projectionId.localeCompare(target.projectionId);
        if (score < bestScore || (score === bestScore && tie < 0)) {
          bestScore = score;
          bestSource = source;
          bestTarget = target;
        }
      }
    }

    // Stabilize with preferred picks when scores equal.
    bestSource =
      pickProjection(edge.from, bestTarget.layerId) ?? bestSource;
    bestTarget =
      pickProjection(edge.to, bestSource.layerId) ?? bestTarget;

    const labelZh = resolveGraphChineseLabel({
      apiLabelZh: edge.label,
      localName: edge.relation,
      kind: "relation",
    });

    projected.push({
      id: edgeId,
      sourceProjectionId: bestSource.projectionId,
      targetProjectionId: bestTarget.projectionId,
      relationId: edge.relation,
      labelZh,
      sourceEdgeIds: [edgeId],
      presentationType:
        edge.presentationType ?? input.presentationType ?? "ONTOLOGY",
      state: edge.state,
    });
  }

  return { edges: projected, dangling };
}

export function mappingCountByRole(
  assignments: Map<string, NodeRoleAssignment>,
): Map<BusinessRoleId, number> {
  const counts = new Map<BusinessRoleId, number>();
  for (const role of ALL_CORE_ROLES) counts.set(role, 0);
  for (const assignment of assignments.values()) {
    for (const role of assignment.roles) {
      counts.set(role, (counts.get(role) ?? 0) + 1);
    }
    if (!assignment.roles.length) {
      // Extension nodes counted under first role of their layer for overview badges.
      const layerRoles = ALL_CORE_ROLES.filter(
        (role) => ROLE_LAYER[role] === assignment.layerId,
      );
      const anchor = layerRoles[0];
      if (anchor) counts.set(anchor, (counts.get(anchor) ?? 0) + 1);
    }
  }
  return counts;
}

export function extensionCountByRole(
  assignments: Map<string, NodeRoleAssignment>,
): Map<BusinessRoleId, number> {
  const counts = new Map<BusinessRoleId, number>();
  for (const role of ALL_CORE_ROLES) counts.set(role, 0);
  for (const assignment of assignments.values()) {
    if (assignment.roles.length) continue;
    const layerRoles = ALL_CORE_ROLES.filter(
      (role) => ROLE_LAYER[role] === assignment.layerId,
    );
    const anchor = layerRoles[0];
    if (anchor) counts.set(anchor, (counts.get(anchor) ?? 0) + 1);
  }
  return counts;
}

export function roleDisplayLabel(roleId: BusinessRoleId): string {
  return CORE_ROLE_LABELS[roleId];
}
