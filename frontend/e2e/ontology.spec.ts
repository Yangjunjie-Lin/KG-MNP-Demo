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
  const layoutErrors: string[] = [];
  page.on("console", (message) => {
    if (
      message.type() === "error" &&
      message.text().includes("[ontology-layout]")
    ) {
      layoutErrors.push(message.text());
    }
  });

  const response = await page.request.get(
    "http://127.0.0.1:8000/api/v1/views/ontology",
  );
  expect(response.ok()).toBe(true);
  const payload = await response.json();
  expect(payload.graph.nodes.length).toBeGreaterThan(0);
  expect(payload.graph.edges.length).toBeGreaterThan(0);

  await page.setViewportSize({ width: 1440, height: 900 });
  await page.goto("/ontology");
  await expect(page.getByRole("button", { name: "总览图" })).toBeVisible();

  const graph = page.getByTestId("ontology-overview-graph");
  await expect(graph).toBeVisible();

  await expect(graph).toHaveAttribute("data-geometry-violation-count", "0");
  await expect(graph).toHaveAttribute("data-edge-through-node-count", "0");
  await expect(graph).toHaveAttribute("data-segment-overlap-count", "0");
  await expect(graph).toHaveAttribute("data-label-inside-node-count", "0");
  await expect(graph).toHaveAttribute("data-node-outside-lane-count", "0");
  await expect(graph).toHaveAttribute("data-duplicate-cross-channel-count", "0");
  await expect(graph).toHaveAttribute("data-unmapped-node-count", "0");

  const width = Number(await graph.getAttribute("data-overview-width"));
  expect(width).toBeGreaterThanOrEqual(1600);
  expect(width).toBeLessThanOrEqual(2200);

  const runtimeNodeCount = Number(
    await graph.getAttribute("data-runtime-node-count"),
  );
  const runtimeEdgeCount = Number(
    await graph.getAttribute("data-runtime-edge-count"),
  );
  const renderedNodeCount = Number(
    await graph.getAttribute("data-rendered-node-count"),
  );
  const renderedEdgeCount = Number(
    await graph.getAttribute("data-rendered-edge-count"),
  );
  expect(runtimeNodeCount).toBeGreaterThan(0);
  expect(runtimeEdgeCount).toBeGreaterThan(0);
  expect(renderedNodeCount).toBe(runtimeNodeCount);
  expect(renderedEdgeCount).toBe(runtimeEdgeCount);

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
    const root = document.querySelector('[data-testid="ontology-overview-graph"]');
    if (!root) return { lines: -1, paths: 0, bad: 0 };
    const lines = root.querySelectorAll("line").length;
    const paths = [...root.querySelectorAll("path")].filter((path) =>
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
  expect(layoutErrors).toEqual([]);
});
