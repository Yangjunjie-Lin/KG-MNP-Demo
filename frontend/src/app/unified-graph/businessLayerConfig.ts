import type { BusinessLayerId, LayerGeometry } from "./graphTypes";

export const BUSINESS_LAYER_ORDER: BusinessLayerId[] = [
  "USER_IDENTITY",
  "ACCOUNT_BILLING",
  "SERVICE_OFFERING",
  "PORTABILITY_PROCESS",
  "QUALIFICATION_COMPLIANCE",
];

export const BUSINESS_LAYER_LABELS: Record<BusinessLayerId, string> = {
  USER_IDENTITY: "1. 用户与身份层",
  ACCOUNT_BILLING: "2. 账户与计费层",
  SERVICE_OFFERING: "3. 业务与服务层",
  PORTABILITY_PROCESS: "4. 携号转网流程层",
  QUALIFICATION_COMPLIANCE: "5. 资格与合规层",
};

export const BUSINESS_WORLD = {
  width: 1600,
  height: 1100,
} as const;

export const BUSINESS_LAYER_BOUNDS: Record<
  BusinessLayerId,
  { xRatio: number; yRatio: number; widthRatio: number; heightRatio: number }
> = {
  USER_IDENTITY: {
    xRatio: 0.01,
    yRatio: 0.01,
    widthRatio: 0.98,
    heightRatio: 0.17,
  },
  ACCOUNT_BILLING: {
    xRatio: 0.01,
    yRatio: 0.2,
    widthRatio: 0.98,
    heightRatio: 0.12,
  },
  SERVICE_OFFERING: {
    xRatio: 0.01,
    yRatio: 0.34,
    widthRatio: 0.98,
    heightRatio: 0.14,
  },
  PORTABILITY_PROCESS: {
    xRatio: 0.01,
    yRatio: 0.5,
    widthRatio: 0.98,
    heightRatio: 0.19,
  },
  QUALIFICATION_COMPLIANCE: {
    xRatio: 0.01,
    yRatio: 0.71,
    widthRatio: 0.98,
    heightRatio: 0.28,
  },
};

export const LAYER_STYLES: Record<
  BusinessLayerId,
  { border: string; background: string; accent: string }
> = {
  USER_IDENTITY: {
    border: "#94a3b8",
    background: "#f8fafc",
    accent: "#475569",
  },
  ACCOUNT_BILLING: {
    border: "#7dd3fc",
    background: "#f0f9ff",
    accent: "#0369a1",
  },
  SERVICE_OFFERING: {
    border: "#a5b4fc",
    background: "#eef2ff",
    accent: "#4338ca",
  },
  PORTABILITY_PROCESS: {
    border: "#5eead4",
    background: "#f0fdfa",
    accent: "#0f766e",
  },
  QUALIFICATION_COMPLIANCE: {
    border: "#86efac",
    background: "#f0fdf4",
    accent: "#15803d",
  },
};

export const LAYER_HEADER_WIDTH_RATIO = 0.13;
export const LAYER_CONTENT_GAP = 24;

export function layerHeaderWidth(worldWidth = BUSINESS_WORLD.width): number {
  return LAYER_HEADER_WIDTH_RATIO * worldWidth;
}

export function contentStartX(worldWidth = BUSINESS_WORLD.width): number {
  return layerHeaderWidth(worldWidth) + LAYER_CONTENT_GAP;
}

export function computeLayerGeometries(
  worldWidth = BUSINESS_WORLD.width,
  worldHeight = BUSINESS_WORLD.height,
  heightOverrides: Partial<Record<BusinessLayerId, number>> = {},
): LayerGeometry[] {
  const headerWidth = layerHeaderWidth(worldWidth);
  const contentX = contentStartX(worldWidth);

  return BUSINESS_LAYER_ORDER.map((id) => {
    const bounds = BUSINESS_LAYER_BOUNDS[id];
    const x = bounds.xRatio * worldWidth;
    const y = bounds.yRatio * worldHeight;
    const width = bounds.widthRatio * worldWidth;
    const height = heightOverrides[id] ?? bounds.heightRatio * worldHeight;
    return {
      id,
      label: BUSINESS_LAYER_LABELS[id],
      x,
      y,
      width,
      height,
      contentX,
      contentY: y,
      contentWidth: width - (contentX - x),
      contentHeight: height,
      routeBottomY: y + height + 18,
    };
  });
}

export function layerIndex(layerId: BusinessLayerId): number {
  return BUSINESS_LAYER_ORDER.indexOf(layerId);
}
