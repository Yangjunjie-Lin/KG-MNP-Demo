import { fireEvent, waitFor } from "@testing-library/react";
import { describe, expect, it } from "vitest";
import { renderApp } from "../../test/renderWithProviders";

describe("本体 API 集成", () => {
  it("只渲染后端返回的节点、边和属性中文标签", async () => {
    const { container, getAllByRole } = renderApp("/ontology");
    await waitFor(() =>
      expect(container.querySelector('[data-testid="ontology-overview-graph"]')).toBeInTheDocument(),
    );
    expect(container.textContent).toContain("业务总览");
    expect(container.textContent).toContain("用户");
    fireEvent.click(getAllByRole("button", { name: "完整本体" })[0]);
    await waitFor(() =>
      expect(container.querySelector('[data-testid="ontology-complete-graph"]')).toBeInTheDocument(),
    );
    await waitFor(() => expect(container.textContent).toMatch(/携转案件|资格评估|订户/));
    expect(container.querySelector("svg")).toBeInTheDocument();
    expect(container.textContent).not.toContain("urn:mnp:case");
  });
});
