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
  await page.setViewportSize({ width: 1440, height: 900 });
  await page.goto("/ontology");
  await expect(page.getByRole("button", { name: "总览图" })).toBeVisible();
  await expect(page.getByTestId("ontology-overview-graph")).toBeVisible();

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

  const nodeLaneChecks: Array<[string, string]> = [
    ["ontology-node-Subscriber", "ontology-lane-USER_IDENTITY"],
    ["ontology-node-BillingAccount", "ontology-lane-ACCOUNT_BILLING"],
    ["ontology-node-MobilePlan", "ontology-lane-SERVICE_OFFERING"],
    ["ontology-node-MNPRequest", "ontology-lane-PORTABILITY_PROCESS"],
    ["ontology-node-EligibilityAssessment", "ontology-lane-QUALIFICATION_COMPLIANCE"],
  ];

  for (const [nodeId, laneId] of nodeLaneChecks) {
    const inside = await page.evaluate(
      ([nid, lid]) => {
        const node = document.querySelector(`[data-testid="${nid}"] rect`);
        const lane = document.querySelector(`[data-testid="${lid}"] rect`);
        if (!node || !lane) return false;
        const nx = Number(node.getAttribute("x"));
        const ny = Number(node.getAttribute("y"));
        const nw = Number(node.getAttribute("width"));
        const nh = Number(node.getAttribute("height"));
        const lx = Number(lane.getAttribute("x"));
        const ly = Number(lane.getAttribute("y"));
        const lw = Number(lane.getAttribute("width"));
        const lh = Number(lane.getAttribute("height"));
        return nx >= lx && ny >= ly && nx + nw <= lx + lw && ny + nh <= ly + lh;
      },
      [nodeId, laneId],
    );
    expect(inside, `${nodeId} in ${laneId}`).toBe(true);
  }

  const pathStats = await page.evaluate(() => {
    const graph = document.querySelector('[data-testid="ontology-overview-graph"]');
    if (!graph) return { lines: -1, paths: 0, bad: 0 };
    const lines = graph.querySelectorAll("line").length;
    const paths = [...graph.querySelectorAll("path")].filter((path) =>
      path.closest('[data-testid^="ontology-edge-"]'),
    );
    const bad = paths.filter((path) => /[CQA]/i.test(path.getAttribute("d") ?? "")).length;
    return { lines, paths: paths.length, bad };
  });
  expect(pathStats.lines).toBe(0);
  expect(pathStats.paths).toBeGreaterThan(0);
  expect(pathStats.bad).toBe(0);

  await page.getByTestId("ontology-node-RealNameRegistration").click();
  await expect(page.getByTestId("ontology-node-details")).toContainText("实名登记");

  await page.getByRole("button", { name: "账户与计费层" }).click();
  await expect(page.getByTestId("ontology-node-BillingAccount")).toBeVisible();
  await expect(page.getByTestId("ontology-node-Subscriber")).toHaveCount(0);

  await page.getByRole("button", { name: "总览图" }).click();
  for (const lane of LANES) {
    await expect(page.getByTestId(lane)).toBeVisible();
  }

  await expectChineseUi(page);
});
