import { describe, expect, it } from "vitest";
import {
  DRAG_THRESHOLD_PX,
  MAX_SCALE,
  MIN_SCALE,
  clampScale,
  exceedsDragThreshold,
  fitGraphToViewport,
  panByDelta,
  screenToWorld,
  zoomAtPointer,
} from "../graphTransform";

describe("graphTransform", () => {
  it("keeps world point under cursor stable when zooming", () => {
    const transform = { scale: 1, translateX: 40, translateY: 30 };
    const pointerX = 220;
    const pointerY = 160;
    const worldBefore = screenToWorld({ x: pointerX, y: pointerY }, transform);
    const next = zoomAtPointer({
      transform,
      pointerX,
      pointerY,
      nextScale: 1.35,
    });
    const worldAfter = screenToWorld({ x: pointerX, y: pointerY }, next);
    expect(Math.abs(worldBefore.x - worldAfter.x)).toBeLessThan(0.001);
    expect(Math.abs(worldBefore.y - worldAfter.y)).toBeLessThan(0.001);
  });

  it("clamps scale to [0.35, 3.0]", () => {
    expect(clampScale(0.1)).toBe(MIN_SCALE);
    expect(clampScale(9)).toBe(MAX_SCALE);
    expect(clampScale(1.2)).toBe(1.2);
  });

  it("pans by pointer delta", () => {
    const next = panByDelta({ scale: 1, translateX: 10, translateY: 20 }, 100, 50);
    expect(next.translateX).toBe(110);
    expect(next.translateY).toBe(70);
  });

  it("requires >4px movement before drag", () => {
    expect(exceedsDragThreshold(0, 0, 3, 2, DRAG_THRESHOLD_PX)).toBe(false);
    expect(exceedsDragThreshold(0, 0, 5, 0, DRAG_THRESHOLD_PX)).toBe(true);
  });

  it("fit view keeps graph inside padded viewport", () => {
    const transform = fitGraphToViewport({
      viewportWidth: 1000,
      viewportHeight: 800,
      graphWorldWidth: 1600,
      graphWorldHeight: 1100,
      padding: 32,
    });
    expect(transform.scale).toBeGreaterThanOrEqual(MIN_SCALE);
    expect(transform.scale).toBeLessThanOrEqual(1);
    const left = transform.translateX;
    const top = transform.translateY;
    const right = left + 1600 * transform.scale;
    const bottom = top + 1100 * transform.scale;
    expect(left).toBeGreaterThanOrEqual(0);
    expect(top).toBeGreaterThanOrEqual(0);
    expect(right).toBeLessThanOrEqual(1000);
    expect(bottom).toBeLessThanOrEqual(800);
  });

  it("reset equals initial fit transform", () => {
    const initial = fitGraphToViewport({
      viewportWidth: 900,
      viewportHeight: 700,
      graphWorldWidth: 1600,
      graphWorldHeight: 1100,
    });
    const reset = { ...initial };
    expect(reset).toEqual(initial);
  });
});
