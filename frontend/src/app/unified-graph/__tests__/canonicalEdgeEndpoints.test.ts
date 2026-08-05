import { describe, expect, it } from "vitest";
import { canonicalDiagramConfig } from "../canonicalDiagramConfig";
import {
  validateCanonicalEdgeEndpoints,
  type CanonicalEdgeEndpointValidation,
} from "../canonicalEdgeEndpoints";
import { canonicalPathEndpoints } from "../canonicalPath";

function resultFor(
  edgeId: string,
  results: CanonicalEdgeEndpointValidation[],
): CanonicalEdgeEndpointValidation {
  const result = results.find((item) => item.edgeId === edgeId);
  if (!result) throw new Error(`Missing endpoint result for ${edgeId}`);
  return result;
}

describe("canonical edge endpoints", () => {
  const results = validateCanonicalEdgeEndpoints({
    edges: canonicalDiagramConfig.edges,
    nodes: canonicalDiagramConfig.nodes,
    buses: canonicalDiagramConfig.buses,
    tolerance: 2,
  });

  it("connects both ends of every canonical structural edge", () => {
    expect(results).toHaveLength(canonicalDiagramConfig.edges.length);
    const disconnectedSources = results.filter((item) => !item.sourceConnected);
    const disconnectedTargets = results.filter((item) => !item.targetConnected);
    expect(disconnectedSources, JSON.stringify(disconnectedSources)).toEqual([]);
    expect(disconnectedTargets, JSON.stringify(disconnectedTargets)).toEqual([]);
    expect(results.every((item) => item.sourceDistance <= 2)).toBe(true);
    expect(results.every((item) => item.targetDistance <= 2)).toBe(true);
  });

  it("keeps the user-to-port-request submit edge connected at both explicit ports", () => {
    const edge = canonicalDiagramConfig.edges.find(
      (item) => item.id === "struct-user-port",
    );
    expect(edge).toBeDefined();
    if (!edge) return;
    const endpoints = canonicalPathEndpoints(edge.path);
    expect(endpoints.start).toEqual({ x: 302, y: 114 });
    expect(endpoints.end).toEqual({ x: 333, y: 558 });
    const result = resultFor("struct-user-port", results);
    expect(result.sourceConnected).toBe(true);
    expect(result.targetConnected).toBe(true);
    expect(result.sourceDistance).toBeLessThanOrEqual(2);
    expect(result.targetDistance).toBeLessThanOrEqual(2);
  });

  it("treats service branches as connected through the single shared bus", () => {
    for (const edge of canonicalDiagramConfig.edges.filter((item) => item.busId)) {
      const result = resultFor(edge.id, results);
      expect(result.sourceConnected, `${edge.id}: ${result.sourceDistance}`).toBe(true);
      expect(result.targetConnected, edge.id).toBe(true);
    }
  });

  it("reports a path whose source is off-node instead of inferring adjacency", () => {
    const original = canonicalDiagramConfig.edges.find(
      (item) => item.id === "struct-user-port",
    );
    expect(original).toBeDefined();
    if (!original) return;
    const broken = {
      ...original,
      path: "M 0 0 H 278 V 558 H 333",
    };
    const [result] = validateCanonicalEdgeEndpoints({
      edges: [broken],
      nodes: canonicalDiagramConfig.nodes,
      buses: canonicalDiagramConfig.buses,
      tolerance: 2,
    });
    expect(result.sourceConnected).toBe(false);
    expect(result.targetConnected).toBe(true);
    expect(result.sourceDistance).toBeGreaterThan(2);
  });

  it("rejects two disconnected subpaths even when their endpoints touch nodes", () => {
    const original = canonicalDiagramConfig.edges.find(
      (item) => item.id === "struct-user-verification",
    );
    expect(original).toBeDefined();
    if (!original) return;
    const disconnected = {
      ...original,
      path: "M 386 78 H 450 M 500 78 H 610",
    };
    const [result] = validateCanonicalEdgeEndpoints({
      edges: [disconnected],
      nodes: canonicalDiagramConfig.nodes,
      tolerance: 2,
    });
    expect(result.sourceConnected).toBe(false);
    expect(result.targetConnected).toBe(false);
  });
});
