import { screen, waitFor, fireEvent } from "@testing-library/react";
import { describe, expect, it } from "vitest";
import { renderApp } from "../../test/renderWithProviders";

describe("导航", () => {
  it("侧边栏可切换到案件与历史、规则与版本", async () => {
    renderApp();
    await waitFor(() => {
      expect(screen.getByText("真实数据统计")).toBeInTheDocument();
    });

    fireEvent.click(screen.getByRole("link", { name: "案件与历史" }));
    await waitFor(() => {
      expect(screen.getByPlaceholderText("搜索案例")).toBeInTheDocument();
    });

    fireEvent.click(screen.getByRole("link", { name: "规则与版本" }));
    await waitFor(() => {
      expect(screen.getByText("规则列表")).toBeInTheDocument();
    });

    fireEvent.click(screen.getByRole("link", { name: "系统状态" }));
    await waitFor(() => {
      expect(screen.getByText("实时监控")).toBeInTheDocument();
    });
  });

  it("评估详情路由保持案件与历史高亮", async () => {
    renderApp("/assessments/exec-case03");

    await waitFor(() => {
      expect(screen.getByText("资格结论")).toBeInTheDocument();
    });
    expect(screen.getByRole("link", { name: "案件与历史" })).toHaveClass("bg-blue-600");
  });
});
