import { test, expect } from "@playwright/test";
import { expectChineseUi } from "./helpers";

test("情景推演调用后端并展示后端规则变化", async ({ page }) => {
  await page.goto("/what-if");
  const retry = page.getByRole("button", { name: "重试" });
  if (await retry.isVisible().catch(() => false)) await retry.click();
  const baseline = page.getByLabel("基准评估");
  await expect(baseline.locator("option")).toHaveCount(9, { timeout: 30_000 });
  const labels = await baseline.locator("option").allTextContents();
  const case03Index = labels.findIndex((label) => label.includes("案例三"));
  expect(case03Index).toBeGreaterThanOrEqual(0);
  await baseline.selectOption({ index: case03Index });
  await page.locator("select").nth(1).selectOption("EXPIRED");
  const request = page.waitForRequest((item) => item.url().includes("/what-if") && item.method() === "POST");
  await page.getByRole("button", { name: "运行后端推演" }).click();
  const sent = await request;
  expect(sent.postDataJSON()).toEqual({ changes: { evidence: { contract: { contract_status: "EXPIRED" } } } });
  await expect(page.getByTestId("what-if-result")).toBeVisible();
  await expect(page.getByText("结论已改变")).toBeVisible();
  await expect(page.getByText("规则四：合约限制检查")).toBeVisible();
  await expectChineseUi(page);
});
