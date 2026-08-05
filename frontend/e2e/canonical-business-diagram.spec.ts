import { expect, test, type Page } from "@playwright/test";
import { openCase } from "./helpers";

const CORE_NODE_GEOMETRY = {
  USER: [266, 42, 120, 72],
  VERIFICATION: [610, 42, 198, 72],
  MOBILE_NUMBER_IDENTITY: [969, 42, 195, 72],
  OPERATOR_CURRENT: [1378, 43, 157, 72],
  ACCOUNT: [409, 241, 157, 62],
  BILL: [799, 241, 177, 62],
  PAYMENT: [1275, 241, 157, 62],
  TARIFF_PLAN: [290, 379, 153, 62],
  CONTRACT: [535, 379, 153, 62],
  BROADBAND: [806, 379, 153, 62],
  VALUE_ADDED_SERVICE: [1067, 379, 191, 62],
  USER_RIGHT: [1381, 379, 151, 62],
  PORT_REQUEST: [333, 527, 139, 61],
  MOBILE_NUMBER_PORT: [640, 482, 160, 48],
  OPERATOR_DONOR: [640, 532, 168, 52],
  OPERATOR_RECIPIENT: [640, 584, 168, 52],
  PORT_STEP: [887, 529, 139, 58],
  AUTH_CODE: [1100, 529, 120, 58],
  EXCEPTION_EVENT: [1301, 529, 142, 58],
  IMPACT: [1512, 529, 103, 58],
  ELIGIBILITY_CONDITION: [287, 673, 180, 67],
  REGULATION_RULE: [286, 796, 180, 62],
  SAFETY_CHECK: [630, 672, 247, 99],
  BLOCK_REASON: [1050, 674, 175, 64],
  REMEDIATION_ACTION: [1375, 674, 205, 64],
  EVIDENCE: [1050, 796, 179, 61],
  OPERATOR_EVIDENCE: [1380, 796, 176, 61],
} as const;

const LAYER_GEOMETRY = {
  USER_IDENTITY: [8, 10, 1648, 180],
  ACCOUNT_BILLING: [8, 208, 1648, 114],
  SERVICE_OFFERING: [8, 338, 1648, 122],
  PORTABILITY_PROCESS: [8, 475, 1648, 160],
  QUALIFICATION_COMPLIANCE: [8, 652, 1648, 235],
} as const;

test.beforeEach(async ({ page }) => {
  await page.setViewportSize({ width: 1664, height: 960 });
  await page.goto("/ontology");
});

async function stabilizeVisualState(page: Page) {
  await page.emulateMedia({ reducedMotion: "reduce" });
  await page.addStyleTag({
    content: `
      *, *::before, *::after {
        animation: none !important;
        caret-color: transparent !important;
        transition: none !important;
      }
      [data-testid="graph-minimap"] {
        display: none !important;
      }
    `,
  });
  await page.evaluate(async () => {
    await document.fonts.ready;
    await new Promise<void>((resolve) =>
      requestAnimationFrame(() => requestAnimationFrame(() => resolve())),
    );
  });
}

async function openCanonicalCase(page: Page, caseName: string) {
  await openCase(page, caseName);
  await page.getByRole("button", { name: "追溯图" }).click();
  const graph = page.getByTestId("assessment-trace-svg");
  await expect(graph).toBeVisible();
  await expect(graph).toHaveAttribute("viewBox", "0 0 1664 900");
  await expect(graph).toHaveAttribute("data-canonical-geometry-violation-count", "0");
  await stabilizeVisualState(page);
  return graph;
}

