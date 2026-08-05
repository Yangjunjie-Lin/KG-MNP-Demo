import { describe, expect, it } from "vitest";
import { canonicalDiagramConfig } from "../canonicalDiagramConfig";
import { validateCanonicalDiagramGeometry } from "../canonicalGeometry";

describe("canonical diagram geometry", () => {
  it("has no overlaps, node crossings, label intrusions, or canvas violations", () => {
    expect(validateCanonicalDiagramGeometry(canonicalDiagramConfig)).toEqual({
      violations: [],
      edgeThroughNode: 0,
      unexpectedOverlap: 0,
      labelInsideNode: 0,
      nodeOverlap: 0,
      nodeOutsideCanvas: 0,
      sharedBusDuplicate: 0,
      total: 0,
    });
  });
});
