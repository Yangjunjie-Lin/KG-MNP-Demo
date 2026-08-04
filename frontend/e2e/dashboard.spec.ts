import { test, expect, type Page } from "@playwright/test";
import { expectChineseUi } from "./helpers";

interface DashboardResponse {
  ontology: {
    module_count: number;
    class_count: number;
    object_property_count: number;
    data_property_count: number;
    shape_count: number;
    rule_count: number;
    competency_question_count: number;
  };
  example_cases: { total: number };
  executions: { total: number };
  latest_case_states: {
    total: number;
    eligible: number;
    blocked: number;
    manual_review: number;
  };
  example_case_ids: string[];
}

async function expectMetric(page: Page, label: string, value: number) {
  const card = page.getByText(label, { exact: true }).locator("..");
  await expect(card.getByText(String(value), { exact: true })).toBeVisible();
}

test("系统总览使用真实后端统计和九个案例", async ({ page }) => {
  const dashboardResponse = page.waitForResponse((response) => {
    const url = new URL(response.url());
    return (
      response.request().method() === "GET" &&
      url.pathname === "/api/v1/views/dashboard"
    );
  });
  await page.goto("/overview");
  const response = await dashboardResponse;
  expect(response.ok()).toBeTruthy();
  const dashboard = (await response.json()) as DashboardResponse;

  await expect(page.getByText("后端服务：可访问")).toBeVisible();
  const metrics: Array<[string, number]> = [
    ["本体模块", dashboard.ontology.module_count],
    ["本体类", dashboard.ontology.class_count],
    ["对象属性", dashboard.ontology.object_property_count],
    ["数据属性", dashboard.ontology.data_property_count],
    ["约束形状", dashboard.ontology.shape_count],
    ["资格规则", dashboard.ontology.rule_count],
    ["能力问题", dashboard.ontology.competency_question_count],
    ["示例案例", dashboard.example_cases.total],
    ["执行记录", dashboard.executions.total],
    ["当前案例", dashboard.example_case_ids.length],
    ["已运行案例", dashboard.latest_case_states.total],
    ["最新可携转", dashboard.latest_case_states.eligible],
    ["最新不可携转", dashboard.latest_case_states.blocked],
    ["最新需人工复核", dashboard.latest_case_states.manual_review],
  ];
  for (const [label, value] of metrics) await expectMetric(page, label, value);

  expect(dashboard.example_case_ids).toHaveLength(9);
  for (const name of ["案例一", "案例二", "案例三", "案例四", "案例五", "案例六", "案例七", "案例八", "案例九"]) {
    await expect(page.getByText(name, { exact: true }).first()).toBeVisible();
  }
  await expectChineseUi(page);
});
