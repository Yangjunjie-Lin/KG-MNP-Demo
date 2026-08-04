import { test, expect } from "@playwright/test";
import { expectChineseUi, openCase } from "./helpers";

test("案例六保留历史与当前规则语义", async ({ page }) => {
  await openCase(page, "案例六");
  await expect(page.getByText("历史规则版本 1.0 / 120 天")).toBeVisible();
  await expect(page.getByText("当前规则版本 1.1 / 180 天")).toBeVisible();
  await expect(page.getByText("可携转", { exact: true }).first()).toBeVisible();
  await expect(page.getByText("不可携转", { exact: true }).first()).toBeVisible();
  await page.goto("/rules");
  await expect(page.getByText("受影响的历史评估")).toBeVisible();
  await expect(page.getByText("案例六", { exact: true }).last()).toBeVisible();
  await expectChineseUi(page);
});
