import { fireEvent, waitFor } from "@testing-library/react";
import { describe, expect, it } from "vitest";
import { renderApp } from "../../test/renderWithProviders";

describe("能力问题 API 集成", () => {
  it("执行后端能力问题并按响应列生成中文表头", async () => {
    const { container, findByRole } = renderApp("/competency-questions");
    fireEvent.click(await findByRole("button", { name: "执行查询" }));
    await waitFor(() => expect(container.querySelector('[data-testid="competency-result"]')).toBeInTheDocument());
    expect(container.textContent).toContain("案例");
    expect(container.textContent).toContain("资格结论");
    expect(container.textContent).not.toContain("BLOCKED");
  });
});
