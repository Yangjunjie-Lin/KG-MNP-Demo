import { waitFor } from "@testing-library/react";
import { describe, expect, it } from "vitest";
import { renderApp } from "../../test/renderWithProviders";

describe("本体 API 集成", () => {
  it("只渲染后端返回的节点、边和属性中文标签", async () => {
    const { container } = renderApp("/ontology");
    await waitFor(() => expect(container.textContent).toContain("携转案例"));
    expect(container.textContent).toContain("资格评估");
    expect(container.textContent).toContain("关联评估");
    expect(container.querySelector("svg")).toBeInTheDocument();
    expect(container.textContent).not.toContain("urn:mnp:case");
  });
});