test("canonical overview renders the fixed monochrome geometry", async ({ page }) => {
  const graph = page.getByTestId("ontology-overview-graph");
  await expect(graph).toBeVisible();
  await expect(graph).toHaveAttribute("viewBox", "0 0 1664 900");
  await expect(graph).toHaveAttribute("preserveAspectRatio", "xMidYMid meet");

  const expectedAttributes = {
    "data-canonical-canvas-width": "1664",
    "data-canonical-canvas-height": "900",
    "data-canonical-core-node-count": "27",
    "data-canonical-edge-count": "29",
    "data-canonical-disconnected-source-count": "0",
    "data-canonical-disconnected-target-count": "0",
    "data-canonical-excessive-bend-count": "0",
    "data-canonical-geometry-violation-count": "0",
    "data-edge-through-node-count": "0",
    "data-segment-overlap-count": "0",
    "data-label-inside-node-count": "0",
    "data-node-outside-lane-count": "0",
    "data-canonical-shared-bus-duplicate-count": "0",
  } as const;
  for (const [name, value] of Object.entries(expectedAttributes)) {
    await expect(graph).toHaveAttribute(name, value);
  }

  const layers = await graph.locator('[data-testid^="ontology-lane-"]').evaluateAll(
    (elements) =>
      Object.fromEntries(
        elements.map((element) => {
          const id = element.getAttribute("data-testid")?.replace("ontology-lane-", "") ?? "";
          const rect = element.querySelector(":scope > rect");
          return [
            id,
            {
              geometry: ["x", "y", "width", "height"].map((name) =>
                Number(rect?.getAttribute(name)),
              ),
              fill: rect?.getAttribute("fill"),
              stroke: rect?.getAttribute("stroke"),
              strokeWidth: rect?.getAttribute("stroke-width"),
              radius: rect?.getAttribute("rx"),
            },
          ];
        }),
      ),
  );
  expect(Object.keys(layers)).toHaveLength(5);
  for (const [layerId, geometry] of Object.entries(LAYER_GEOMETRY)) {
    expect(layers[layerId]).toEqual({
      geometry,
      fill: "#ffffff",
      stroke: "#111111",
      strokeWidth: "1.5",
      radius: "0",
    });
  }

  const nodes = await graph.locator("[data-role-id]").evaluateAll((elements) =>
    Object.fromEntries(
      elements.map((element) => [
        element.getAttribute("data-role-id") ?? "",
        [
          Number(element.getAttribute("data-node-x")),
          Number(element.getAttribute("data-node-y")),
          Number(element.getAttribute("data-node-width")),
          Number(element.getAttribute("data-node-height")),
        ],
      ]),
    ),
  );
  expect(nodes).toEqual(CORE_NODE_GEOMETRY);

  const nodeStyleAndLabels = await graph.locator("[data-role-id]").evaluateAll(
    (elements) =>
      elements.map((element) => {
        const rect = element.querySelector(":scope > rect");
        const text = element.querySelector("[data-canonical-node-label]");
        return {
          roleId: element.getAttribute("data-role-id"),
          background: element.getAttribute("data-node-background"),
          radius: element.getAttribute("data-node-radius"),
          fill: rect?.getAttribute("fill"),
          stroke: rect?.getAttribute("stroke"),
          borderWidth: rect?.getAttribute("data-node-border-width"),
          lines: [...(text?.querySelectorAll(":scope > tspan") ?? [])].map(
            (line) => line.textContent?.trim() ?? "",
          ),
        };
      }),
  );
  expect(nodeStyleAndLabels).toHaveLength(27);
  for (const node of nodeStyleAndLabels) {
    expect(node.background).toBe("#ffffff");
    expect(node.radius).toBe("0");
    expect(node.fill).toBe("#ffffff");
    expect(node.stroke).toBe("#111111");
    expect(node.lines).toHaveLength(2);
    expect(node.lines[0]).not.toBe("");
    expect(node.lines[1]).toMatch(/^\(.+\)$/);
    expect(node.borderWidth).toBe(node.roleId === "SAFETY_CHECK" ? "3.5" : "1.5");
  }

  await expect(graph.locator("line")).toHaveCount(0);
  await expect(graph.locator("linearGradient, radialGradient, filter, [filter]")).toHaveCount(0);
  await expect(graph.locator("[data-canonical-marker]")).toHaveCount(1);
});

test("canonical relations use declared M/H/V paths and one shared service bus", async ({ page }) => {
  const graph = page.getByTestId("ontology-overview-graph");
  await expect(graph).toBeVisible();

  await expect(graph.locator("[data-canonical-bus]")).toHaveCount(1);
  await expect(graph.locator("[data-canonical-bus-trunk]")).toHaveCount(1);
  await expect(graph.locator("[data-canonical-edge-path]")).toHaveCount(29);

  const paths = await graph.locator("[data-canonical-edge-path]").evaluateAll(
    (elements) =>
      elements.map((element) => {
        const path = element as SVGPathElement;
        const owner = path.closest("[data-canonical-edge]");
        const d = path.getAttribute("d") ?? "";
        const commands = d.match(/[A-Za-z]/g) ?? [];
        let previousDirection: "H" | "V" | null = null;
        let bends = 0;
        for (const command of commands) {
          const direction = command.toUpperCase();
          if (direction === "M") {
            previousDirection = null;
          } else if (direction === "H" || direction === "V") {
            if (previousDirection && previousDirection !== direction) bends += 1;
            previousDirection = direction;
          }
        }
        return {
          id: path.getAttribute("data-canonical-edge-path"),
          d,
          commands,
          bends,
          declared: Number(
            path.getAttribute("data-declared-bend-count") ??
              owner?.getAttribute("data-declared-bend-count"),
          ),
          sourceRole:
            path.getAttribute("data-source-role") ?? owner?.getAttribute("data-source-role"),
          targetRole:
            path.getAttribute("data-target-role") ?? owner?.getAttribute("data-target-role"),
          stroke: path.getAttribute("stroke"),
        };
      }),
  );

  expect(new Set(paths.map((path) => path.id)).size).toBe(29);
  for (const path of paths) {
    expect(path.commands.length).toBeGreaterThan(1);
    expect(path.commands.every((command) => /^[MHV]$/i.test(command))).toBe(true);
    expect(path.d).not.toMatch(/[LCQSTA]/i);
    expect(path.bends).toBeLessThanOrEqual(path.declared);
    expect(path.bends).toBeLessThanOrEqual(3);
    expect(path.sourceRole).toBeTruthy();
    expect(path.targetRole).toBeTruthy();
    expect(path.stroke).toBe("#111111");
  }

  const submit = graph.getByTestId("graph-edge-struct-user-port");
  await expect(submit).toHaveAttribute("data-source-role", "USER");
  await expect(submit).toHaveAttribute("data-target-role", "PORT_REQUEST");
  const submitPath = submit.locator("[data-canonical-edge-path]");
  await expect(submitPath).toHaveAttribute("d", /^M 302 114 .+ H 333$/);
  await expect(graph).toHaveAttribute("data-canonical-disconnected-source-count", "0");
  await expect(graph).toHaveAttribute("data-canonical-disconnected-target-count", "0");
});

