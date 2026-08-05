import { expect, test } from "@playwright/test";

const LANES = [
  "ontology-lane-USER_IDENTITY",
  "ontology-lane-ACCOUNT_BILLING",
  "ontology-lane-SERVICE_OFFERING",
  "ontology-lane-PORTABILITY_PROCESS",
  "ontology-lane-QUALIFICATION_COMPLIANCE",
] as const;

test("业务总览五层结构与核心角色", async ({ page }) => {
  await page.setViewportSize({ width: 1440, height: 900 });
  await page.goto("/ontology");
  await expect(page.getByRole("button", { name: "业务总览" })).toBeVisible();

  const graph = page.getByTestId("ontology-overview-graph");
  await expect(graph).toBeVisible();
  await expect(graph).toHaveAttribute("data-graph-dangling-edge-count", "0");
  await expect(graph).toHaveAttribute("data-graph-unmapped-node-count", "0");

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

  await expect(page.locator("[data-role-id='USER']").first()).toBeVisible();
  await expect(page.locator("[data-role-id='SAFETY_CHECK']").first()).toBeVisible();

  // No SVG <line> elements in the business graph itself (icons elsewhere may use <line>).
  const lineCount = await page
    .locator('[data-testid="ontology-overview-graph"] line')
    .count();
  expect(lineCount).toBe(0);
});

test("完整本体模式渲染全部投影", async ({ page }) => {
  await page.setViewportSize({ width: 1440, height: 900 });
  await page.goto("/ontology");
  await page.getByRole("button", { name: "完整本体" }).click();
  const graph = page.getByTestId("ontology-complete-graph");
  await expect(graph).toBeVisible();
  const rendered = Number(await graph.getAttribute("data-rendered-node-count"));
  const runtime = Number(await graph.getAttribute("data-runtime-node-count"));
  expect(rendered).toBeGreaterThan(0);
  expect(runtime).toBeGreaterThan(0);
  await expect(graph).toHaveAttribute("data-graph-dangling-edge-count", "0");
});
