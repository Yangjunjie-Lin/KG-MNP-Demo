import { fireEvent, waitFor } from "@testing-library/react";
import { describe, expect, it } from "vitest";
import { renderApp } from "../../test/renderWithProviders";

describe("评估详情 API 集成", () => {
  it("以真实 execution_id 加载决策、规则和后端追溯边", async () => {
    const { container, getByRole } = renderApp("/assessments/exec-case03");
    await waitFor(() => {
      expect(container.textContent).toContain("案例三");
      expect(container.textContent).toContain("不可携转");
    });
    fireEvent.click(getByRole("button", { name: "阻塞原因" }));
    await waitFor(() => expect(container.textContent).toContain("有效合约限制"));
    fireEvent.click(getByRole("button", { name: "追溯图" }));
    await waitFor(() => expect(container.textContent).toContain("2 条边"));
    expect(container.querySelector('[data-testid="trace-graph"]')).toBeInTheDocument();
    expect(container.textContent).not.toContain("exec-case03");
  });

  it("不存在的执行记录显示中文未找到状态", async () => {
    const { container } = renderApp("/assessments/not-present");

    await waitFor(() => expect(container.textContent).toContain("未找到相关评估"));
    expect(container.textContent).toContain("该评估记录不存在或已被移除");
    expect(container.textContent).not.toContain("not-present");
  });
});
