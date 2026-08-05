import { fireEvent, waitFor } from "@testing-library/react";
import { describe, expect, it } from "vitest";
import { renderApp } from "../../test/renderWithProviders";

describe("本体浏览器交互", () => {
  it("默认显示五层业务总览", async () => {
    const { container, getAllByRole, queryByText } = renderApp("/ontology");
    await waitFor(() =>
      expect(container.querySelector('[data-testid="ontology-overview-graph"]')).toBeInTheDocument(),
    );

    expect(getAllByRole("button", { name: "业务总览" }).length).toBeGreaterThan(0);
    expect(queryByText("全部模块")).not.toBeInTheDocument();
    expect(container.querySelector('[data-testid="ontology-lane-USER_IDENTITY"]')).toBeInTheDocument();
    expect(container.querySelector('[data-testid="ontology-lane-ACCOUNT_BILLING"]')).toBeInTheDocument();
    expect(container.querySelector('[data-testid="ontology-lane-SERVICE_OFFERING"]')).toBeInTheDocument();
    expect(container.querySelector('[data-testid="ontology-lane-PORTABILITY_PROCESS"]')).toBeInTheDocument();
    expect(container.querySelector('[data-testid="ontology-lane-QUALIFICATION_COMPLIANCE"]')).toBeInTheDocument();
    expect(
      container.querySelectorAll('[data-testid="ontology-overview-graph"] line'),
    ).toHaveLength(0);

    const graph = container.querySelector(
      '[data-testid="ontology-overview-graph"]',
    );
    expect(graph).toHaveAttribute("data-geometry-violation-count", "0");
    expect(graph).toHaveAttribute("data-unmapped-node-count", "0");
  });

  it("切换完整本体后仍保持五层结构", async () => {
    const { container, getAllByRole } = renderApp("/ontology");
    await waitFor(() =>
      expect(container.querySelector('[data-testid="ontology-overview-graph"]')).toBeInTheDocument(),
    );
    fireEvent.click(getAllByRole("button", { name: "完整本体" })[0]);
    await waitFor(() =>
      expect(container.querySelector('[data-testid="ontology-complete-graph"]')).toBeInTheDocument(),
    );
    expect(container.querySelector('[data-testid="ontology-lane-USER_IDENTITY"]')).toBeInTheDocument();
  });

  it("点击核心角色显示详情", async () => {
    const { container } = renderApp("/ontology");
    await waitFor(() =>
      expect(container.querySelector('[data-role-id="USER"]')).toBeInTheDocument(),
    );
    const node = container.querySelector('[data-role-id="USER"]');
    expect(node).toBeTruthy();
    fireEvent.click(node!);
    await waitFor(() =>
      expect(container.querySelector('[data-testid="graph-node-details"]')?.textContent).toContain(
        "用户",
      ),
    );
  });

  it("搜索不改变节点世界坐标", async () => {
    const { container, getByPlaceholderText } = renderApp("/ontology");
    await waitFor(() =>
      expect(container.querySelector('[data-role-id="USER"]')).toBeInTheDocument(),
    );
    const before = container
      .querySelector('[data-role-id="USER"]')
      ?.getAttribute("data-node-x");
    fireEvent.change(getByPlaceholderText("搜索业务概念"), {
      target: { value: "用户" },
    });
    const after = container
      .querySelector('[data-role-id="USER"]')
      ?.getAttribute("data-node-x");
    expect(after).toBe(before);
    expect(container.textContent).not.toContain("urn:mnp:");
    expect(container.textContent).not.toContain("localName");
  });
});
