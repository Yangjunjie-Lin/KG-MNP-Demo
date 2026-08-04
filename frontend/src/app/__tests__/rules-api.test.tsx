import { waitFor } from "@testing-library/react";
import { describe, expect, it } from "vitest";
import { renderApp } from "../../test/renderWithProviders";

describe("规则版本 API 集成", () => {
  it("消费后端规则版本和受影响评估查询", async () => {
    const { container } = renderApp("/rules");
    await waitFor(() => {
      expect(container.textContent).toContain("120 天");
      expect(container.textContent).toContain("180 天");
      expect(container.textContent).toContain("案例六");
    });
    expect(container.textContent).toContain("需要重新评估");
    expect(container.textContent).not.toContain("MNP-ELIG-005");
  });
});
