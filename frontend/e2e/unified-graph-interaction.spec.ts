import { expect, test } from "@playwright/test";

test("unified graph pan/zoom interaction", async ({ page }) => {
  await page.setViewportSize({ width: 1440, height: 900 });
  await page.goto("/ontology");

  const graph = page.getByTestId("ontology-overview-graph");
  await expect(graph).toBeVisible();

  const scaleBefore = Number(await graph.getAttribute("data-graph-scale"));
  const box = await graph.boundingBox();
  expect(box).toBeTruthy();
  if (!box) return;

  await page.mouse.move(box.x + box.width / 2, box.y + box.height / 2);
  await page.mouse.wheel(0, -200);
  const scaleUp = Number(await graph.getAttribute("data-graph-scale"));
  expect(scaleUp).toBeGreaterThan(scaleBefore);

  await page.mouse.wheel(0, 400);
  const scaleDown = Number(await graph.getAttribute("data-graph-scale"));
  expect(scaleDown).toBeLessThan(scaleUp);
  expect(scaleDown).toBeGreaterThanOrEqual(0.35);
  expect(scaleDown).toBeLessThanOrEqual(3);

  // Zoom in so the world exceeds the viewport; otherwise translation is recentered.
  await page.getByRole("button", { name: "放大" }).click();
  await page.getByRole("button", { name: "放大" }).click();

  const txBefore = Number(await graph.getAttribute("data-graph-translate-x"));
  const tyBefore = Number(await graph.getAttribute("data-graph-translate-y"));
  // Drag near the top-left padding of the canvas (lane header, away from nodes).
  await page.mouse.move(box.x + 30, box.y + 30);
  await page.mouse.down();
  await page.mouse.move(box.x + 30 + 120, box.y + 30 + 80, { steps: 8 });
  await page.mouse.up();
  const txAfter = Number(await graph.getAttribute("data-graph-translate-x"));
  const tyAfter = Number(await graph.getAttribute("data-graph-translate-y"));
  expect(Math.abs(txAfter - txBefore) + Math.abs(tyAfter - tyBefore)).toBeGreaterThan(0);

  const node = page.locator("[data-projection-id]").first();
  const xBefore = await node.getAttribute("data-node-x");
  const yBefore = await node.getAttribute("data-node-y");
  await node.click();
  await expect(page.getByTestId("graph-node-details")).toBeVisible();
  expect(await node.getAttribute("data-node-x")).toBe(xBefore);
  expect(await node.getAttribute("data-node-y")).toBe(yBefore);

  await page.getByRole("button", { name: "适应画布" }).click();
  await page.getByRole("button", { name: "重置视图" }).click();

  // Wheel over graph should not scroll the page body.
  const scrollBefore = await page.evaluate(() => window.scrollY);
  await page.mouse.move(box.x + box.width / 2, box.y + box.height / 2);
  await page.mouse.wheel(0, 300);
  const scrollAfter = await page.evaluate(() => window.scrollY);
  expect(scrollAfter).toBe(scrollBefore);
});
