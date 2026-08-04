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
  const executionId = new URL(page.url()).pathname.split("/").pop();
  expect(executionId).toBeTruthy();
  const traceResponse = await page.request.get(
    `/api/v1/views/assessments/${encodeURIComponent(executionId!)}/trace`,
  );
  expect(traceResponse.ok()).toBeTruthy();
  const trace = await traceResponse.json() as { node_count: number; edge_count: number };
  expect(trace.node_count).toBeGreaterThan(0);
  expect(trace.edge_count).toBeGreaterThan(0);
  await expect(page.getByText(`真实追溯关系：${trace.node_count} 个节点，${trace.edge_count} 条边`)).toBeVisible();
  await expect(page.getByText("案例三", { exact: true }).last()).toBeVisible();
  await expect(page.getByText("案例三资格评估", { exact: true })).toBeVisible();
  await expect(page.getByText("合约状态证据", { exact: true })).toBeVisible();
  await expect(page.getByText("存在有效合约限制", { exact: true })).toBeVisible();
  await expect(page.getByText("规则四：合约限制检查", { exact: true })).toBeVisible();
  await expect(page.getByText("监管条款四：合约限制要求", { exact: true })).toBeVisible();
  await expect(page.getByText("等待合约到期或办理解约", { exact: true })).toBeVisible();
  await expect(page.getByTestId("trace-graph")).toBeVisible();
  await page.getByText("合约状态证据", { exact: true }).click();
  const nodeDetails = page.getByTestId("trace-node-details");
  await expect(nodeDetails.getByText("节点类型", { exact: true })).toBeVisible();
  await expect(nodeDetails.getByText("节点名称", { exact: true })).toBeVisible();
  await expect(nodeDetails.getByText("关系数量", { exact: true })).toBeVisible();
  await expect(nodeDetails.getByText("合约状态证据", { exact: true })).toBeVisible();
  await expectChineseUi(page);
});
