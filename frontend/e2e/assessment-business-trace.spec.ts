import { expect, test, type Locator, type Page } from "@playwright/test";
import { openCase } from "./helpers";

const LANES = [
  "ontology-lane-USER_IDENTITY",
  "ontology-lane-ACCOUNT_BILLING",
  "ontology-lane-SERVICE_OFFERING",
  "ontology-lane-PORTABILITY_PROCESS",
  "ontology-lane-QUALIFICATION_COMPLIANCE",
] as const;

async function openTrace(page: Page, caseName: string): Promise<Locator> {
  await openCase(page, caseName);
  await page.getByRole("button", { name: "追溯图" }).click();
  await expect(page.getByTestId("trace-graph")).toBeVisible();
  const graph = page.getByTestId("assessment-trace-svg");
  await expect(graph).toBeVisible();
  return graph;
}

async function canonicalGeometry(graph: Locator) {
  return graph.evaluate((root) => ({
    nodes: Object.fromEntries(
      [...root.querySelectorAll("[data-role-id]")].map((node) => [
        node.getAttribute("data-role-id") ?? "",
        [
          node.getAttribute("data-node-x"),
          node.getAttribute("data-node-y"),
          node.getAttribute("data-node-width"),
          node.getAttribute("data-node-height"),
        ],
      ]),
    ),
    paths: Object.fromEntries(
      [...root.querySelectorAll("[data-canonical-edge-path]")].map((path) => [
        path.getAttribute("data-canonical-edge-path") ?? "",
        path.getAttribute("d"),
      ]),
    ),
  }));
}

test("案件追溯使用统一五层图形", async ({ page }) => {
  await page.setViewportSize({ width: 1664, height: 960 });
  const graph = await openTrace(page, "案例三");
  await expect(graph).toHaveAttribute("viewBox", "0 0 1664 900");
  await expect(graph).toHaveAttribute("data-canonical-canvas-width", "1664");
  await expect(graph).toHaveAttribute("data-canonical-canvas-height", "900");
  await expect(graph).toHaveAttribute("data-canonical-core-node-count", "27");
  await expect(graph).toHaveAttribute("data-canonical-edge-count", "29");
  await expect(graph).toHaveAttribute("data-canonical-disconnected-source-count", "0");
  await expect(graph).toHaveAttribute("data-canonical-disconnected-target-count", "0");
  await expect(graph).toHaveAttribute("data-canonical-excessive-bend-count", "0");
  await expect(graph).toHaveAttribute("data-canonical-geometry-violation-count", "0");

  for (const lane of LANES) {
    await expect(page.getByTestId(lane)).toBeVisible();
  }

  await expect(graph.locator("[data-role-id]")).toHaveCount(27);
  await expect(graph.locator("[data-canonical-edge-path]")).toHaveCount(29);
  await expect(graph.locator("[data-canonical-bus]")).toHaveCount(1);
  await expect(graph.locator("line")).toHaveCount(0);
  await expect(graph).toHaveAttribute("data-graph-dangling-edge-count", "0");
});

test("案例三、六、七复用完全相同的核心坐标和路径", async ({ page }) => {
  await page.setViewportSize({ width: 1664, height: 960 });
  let baseline: Awaited<ReturnType<typeof canonicalGeometry>> | undefined;

  for (const caseName of ["案例三", "案例六", "案例七"]) {
    const graph = await openTrace(page, caseName);
    const geometry = await canonicalGeometry(graph);
    expect(Object.keys(geometry.nodes)).toHaveLength(27);
    expect(Object.keys(geometry.paths)).toHaveLength(29);
    if (!baseline) {
      baseline = geometry;
    } else {
      expect(geometry).toEqual(baseline);
    }
  }
});
