import { render, screen, waitFor } from "@testing-library/react";
import { describe, expect, it } from "vitest";
import App from "../App";
import { SystemOverview } from "../pages/SystemOverview";
import { CaseHistory } from "../pages/CaseHistory";
import { AssessmentResult } from "../pages/AssessmentResult";
import { OntologyBrowser } from "../pages/OntologyBrowser";
import { CompetencyQuestions } from "../pages/CompetencyQuestions";
import { RulesAndVersions } from "../pages/RulesAndVersions";
import { WhatIfExperiment } from "../pages/WhatIfExperiment";
import { SystemStatus } from "../pages/SystemStatus";
import { NewAssessment } from "../pages/NewAssessment";
import { findForbiddenVisibleText } from "../i18n/forbiddenVisibleTokens";
import { DecisionBadge, StatusBadge } from "../components/StatusBadges";
import { translateOrUnknown, ruleLabels, stepStatusLabels, ui } from "../i18n/zh-CN";
import type { Decision } from "../types/common";

function assertNoForbidden(label: string, text: string | null) {
  const content = text ?? "";
  const hits = findForbiddenVisibleText(content);
  expect(hits, `${label} 发现禁止词: ${hits.join(", ")}`).toEqual([]);
}

describe("中文界面与安全映射", () => {
  it("系统总览不出现禁止词", async () => {
    const { container } = render(<SystemOverview onCaseClick={() => undefined} />);
    await waitFor(() => {
      expect(container.textContent).toContain("本体统计");
    });
    assertNoForbidden("系统总览", container.textContent);
  });

  it("案件列表不出现禁止词", async () => {
    const { container } = render(<CaseHistory onCaseClick={() => undefined} />);
    await waitFor(() => {
      expect(container.textContent).toMatch(/案例/);
    });
    assertNoForbidden("案件列表", container.textContent);
  });

  it("案例三评估详情不出现禁止词", async () => {
    const { container } = render(
      <AssessmentResult caseId="CASE-03" onBack={() => undefined} />,
    );
    await waitFor(() => {
      expect(container.textContent).toContain("案例三");
    });
    assertNoForbidden("案例三", container.textContent);
  });

  it("本体浏览器不出现禁止词", async () => {
    const { container } = render(<OntologyBrowser />);
    await waitFor(() => {
      expect(container.textContent).toMatch(/本体|模块|携转/);
    });
    assertNoForbidden("本体浏览器", container.textContent);
  });

  it("能力问题不出现禁止词", async () => {
    const { container } = render(<CompetencyQuestions />);
    await waitFor(() => {
      expect(container.textContent).toMatch(/问题/);
    });
    assertNoForbidden("能力问题", container.textContent);
  });

  it("规则与版本不出现禁止词", async () => {
    const { container } = render(<RulesAndVersions />);
    await waitFor(() => {
      expect(container.textContent).toMatch(/规则/);
    });
    assertNoForbidden("规则与版本", container.textContent);
  });

  it("情景推演不出现禁止词", async () => {
    const { container } = render(<WhatIfExperiment />);
    await waitFor(() => {
      expect(container.textContent).toMatch(/基准|推演|情景/);
    });
    assertNoForbidden("情景推演", container.textContent);
  });

  it("系统状态不出现禁止词", async () => {
    const { container } = render(<SystemStatus />);
    expect(container.textContent).toContain("系统状态");
    assertNoForbidden("系统状态", container.textContent);
  });

  it("新建评估正式界面不显示原始 JSON 字段", () => {
    const { container } = render(<NewAssessment />);
    expect(container.textContent).toContain("表单录入");
    expect(container.textContent).not.toContain("schema_version");
    expect(container.textContent).not.toContain("case_id");
    expect(container.textContent).not.toContain("技术调试");
    assertNoForbidden("新建评估", container.textContent);
  });

  it("应用壳层不出现禁止词", async () => {
    const { container } = render(<App />);
    await waitFor(() => {
      expect(container.textContent).toContain("携号转网资格判断本体系统");
    });
    assertNoForbidden("App", container.textContent);
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
