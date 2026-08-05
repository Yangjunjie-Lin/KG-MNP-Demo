import { expect, test } from "@playwright/test";
import { openCase } from "./helpers";

test("案件追溯使用统一五层图形", async ({ page }) => {
  await page.setViewportSize({ width: 1440, height: 900 });
  await openCase(page, "案例三");
  await page.getByRole("button", { name: "追溯图" }).click();
  await expect(page.getByTestId("trace-graph")).toBeVisible();
  await expect(page.getByTestId("assessment-trace-svg")).toBeVisible();

  for (const lane of [
    "ontology-lane-USER_IDENTITY",
    "ontology-lane-ACCOUNT_BILLING",
    "ontology-lane-SERVICE_OFFERING",
    "ontology-lane-PORTABILITY_PROCESS",
    "ontology-lane-QUALIFICATION_COMPLIANCE",
  ]) {
    await expect(page.getByTestId(lane)).toBeVisible();
  }

  const lineCount = await page
    .locator('[data-testid="assessment-trace-svg"] line')
    .count();
  expect(lineCount).toBe(0);
  await expect(page.getByTestId("assessment-trace-svg")).toHaveAttribute(
    "data-graph-dangling-edge-count",
    "0",
  );
});