test("wheel zoom and blank-canvas pan preserve canonical world coordinates", async ({ page }) => {
  const graph = page.getByTestId("ontology-overview-graph");
  const userNode = graph.locator('[data-role-id="USER"]');
  await expect(graph).toBeVisible();
  await expect(userNode).toBeVisible();

  const worldGeometryBefore = await userNode.evaluate((node) => ({
    x: node.getAttribute("data-node-x"),
    y: node.getAttribute("data-node-y"),
    width: node.getAttribute("data-node-width"),
    height: node.getAttribute("data-node-height"),
  }));
  const nodeBoxBefore = await userNode.boundingBox();
  expect(nodeBoxBefore).not.toBeNull();
  if (!nodeBoxBefore) return;

  const pointer = {
    x: nodeBoxBefore.x + nodeBoxBefore.width / 2,
    y: nodeBoxBefore.y + nodeBoxBefore.height / 2,
  };
  await page.mouse.move(pointer.x, pointer.y);
  await page.mouse.wheel(0, -220);
  await expect.poll(async () => Number(await graph.getAttribute("data-graph-scale"))).toBeGreaterThan(1);

  const nodeBoxAfterZoom = await userNode.boundingBox();
  expect(nodeBoxAfterZoom).not.toBeNull();
  if (!nodeBoxAfterZoom) return;
  expect(Math.abs(nodeBoxAfterZoom.x + nodeBoxAfterZoom.width / 2 - pointer.x)).toBeLessThan(2);
  expect(Math.abs(nodeBoxAfterZoom.y + nodeBoxAfterZoom.height / 2 - pointer.y)).toBeLessThan(2);

  const graphBox = await graph.boundingBox();
  expect(graphBox).not.toBeNull();
  if (!graphBox) return;
  const translateBefore = {
    x: Number(await graph.getAttribute("data-graph-translate-x")),
    y: Number(await graph.getAttribute("data-graph-translate-y")),
  };
  await page.mouse.move(graphBox.x + 18, graphBox.y + graphBox.height / 2);
  await page.mouse.down({ button: "left" });
  await page.mouse.move(graphBox.x + 98, graphBox.y + graphBox.height / 2 + 48, {
    steps: 8,
  });
  await page.mouse.up({ button: "left" });
  await expect
    .poll(async () => {
      const x = Number(await graph.getAttribute("data-graph-translate-x"));
      const y = Number(await graph.getAttribute("data-graph-translate-y"));
      return Math.abs(x - translateBefore.x) + Math.abs(y - translateBefore.y);
    })
    .toBeGreaterThan(0);

  expect(
    await userNode.evaluate((node) => ({
      x: node.getAttribute("data-node-x"),
      y: node.getAttribute("data-node-y"),
      width: node.getAttribute("data-node-width"),
      height: node.getAttribute("data-node-height"),
    })),
  ).toEqual(worldGeometryBefore);

  await page.getByRole("button", { name: "适应画布" }).click();
  await expect(graph).toHaveAttribute("data-graph-scale", "1");
  await expect(graph).toHaveAttribute("data-graph-translate-x", "0");
  await expect(graph).toHaveAttribute("data-graph-translate-y", "0");
});

test("canonical business overview visual baseline", async ({ page }) => {
  const graph = page.getByTestId("ontology-overview-graph");
  await expect(graph).toBeVisible();
  await expect(graph).toHaveAttribute("data-canonical-geometry-violation-count", "0");
  await stabilizeVisualState(page);
  await expect(graph).toHaveScreenshot("canonical-business-overview.png", {
    animations: "disabled",
    maxDiffPixelRatio: 0.005,
  });
});

test("canonical case 03 visual baseline", async ({ page }) => {
  const graph = await openCanonicalCase(page, "案例三");
  await expect(graph).toHaveScreenshot("canonical-business-case03.png", {
    animations: "disabled",
    maxDiffPixelRatio: 0.005,
  });
});

test("canonical case 06 visual baseline", async ({ page }) => {
  const graph = await openCanonicalCase(page, "案例六");
  await expect(graph).toHaveScreenshot("canonical-business-case06.png", {
    animations: "disabled",
    maxDiffPixelRatio: 0.005,
  });
});

test("canonical case 07 visual baseline", async ({ page }) => {
  const graph = await openCanonicalCase(page, "案例七");
  await expect(graph).toHaveScreenshot("canonical-business-case07.png", {
    animations: "disabled",
    maxDiffPixelRatio: 0.005,
  });
});
