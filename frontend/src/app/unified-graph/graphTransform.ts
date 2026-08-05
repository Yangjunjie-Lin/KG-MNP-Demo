import type { GraphTransformState, Point, Rect } from "./graphTypes";

export const MIN_SCALE = 0.35;
export const MAX_SCALE = 3.0;
export const MIN_VISIBLE_MARGIN = 80;
export const DRAG_THRESHOLD_PX = 4;
export const FIT_PADDING = 32;

export function clamp(value: number, min: number, max: number): number {
  return Math.min(max, Math.max(min, value));
}

export function clampScale(scale: number): number {
  return clamp(scale, MIN_SCALE, MAX_SCALE);
}

export function screenToWorld(
  screen: Point,
  transform: GraphTransformState,
): Point {
  return {
    x: (screen.x - transform.translateX) / transform.scale,
    y: (screen.y - transform.translateY) / transform.scale,
  };
}

export function worldToScreen(
  world: Point,
  transform: GraphTransformState,
): Point {
  return {
    x: world.x * transform.scale + transform.translateX,
    y: world.y * transform.scale + transform.translateY,
  };
}

export function zoomAtPointer(input: {
  transform: GraphTransformState;
  pointerX: number;
  pointerY: number;
  nextScale: number;
}): GraphTransformState {
  const nextScale = clampScale(input.nextScale);
  const world = screenToWorld(
    { x: input.pointerX, y: input.pointerY },
    input.transform,
  );
  return {
    scale: nextScale,
    translateX: input.pointerX - world.x * nextScale,
    translateY: input.pointerY - world.y * nextScale,
  };
}

export function zoomByFactor(
  transform: GraphTransformState,
  factor: number,
  centerX: number,
  centerY: number,
): GraphTransformState {
  return zoomAtPointer({
    transform,
    pointerX: centerX,
    pointerY: centerY,
    nextScale: transform.scale * factor,
  });
}

export function panByDelta(
  transform: GraphTransformState,
  dx: number,
  dy: number,
): GraphTransformState {
  return {
    ...transform,
    translateX: transform.translateX + dx,
    translateY: transform.translateY + dy,
  };
}

export function clampTranslation(
  transform: GraphTransformState,
  viewport: Rect,
  world: Rect,
  margin = MIN_VISIBLE_MARGIN,
): GraphTransformState {
  const scaledWidth = world.width * transform.scale;
  const scaledHeight = world.height * transform.scale;

  const minTranslateX = viewport.width - scaledWidth - margin;
  const maxTranslateX = margin;
  const minTranslateY = viewport.height - scaledHeight - margin;
  const maxTranslateY = margin;

  let translateX = transform.translateX;
  let translateY = transform.translateY;

  if (scaledWidth + margin * 2 <= viewport.width) {
    translateX = (viewport.width - scaledWidth) / 2;
  } else {
    translateX = clamp(translateX, minTranslateX, maxTranslateX);
  }

  if (scaledHeight + margin * 2 <= viewport.height) {
    translateY = (viewport.height - scaledHeight) / 2;
  } else {
    translateY = clamp(translateY, minTranslateY, maxTranslateY);
  }

  return { ...transform, translateX, translateY };
}

export function fitGraphToViewport(input: {
  viewportWidth: number;
  viewportHeight: number;
  graphWorldWidth: number;
  graphWorldHeight: number;
  padding?: number;
  maxScale?: number;
}): GraphTransformState {
  const padding = input.padding ?? FIT_PADDING;
  const maxScale = input.maxScale ?? 1;
  const scaleX = (input.viewportWidth - padding * 2) / input.graphWorldWidth;
  const scaleY = (input.viewportHeight - padding * 2) / input.graphWorldHeight;
  const scale = clamp(Math.min(scaleX, scaleY), MIN_SCALE, maxScale);
  const translateX =
    (input.viewportWidth - input.graphWorldWidth * scale) / 2;
  const translateY =
    (input.viewportHeight - input.graphWorldHeight * scale) / 2;
  return { scale, translateX, translateY };
}

export function scaleAt100Percent(
  transform: GraphTransformState,
  centerX: number,
  centerY: number,
): GraphTransformState {
  return zoomAtPointer({
    transform,
    pointerX: centerX,
    pointerY: centerY,
    nextScale: 1,
  });
}

export function exceedsDragThreshold(
  startX: number,
  startY: number,
  currentX: number,
  currentY: number,
  threshold = DRAG_THRESHOLD_PX,
): boolean {
  const dx = currentX - startX;
  const dy = currentY - startY;
  return Math.hypot(dx, dy) > threshold;
}
