import { test, expect, type Page } from "@playwright/test";
import { expectChineseUi } from "./helpers";

interface HistoryResponse {
  items: Array<{
    execution_id: string;
    assessment_time: string;
  }>;
}

interface AssessmentResponse {
  execution_id: string;
}

interface AssessmentRecordResponse {
  execution_id: string;
  case_id: string;
  assessment_time: string;
}

interface ExampleRunResponse {
  execution_id: string;
  decision: string;
  process?: {
    can_advance?: boolean;
    blocking_reasons?: Array<{ code?: string }>;
  };
}

const unseededAssessmentTime = "2026-07-02T12:34:56";
const expectedAssessmentTime = new Date(unseededAssessmentTime).toISOString();

async function getCase03History(page: Page) {
  const response = await page.request.get("/api/v1/cases/CASE-03/history");
  expect(response.ok()).toBeTruthy();
  return (await response.json()) as HistoryResponse;
}

test("加载示例并提交真实评估，刷新后仍可访问", async ({ page }) => {
  await page.goto("/assessments/new");
  await page.getByRole("button", { name: /加载示例/ }).click();
  await expect(page.getByLabel(/案例编号/)).toHaveValue("CASE-03");
  await page.getByLabel("评估时间").fill(unseededAssessmentTime);
  await expectChineseUi(page);

  const before = await getCase03History(page);
  expect(before.items.some(
    (item) => new Date(item.assessment_time).toISOString() === expectedAssessmentTime,
  )).toBe(false);
  const response = page.waitForResponse((item) => {
    const url = new URL(item.url());
    return item.request().method() === "POST" && url.pathname === "/api/v1/assessments";
  });
  await page.getByRole("button", { name: "提交真实评估" }).click();
  const result = await response;
  expect(result.ok()).toBeTruthy();
  expect(result.request().postDataJSON()).toMatchObject({
    persist: true,
    force_recompute: false,
    payload: { assessment_time: expectedAssessmentTime },
  });
  const payload = (await result.json()) as AssessmentResponse;
  expect(payload.execution_id).toBeTruthy();

  const encodedExecutionId = encodeURIComponent(payload.execution_id);
  await expect(page).toHaveURL(
    new RegExp(`/assessments/${encodedExecutionId.replace(/[.*+?^${}()|[\]\\]/g, "\\$&")}$`),
  );

  const after = await getCase03History(page);
  expect(after.items).toHaveLength(before.items.length + 1);
  const persistedHistory = after.items.find(
    (item) => item.execution_id === payload.execution_id,
  );
  expect(persistedHistory).toBeDefined();
  expect(new Date(persistedHistory!.assessment_time).toISOString()).toBe(expectedAssessmentTime);

  const recordResponse = await page.request.get(
    `/api/v1/assessments/${encodedExecutionId}`,
  );
  expect(recordResponse.ok()).toBeTruthy();
  const record = (await recordResponse.json()) as AssessmentRecordResponse;
  expect(record).toMatchObject({
    execution_id: payload.execution_id,
    case_id: "CASE-03",
  });
  expect(new Date(record.assessment_time).toISOString()).toBe(expectedAssessmentTime);

  await page.reload();
  await expect(page.getByText("资格结论")).toBeVisible();
  await expectChineseUi(page);
});

async function submitSelectedExample(page: Page, caseId: string): Promise<ExampleRunResponse> {
  await page.goto("/assessments/new");
  await page.getByLabel("选择案例").selectOption(caseId);
  await page.getByRole("button", { name: /加载示例/ }).click();
  await expect(page.getByLabel(/案例编号/)).toHaveValue(caseId);
  const response = page.waitForResponse((item) => {
    const url = new URL(item.url());
    return item.request().method() === "POST" && url.pathname === "/api/v1/assessments";
  });
  await page.getByRole("button", { name: "提交真实评估" }).click();
  const result = await response;
  expect(result.ok()).toBeTruthy();
  return (await result.json()) as ExampleRunResponse;
}

test("案例七通过普通表单回填过期授权码，资格可携转但流程不能继续", async ({ page }) => {
  await page.goto("/assessments/new");
  await page.getByLabel("选择案例").selectOption("CASE-07");
  await page.getByRole("button", { name: /加载示例/ }).click();
  await page.getByText("流程补充信息（可选）", { exact: true }).click();
  await expect(page.getByLabel("授权码状态")).toHaveValue("EXPIRED");
  const result = await submitSelectedExample(page, "CASE-07");
  expect(result.decision).toBe("ELIGIBLE");
  expect(result.process?.can_advance).toBe(false);
  expect(result.process?.blocking_reasons?.some((reason) => reason.code === "AUTHORIZATION_CODE_EXPIRED")).toBe(true);
});

test("案例八通过普通表单回填未生效解除协议并保留后端流程语义", async ({ page }) => {
  await page.goto("/assessments/new");
  await page.getByLabel("选择案例").selectOption("CASE-08");
  await page.getByRole("button", { name: /加载示例/ }).click();
  await page.getByText("流程补充信息（可选）", { exact: true }).click();
  await expect(page.getByLabel("解除协议状态")).toHaveValue("SIGNED_PENDING_EFFECTIVE");
  const result = await submitSelectedExample(page, "CASE-08");
  expect(result.decision).toBe("BLOCKED");
  expect(result.process?.blocking_reasons?.some((reason) => reason.code === "TERMINATION_NOT_EFFECTIVE")).toBe(true);
});
