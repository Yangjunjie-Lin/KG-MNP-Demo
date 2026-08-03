import { render, waitFor, fireEvent, screen } from "@testing-library/react";
import { describe, expect, it } from "vitest";
import { AssessmentResult } from "../pages/AssessmentResult";
import { findForbiddenVisibleText } from "../i18n/forbiddenVisibleTokens";

describe("案例六", () => {
  it("展示历史可携转与当前不可携转，且无原始编号泄漏", async () => {
    const { container } = render(
      <AssessmentResult caseId="CASE-06" onBack={() => undefined} />,
    );

    await waitFor(() => {
      expect(container.textContent).toContain("案例六");
      expect(container.textContent).toContain("历史规则版本");
      expect(container.textContent).toContain("120 天");
      expect(container.textContent).toContain("可携转");
      expect(container.textContent).toContain("当前规则版本");
      expect(container.textContent).toContain("180 天");
      expect(container.textContent).toContain("不可携转");
    });

    const hits = findForbiddenVisibleText(container.textContent ?? "");
    expect(hits).toEqual([]);
    expect(container.textContent).not.toContain("CASE-06");
    expect(container.textContent).not.toContain("MNP-ELIG-005");
    expect(container.textContent).not.toContain("EXEC-CASE-06-HIST");
    expect(container.textContent).not.toContain("REG-MNP-CLAUSE-05");

    fireEvent.click(screen.getByRole("button", { name: "追溯图" }));
    await waitFor(() => {
      expect(container.textContent).toMatch(/监管条款|阻塞|规则/);
    });
    expect(findForbiddenVisibleText(container.textContent ?? "")).toEqual([]);
  });
});
