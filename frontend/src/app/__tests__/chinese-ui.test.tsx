import { render, waitFor } from "@testing-library/react";
import { describe, expect, it } from "vitest";
import { renderApp } from "../../test/renderWithProviders";
import { DecisionBadge, StatusBadge } from "../components/StatusBadges";
import { findForbiddenVisibleText } from "../i18n/forbiddenVisibleTokens";
import { ruleLabels, stepStatusLabels, translateOrUnknown, ui } from "../i18n/zh-CN";
import type { Decision } from "../types/common";

function assertNoForbidden(label: string, text: string | null) {
  const content = text ?? "";
  const hits = findForbiddenVisibleText(content);
  expect(hits, `${label} 发现禁止词: ${hits.join(", ")}`).toEqual([]);
}

async function renderRoute(route: string, expected: RegExp | string) {
  const result = renderApp(route);
  await waitFor(() => {
    if (typeof expected === "string") {
      expect(result.container.textContent).toContain(expected);
    } else {
      expect(result.container.textContent).toMatch(expected);
    }
  });
  return result;
}

describe("中文界面与安全映射", () => {
  it("系统总览不出现禁止词", async () => {
    const { container } = await renderRoute("/overview", "真实数据统计");
    assertNoForbidden("系统总览", container.textContent);
  });

  it("案件列表不出现禁止词", async () => {
    const { container } = await renderRoute("/cases", "案例九");
    assertNoForbidden("案件列表", container.textContent);
  });

  it("案例三评估详情不出现禁止词", async () => {
    const { container } = await renderRoute("/assessments/exec-case03", "案例三");
    assertNoForbidden("案例三", container.textContent);
  });

  it("本体浏览器不出现禁止词", async () => {
    const { container } = await renderRoute("/ontology", "本体模块");
    assertNoForbidden("本体浏览器", container.textContent);
  });

  it("能力问题不出现禁止词", async () => {
    const { container } = await renderRoute("/competency-questions", /能力问题/);
    assertNoForbidden("能力问题", container.textContent);
  });

  it("规则与版本不出现禁止词", async () => {
    const { container } = await renderRoute("/rules", "规则列表");
    assertNoForbidden("规则与版本", container.textContent);
  });

  it("情景推演不出现禁止词", async () => {
    const { container } = await renderRoute("/what-if", "基准评估");
    assertNoForbidden("情景推演", container.textContent);
  });

  it("系统状态不出现禁止词", async () => {
    const { container } = await renderRoute("/system", "系统状态");
    assertNoForbidden("系统状态", container.textContent);
  });

  it("新建评估正式界面不显示原始 JSON 字段", async () => {
    const { container } = await renderRoute("/assessments/new", "新建资格评估");
    expect(container.textContent).not.toContain("schema_version");
    expect(container.textContent).not.toContain("case_id");
    expect(container.textContent).not.toContain("技术调试");
    assertNoForbidden("新建评估", container.textContent);
  });

  it("应用壳层不出现禁止词", async () => {
    const { container } = await renderRoute("/overview", "携号转网资格判断本体系统");
    assertNoForbidden("应用壳层", container.textContent);
  });

  it("未知状态与规则名显示中文未知提示", () => {
    const { container: statusContainer } = render(
      <StatusBadge status="UNKNOWN_NEW_STATUS" />,
    );
    expect(statusContainer.textContent).toContain(ui.unknownStatus);
    expect(statusContainer.textContent).not.toContain("UNKNOWN_NEW_STATUS");

    const mapped = translateOrUnknown(ruleLabels, "NEW_RULE_TYPE", ui.unknownRule);
    expect(mapped).toBe(ui.unknownRule);
    expect(mapped).not.toContain("NEW_RULE_TYPE");

    const { container: decisionContainer } = render(
      <DecisionBadge decision={"UNKNOWN_DECISION" as Decision} />,
    );
    expect(decisionContainer.textContent).toContain(ui.unknownStatus);

    expect(translateOrUnknown(stepStatusLabels, null, ui.unknownStatus)).toBe("暂无信息");
  });
});
