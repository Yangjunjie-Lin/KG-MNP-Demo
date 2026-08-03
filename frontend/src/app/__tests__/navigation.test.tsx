import { render, screen, waitFor, fireEvent } from "@testing-library/react";
import { describe, expect, it } from "vitest";
import App from "../App";

describe("导航", () => {
  it("侧边栏可切换到案件与历史、规则与版本", async () => {
    render(<App />);
    await waitFor(() => {
      expect(screen.getByText("系统总览")).toBeInTheDocument();
    });

    fireEvent.click(screen.getByRole("button", { name: "案件与历史" }));
    await waitFor(() => {
      expect(screen.getByPlaceholderText("搜索案例…")).toBeInTheDocument();
    });

    fireEvent.click(screen.getByRole("button", { name: "规则与版本" }));
    await waitFor(() => {
      expect(screen.getByText("规则列表")).toBeInTheDocument();
    });

    fireEvent.click(screen.getByRole("button", { name: "系统状态" }));
    await waitFor(() => {
      expect(screen.getByText("实时监控")).toBeInTheDocument();
    });
  });
});
