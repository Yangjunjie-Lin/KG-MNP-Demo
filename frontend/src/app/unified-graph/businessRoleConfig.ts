import {
  CANONICAL_CANVAS,
  CANONICAL_EDGES,
  CANONICAL_NODES,
} from "./canonicalDiagramConfig";
import type { BusinessLayerId, BusinessRoleId } from "./graphTypes";

export const EXTENSION_NODE_SIZE = { width: 142, height: 46 } as const;

export interface CoreRoleDefinition {
  id: BusinessRoleId;
  layerId: BusinessLayerId;
  labelZh: string;
  labelEn: string;
  anchor: { x: number; y: number };
  size: { width: number; height: number };
  x: number;
  y: number;
}

export const ALL_CORE_ROLES: BusinessRoleId[] = CANONICAL_NODES.map(
  (node) => node.id,
);

export const CORE_ROLE_ANCHORS = Object.fromEntries(
  CANONICAL_NODES.map((node) => [
    node.id,
    {
      x: (node.x + node.width / 2) / CANONICAL_CANVAS.width,
      y: (node.y + node.height / 2) / CANONICAL_CANVAS.height,
    },
  ]),
) as Record<BusinessRoleId, { x: number; y: number }>;

export const CORE_ROLE_LABELS = Object.fromEntries(
  CANONICAL_NODES.map((node) => [node.id, node.labelZh]),
) as Record<BusinessRoleId, string>;

export const ROLE_LAYER = Object.fromEntries(
  CANONICAL_NODES.map((node) => [node.id, node.layerId]),
) as Record<BusinessRoleId, BusinessLayerId>;

export const CORE_ROLES_BY_LAYER = Object.fromEntries(
  [
    "USER_IDENTITY",
    "ACCOUNT_BILLING",
    "SERVICE_OFFERING",
    "PORTABILITY_PROCESS",
    "QUALIFICATION_COMPLIANCE",
  ].map((layerId) => [
    layerId,
    CANONICAL_NODES.filter((node) => node.layerId === layerId).map(
      (node) => node.id,
    ),
  ]),
) as Record<BusinessLayerId, BusinessRoleId[]>;

export function roleNodeSize(roleId: BusinessRoleId): {
  width: number;
  height: number;
} {
  const node = CANONICAL_NODES.find((item) => item.id === roleId);
  if (!node) throw new Error(`Unknown canonical business role: ${roleId}`);
  return { width: node.width, height: node.height };
}

export function getCoreRoleDefinitions(): CoreRoleDefinition[] {
  return CANONICAL_NODES.map((node) => ({
    id: node.id,
    layerId: node.layerId,
    labelZh: node.labelZh,
    labelEn: node.labelEn,
    anchor: CORE_ROLE_ANCHORS[node.id],
    size: { width: node.width, height: node.height },
    x: node.x,
    y: node.y,
  }));
}

export function anchorToCenter(
  anchor: { x: number; y: number },
  worldWidth = CANONICAL_CANVAS.width,
  worldHeight = CANONICAL_CANVAS.height,
): { cx: number; cy: number } {
  return { cx: anchor.x * worldWidth, cy: anchor.y * worldHeight };
}

/** Presentation-only relations, sourced from the canonical diagram JSON. */
export interface StructuralRelation {
  id: string;
  fromRole: BusinessRoleId;
  toRole: BusinessRoleId;
  labelZh: string;
  group?: string;
}

export const STRUCTURAL_RELATIONS: StructuralRelation[] = CANONICAL_EDGES.map(
  (edge) => ({
    id: edge.id,
    fromRole: edge.sourceRole,
    toRole: edge.targetRole,
    labelZh: edge.labelZh,
    group: edge.busId,
  }),
);
