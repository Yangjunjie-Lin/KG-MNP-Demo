import { fireEvent, waitFor } from "@testing-library/react";
import { describe, expect, it } from "vitest";
import { renderApp } from "../../test/renderWithProviders";

describe("本体浏览器交互", () => {
  it("默认显示五层总览且不出现全部模块按钮", async () => {
    const { container, getAllByRole, queryByText } = renderApp("/ontology");
    await waitFor(() =>
      expect(container.querySelector('[data-testid="ontology-overview-graph"]')).toBeInTheDocument(),
    );

    expect(getAllByRole("button", { name: "总览图" }).length).toBeGreaterThan(0);
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

  it("切换用户与身份层后只保留该层节点", async () => {
    const { container, getAllByRole } = renderApp("/ontology");
    await waitFor(() =>
      expect(container.querySelector('[data-testid="ontology-overview-graph"]')).toBeInTheDocument(),
    );
    fireEvent.click(getAllByRole("button", { name: "用户与身份层" })[0]);
    await waitFor(() =>
      expect(container.querySelector('[data-testid="ontology-node-Subscriber"]')).toBeInTheDocument(),
    );
    expect(container.querySelector('[data-testid="ontology-node-BillingAccount"]')).not.toBeInTheDocument();
    expect(container.querySelector('[data-testid="ontology-node-MobilePlan"]')).not.toBeInTheDocument();
  });

  it("点击节点高亮相邻关系，清除后恢复", async () => {
    const { container } = renderApp("/ontology");
    await waitFor(() =>
      expect(container.querySelector('[data-testid="ontology-node-RealNameRegistration"]')).toBeInTheDocument(),
    );
    const node = container.querySelector('[data-testid="ontology-node-RealNameRegistration"]');
    expect(node).toBeTruthy();
    fireEvent.click(node!);
    await waitFor(() =>
      expect(container.querySelector('[data-testid="ontology-node-details"]')?.textContent).toContain(
        "实名登记",
      ),
    );
    expect(container.querySelector('[data-testid="ontology-node-details"]')?.textContent).toMatch(
      /直接出边数量|直接入边数量/,
    );
    fireEvent.click(node!);
    await waitFor(() =>
      expect(container.querySelector('[data-testid="ontology-node-details"]')?.textContent).toContain(
        "点击图中节点查看本体类详情",
      ),
    );
  });

  it("搜索不改变节点坐标，且正式界面不显示技术标识", async () => {
    const { container, getByPlaceholderText } = renderApp("/ontology");
    await waitFor(() =>
      expect(container.querySelector('[data-testid="ontology-node-Subscriber"]')).toBeInTheDocument(),
    );
    const before = container
      .querySelector('[data-testid="ontology-node-Subscriber"] rect')
      ?.getAttribute("x");
    fireEvent.change(getByPlaceholderText("搜索本体概念…"), {
      target: { value: "订户" },
    });
    const after = container
      .querySelector('[data-testid="ontology-node-Subscriber"] rect')
      ?.getAttribute("x");
    expect(after).toBe(before);
    expect(container.textContent).not.toContain("IDENTITY");
    expect(container.textContent).not.toContain("urn:mnp:");
    expect(container.textContent).not.toContain("localName");
  });
});
