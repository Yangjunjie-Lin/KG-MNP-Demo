import { test, expect } from "@playwright/test";
import { expectChineseUi, openCase } from "./helpers";

test("案例七区分资格与流程状态", async ({ page }) => {
  await openCase(page, "案例七");
  await expect(page.getByText("可携转", { exact: true }).first()).toBeVisible();
  await expect(page.getByText(/授权码已过期，流程不能继续/)).toBeVisible();
  await page.getByRole("button", { name: "流程状态" }).click();
  await expect(page.getByText("不能继续", { exact: true })).toBeVisible();
  await expect(page.getByText(/授权码状态\s*已过期/)).toBeVisible();
  await expectChineseUi(page);
});
