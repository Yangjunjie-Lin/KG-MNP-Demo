import { test, expect } from "@playwright/test";
import { expectChineseUi } from "./helpers";

test("案例三返回真实阻塞原因、规则、条款和追溯图", async ({ page }) => {
  await page.goto("/overview");
  await page.getByRole("button", { name: "运行示例" }).click();
  await expect(page).toHaveURL(/\/assessments\/[^/]+$/);
  await expect(page.getByText("不可携转", { exact: true }).first()).toBeVisible();
  await page.getByRole("button", { name: "阻塞原因" }).click();
  await expect(page.getByText("存在有效合约限制")).toBeVisible();
  await expect(page.getByText("规则四：合约限制检查")).toBeVisible();
  await expect(page.getByText("监管条款四：合约限制要求")).toBeVisible();
  await expect(page.getByText("等待合约到期或办理解约")).toBeVisible();
  await page.getByRole("button", { name: "追溯图" }).click();
  await expect(page.getByText("真实追溯关系：27 个节点，45 条边")).toBeVisible();
  await expect(page.getByTestId("trace-graph")).toBeVisible();
  await expectChineseUi(page);
});
