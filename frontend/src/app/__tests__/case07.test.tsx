import { waitFor, fireEvent, screen } from "@testing-library/react";
import { describe, expect, it } from "vitest";
import { findForbiddenVisibleText } from "../i18n/forbiddenVisibleTokens";
import { renderApp } from "../../test/renderWithProviders";

describe("案例七", () => {
  it("区分资格结论可携转与流程不能继续", async () => {
    const { container } = renderApp("/assessments/exec-case07");

    await waitFor(() => {
      expect(container.textContent).toContain("案例七");
      expect(container.textContent).toContain("资格结论");
      expect(container.textContent).toContain("可携转");
      expect(container.textContent).toContain("授权码已过期");
      expect(container.textContent).toContain("不能继续");
    });

    fireEvent.click(screen.getByRole("button", { name: "流程状态" }));
    await waitFor(() => {
      expect(container.textContent).toContain("资格结论为可携转");
      expect(container.textContent).toContain("授权码已过期");
      expect(container.textContent).toContain("不能继续");
    });

    expect(findForbiddenVisibleText(container.textContent ?? "")).toEqual([]);
    expect(container.textContent).not.toContain("CASE-07");
    expect(container.textContent).not.toContain("ELIGIBLE");
    expect(container.textContent).not.toContain("AUTHORIZATION_CODE_EXPIRED");
  });
});
