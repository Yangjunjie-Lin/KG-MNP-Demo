import { expect, test } from "@playwright/test";
import { expectChineseUi } from "./helpers";

const LANES = [
  "ontology-lane-USER_IDENTITY",
  "ontology-lane-ACCOUNT_BILLING",
  "ontology-lane-SERVICE_OFFERING",
  "ontology-lane-PORTABILITY_PROCESS",
  "ontology-lane-QUALIFICATION_COMPLIANCE",
] as const;

test("本体浏览器五层总览与正交连线", async ({ page }) => {
  await page.setViewportSize({ width: 1664, height: 960 });
  await page.goto("/ontology");
  await expect(page.getByRole("button", { name: "业务总览" })).toBeVisible();

  const graph = page.getByTestId("ontology-overview-graph");
  await expect(graph).toBeVisible();
  await expect(graph).toHaveAttribute("viewBox", "0 0 1664 900");
  await expect(graph).toHaveAttribute("data-graph-dangling-edge-count", "0");
  await expect(graph).toHaveAttribute("data-graph-unmapped-node-count", "0");
  await expect(graph).toHaveAttribute("data-overview-width", "1664");
  await expect(graph).toHaveAttribute("data-canonical-core-node-count", "27");
  await expect(graph).toHaveAttribute("data-canonical-edge-count", "29");
  await expect(graph).toHaveAttribute("data-canonical-geometry-violation-count", "0");

  for (const lane of LANES) {
    await expect(page.getByTestId(lane)).toBeVisible();
  }

  const laneYs = await page.evaluate((ids) => {
    return ids.map((id) => {
      const node = document.querySelector(`[data-testid="${id}"] rect`);
      return node ? Number(node.getAttribute("y")) : Number.NaN;
    });
  }, [...LANES]);

  for (let i = 0; i < laneYs.length - 1; i += 1) {
    expect(laneYs[i]).toBeLessThan(laneYs[i + 1]);
  }

  const pathStats = await page.evaluate(() => {
    const root = document.querySelector('[data-testid="ontology-overview-graph"]');
    if (!root) return { lines: -1, bad: 0 };
    const lines = root.querySelectorAll("line").length;
    const paths = [...root.querySelectorAll("path")];
    const bad = paths.filter((path) => /[LCQSTA]/i.test(path.getAttribute("d") ?? "")).length;
    return { lines, bad };
  });
  expect(pathStats.lines).toBe(0);
  expect(pathStats.bad).toBe(0);
  await expect(graph.locator("[data-role-id]")).toHaveCount(27);
  await expect(graph.locator("[data-canonical-edge-path]")).toHaveCount(29);
  await expect(graph.locator("[data-canonical-bus]")).toHaveCount(1);

  const userNode = graph.locator("[data-role-id='USER']");
  await expect(userNode).toHaveAttribute("data-node-x", "266");
  await expect(userNode).toHaveAttribute("data-node-y", "42");
  const userGeometry = await userNode.evaluate((node) => ({
    x: node.getAttribute("data-node-x"),
    y: node.getAttribute("data-node-y"),
    width: node.getAttribute("data-node-width"),
    height: node.getAttribute("data-node-height"),
  }));

  await userNode.click();
  await expect(page.getByTestId("graph-node-details")).toContainText("用户");

  await page.getByRole("button", { name: "完整本体" }).click();
  await expect(page.getByTestId("ontology-complete-graph")).toBeVisible();

  await page.getByRole("button", { name: "业务总览" }).click();
  for (const lane of LANES) {
    await expect(page.getByTestId(lane)).toBeVisible();
  }
  await expect(page.getByTestId("ontology-overview-graph")).toHaveAttribute(
    "viewBox",
    "0 0 1664 900",
  );
  expect(
    await page
      .getByTestId("ontology-overview-graph")
      .locator("[data-role-id='USER']")
      .evaluate((node) => ({
        x: node.getAttribute("data-node-x"),
        y: node.getAttribute("data-node-y"),
        width: node.getAttribute("data-node-width"),
        height: node.getAttribute("data-node-height"),
      })),
  ).toEqual(userGeometry);

  await expectChineseUi(page);
});
