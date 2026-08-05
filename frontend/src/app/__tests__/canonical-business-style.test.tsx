import { waitFor } from "@testing-library/react";
import { describe, expect, it } from "vitest";
import { renderApp } from "../../test/renderWithProviders";

const LAYER_IDS = [
  "USER_IDENTITY",
  "ACCOUNT_BILLING",
  "SERVICE_OFFERING",
  "PORTABILITY_PROCESS",
  "QUALIFICATION_COMPLIANCE",
] as const;

describe("canonical business diagram rendering", () => {
  it("renders the fixed 1664x900 monochrome overview", async () => {
    const { container } = renderApp("/ontology");

    await waitFor(() =>
      expect(
        container.querySelector('[data-testid="ontology-overview-graph"]'),
      ).toBeInTheDocument(),
    );

    const graph = container.querySelector<SVGSVGElement>(
      '[data-testid="ontology-overview-graph"]',
    );
    expect(graph).not.toBeNull();
    expect(graph).toHaveAttribute("viewBox", "0 0 1664 900");
    expect(graph).toHaveAttribute("preserveAspectRatio", "xMidYMid meet");
    expect(graph).toHaveAttribute("data-canonical-canvas-width", "1664");
    expect(graph).toHaveAttribute("data-canonical-canvas-height", "900");
    expect(graph).toHaveAttribute("data-canonical-core-node-count", "27");
    expect(graph).toHaveAttribute("data-canonical-edge-count", "29");

    const layers = LAYER_IDS.map((layerId) =>
      graph?.querySelector<SVGGElement>(
        `[data-testid="ontology-lane-${layerId}"]`,
      ),
    );
    expect(layers).toHaveLength(5);
    for (const layer of layers) {
      expect(layer).not.toBeNull();
      const background = layer?.querySelector(":scope > rect");
      expect(background).toHaveAttribute("fill", "#ffffff");
      expect(background).toHaveAttribute("stroke", "#111111");
      expect(background).toHaveAttribute("stroke-width", "1.5");
      expect(background).toHaveAttribute("rx", "0");
    }

    const nodes = graph?.querySelectorAll<SVGGElement>("[data-role-id]") ?? [];
    expect(nodes).toHaveLength(27);
    for (const node of nodes) {
      expect(node).toHaveAttribute("data-node-background", "#ffffff");
      expect(node).toHaveAttribute("data-node-radius", "0");
      const rect = node.querySelector(":scope > rect");
      expect(rect).toHaveAttribute("fill", "#ffffff");
      expect(rect).toHaveAttribute("rx", "0");
      expect(rect).toHaveAttribute("stroke", "#111111");

      const title = node.querySelector("[data-canonical-node-label]");
      const lines = title?.querySelectorAll(":scope > tspan") ?? [];
      expect(lines).toHaveLength(2);
      expect(lines[0]?.textContent?.trim()).not.toBe("");
      expect(lines[1]?.textContent?.trim()).toMatch(/^\(.+\)$/);
    }

    const safetyCheck = graph?.querySelector<SVGGElement>(
      '[data-role-id="SAFETY_CHECK"]',
    );
    expect(safetyCheck?.querySelector(":scope > rect")).toHaveAttribute(
      "data-node-border-width",
      "3.5",
    );

    const edgePaths =
      graph?.querySelectorAll<SVGPathElement>("[data-canonical-edge-path]") ?? [];
    expect(edgePaths).toHaveLength(29);
    for (const edgePath of edgePaths) {
      expect(edgePath).toHaveAttribute("stroke", "#111111");
      expect(edgePath).toHaveAttribute("fill", "none");
    }

    expect(graph?.querySelectorAll("[data-canonical-bus]")).toHaveLength(1);
    expect(graph?.querySelectorAll("[data-canonical-bus-trunk]")).toHaveLength(1);
    expect(graph?.querySelectorAll("[data-canonical-marker]")).toHaveLength(1);
    expect(graph?.querySelectorAll("line")).toHaveLength(0);
    expect(graph?.querySelectorAll("linearGradient, radialGradient")).toHaveLength(0);
    expect(graph?.querySelectorAll("filter, [filter]")).toHaveLength(0);
  });
});
