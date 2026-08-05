import { expect, test } from "@playwright/test";

test("unified graph pan/zoom interaction", async ({ page }) => {
  await page.setViewportSize({ width: 1664, height: 960 });
  await page.goto("/ontology");

  const graph = page.getByTestId("ontology-overview-graph");
  await expect(graph).toBeVisible();
  await expect(graph).toHaveAttribute("viewBox", "0 0 1664 900");

  const scaleBefore = Number(await graph.getAttribute("data-graph-scale"));
  const box = await graph.boundingBox();
  expect(box).toBeTruthy();
  if (!box) return;

  const node = graph.locator("[data-role-id='USER']");
  const nodeBoxBefore = await node.boundingBox();
  expect(nodeBoxBefore).toBeTruthy();
  if (!nodeBoxBefore) return;
  const zoomPointer = {
    x: nodeBoxBefore.x + nodeBoxBefore.width / 2,
    y: nodeBoxBefore.y + nodeBoxBefore.height / 2,
  };

  await page.mouse.move(zoomPointer.x, zoomPointer.y);
  await page.mouse.wheel(0, -200);
  await expect
    .poll(async () => Number(await graph.getAttribute("data-graph-scale")))
    .toBeGreaterThan(scaleBefore);
  const scaleUp = Number(await graph.getAttribute("data-graph-scale"));
  expect(scaleUp).toBeGreaterThan(scaleBefore);
  const nodeBoxAfterZoom = await node.boundingBox();
  expect(nodeBoxAfterZoom).toBeTruthy();
  if (!nodeBoxAfterZoom) return;
  expect(
    Math.abs(nodeBoxAfterZoom.x + nodeBoxAfterZoom.width / 2 - zoomPointer.x),
  ).toBeLessThan(2);
  expect(
    Math.abs(nodeBoxAfterZoom.y + nodeBoxAfterZoom.height / 2 - zoomPointer.y),
  ).toBeLessThan(2);

  await page.mouse.wheel(0, 400);
  await expect
    .poll(async () => Number(await graph.getAttribute("data-graph-scale")))
    .toBeLessThan(scaleUp);
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

  const xBefore = await node.getAttribute("data-node-x");
  const yBefore = await node.getAttribute("data-node-y");
  const nodeDragBox = await node.boundingBox();
  expect(nodeDragBox).toBeTruthy();
  if (!nodeDragBox) return;
  const txBeforeNodeDrag = await graph.getAttribute("data-graph-translate-x");
  const tyBeforeNodeDrag = await graph.getAttribute("data-graph-translate-y");
  await page.mouse.move(
    nodeDragBox.x + nodeDragBox.width / 2,
    nodeDragBox.y + nodeDragBox.height / 2,
  );
  await page.mouse.down({ button: "left" });
  await page.mouse.move(
    nodeDragBox.x + nodeDragBox.width / 2 + 80,
    nodeDragBox.y + nodeDragBox.height / 2 + 50,
    { steps: 6 },
  );
  await page.mouse.up({ button: "left" });
  expect(await graph.getAttribute("data-graph-translate-x")).toBe(txBeforeNodeDrag);
  expect(await graph.getAttribute("data-graph-translate-y")).toBe(tyBeforeNodeDrag);

  if (!(await page.getByTestId("graph-node-details").isVisible())) {
    await node.click();
  }
  await expect(page.getByTestId("graph-node-details")).toBeVisible();
  expect(await node.getAttribute("data-node-x")).toBe(xBefore);
  expect(await node.getAttribute("data-node-y")).toBe(yBefore);

  await page.getByRole("button", { name: "适应画布" }).click();
  await expect(graph).toHaveAttribute("data-graph-scale", "1");
  await page.getByRole("button", { name: "放大" }).click();
  await page.getByRole("button", { name: "100%" }).click();
  await expect(graph).toHaveAttribute("data-graph-scale", "1");
  await page.getByRole("button", { name: "重置视图" }).click();
  await expect(graph).toHaveAttribute("data-graph-scale", "1");

  // Wheel over graph should not scroll the page body.
  const scrollBefore = await page.evaluate(() => window.scrollY);
  await page.mouse.move(box.x + box.width / 2, box.y + box.height / 2);
  await page.mouse.wheel(0, 300);
  const scrollAfter = await page.evaluate(() => window.scrollY);
  expect(scrollAfter).toBe(scrollBefore);
});
