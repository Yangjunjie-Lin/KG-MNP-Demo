import { describe, expect, it } from "vitest";
import {
  CANONICAL_BUSES,
  CANONICAL_CANVAS,
  CANONICAL_EDGES,
  CANONICAL_LAYERS,
  CANONICAL_MARKERS,
  CANONICAL_NODES,
  CANONICAL_STYLE,
  canonicalDiagramConfig,
} from "../canonicalDiagramConfig";
import { countPathBends, normalizeCanonicalPath, validatePathCommands } from "../canonicalPath";

const expectedLayerGeometry = {
  USER_IDENTITY: [8, 10, 1648, 180],
  ACCOUNT_BILLING: [8, 208, 1648, 114],
  SERVICE_OFFERING: [8, 338, 1648, 122],
  PORTABILITY_PROCESS: [8, 475, 1648, 160],
  QUALIFICATION_COMPLIANCE: [8, 652, 1648, 235],
} as const;

const expectedNodeGeometry = {
  USER: [266, 42, 120, 72],
  VERIFICATION: [610, 42, 198, 72],
  MOBILE_NUMBER_IDENTITY: [969, 42, 195, 72],
  OPERATOR_CURRENT: [1378, 43, 157, 72],
  ACCOUNT: [409, 241, 157, 62],
  BILL: [799, 241, 177, 62],
  PAYMENT: [1275, 241, 157, 62],
  TARIFF_PLAN: [290, 379, 153, 62],
  CONTRACT: [535, 379, 153, 62],
  BROADBAND: [806, 379, 153, 62],
  VALUE_ADDED_SERVICE: [1067, 379, 191, 62],
  USER_RIGHT: [1381, 379, 151, 62],
  PORT_REQUEST: [333, 527, 139, 61],
  MOBILE_NUMBER_PORT: [640, 482, 160, 48],
  OPERATOR_DONOR: [640, 532, 168, 52],
  OPERATOR_RECIPIENT: [640, 584, 168, 52],
  PORT_STEP: [887, 529, 139, 58],
  AUTH_CODE: [1100, 529, 120, 58],
  EXCEPTION_EVENT: [1301, 529, 142, 58],
  IMPACT: [1512, 529, 103, 58],
  ELIGIBILITY_CONDITION: [287, 673, 180, 67],
  REGULATION_RULE: [286, 796, 180, 62],
  SAFETY_CHECK: [630, 672, 247, 99],
  BLOCK_REASON: [1050, 674, 175, 64],
  REMEDIATION_ACTION: [1375, 674, 205, 64],
  EVIDENCE: [1050, 796, 179, 61],
  OPERATOR_EVIDENCE: [1380, 796, 176, 61],
} as const;

describe("canonical business diagram configuration", () => {
  it("uses the fixed 1664 x 900 canvas and canonical identity", () => {
    expect(canonicalDiagramConfig.version).toBe("2.0");
    expect(canonicalDiagramConfig.view_id).toBe(
      "KG_MNP_CANONICAL_BUSINESS_DIAGRAM",
    );
    expect(CANONICAL_CANVAS).toEqual({
      width: 1664,
      height: 900,
      view_box: "0 0 1664 900",
      preserve_aspect_ratio: "xMidYMid meet",
    });
  });

  it("contains the five fixed layers and exact layer geometry", () => {
    expect(CANONICAL_LAYERS).toHaveLength(5);
    for (const layer of CANONICAL_LAYERS) {
      expect([
        layer.x,
        layer.y,
        layer.width,
        layer.height,
      ]).toEqual(expectedLayerGeometry[layer.id]);
      expect(layer.titleArea).toEqual({ x: 8, width: 214 });
      expect(layer.contentX).toBe(222);
      expect(layer.subtitleLines.length).toBe(2);
    }
  });

  it("contains all 27 core nodes at their reference positions", () => {
    expect(CANONICAL_NODES).toHaveLength(27);
    expect(new Set(CANONICAL_NODES.map((node) => node.id)).size).toBe(27);
    for (const node of CANONICAL_NODES) {
      const geometry = expectedNodeGeometry[node.id];
      expect(geometry).toBeDefined();
      expect([node.x, node.y, node.width, node.height]).toEqual(geometry);
      expect(node.labelZh).toBeTruthy();
      expect(node.labelEn).toBeTruthy();
      expect(node.styleKey).toMatch(/^(ordinary|safety_check)$/);
    }
    expect(CANONICAL_NODES.find((node) => node.id === "SAFETY_CHECK")?.styleKey).toBe(
      "safety_check",
    );
  });

  it("locks the monochrome style and safety-check emphasis", () => {
    expect(CANONICAL_STYLE.canvas_background).toBe("#ffffff");
    expect(CANONICAL_STYLE.layer_background).toBe("#ffffff");
    expect(CANONICAL_STYLE.layer_border).toBe("#111111");
    expect(CANONICAL_STYLE.node_background).toBe("#ffffff");
    expect(CANONICAL_STYLE.node_border).toBe("#111111");
    expect(CANONICAL_STYLE.edge).toBe("#111111");
    expect(CANONICAL_STYLE.node_radius).toBe(0);
    expect(CANONICAL_STYLE.shadow).toBe("none");
    expect(CANONICAL_STYLE.gradient).toBe("none");
    expect(CANONICAL_STYLE.safety_check.node_border_width).toBe(3.5);
    expect(CANONICAL_STYLE.safety_check.font_weight).toBe(700);
  });

  it("uses only canonical path commands and declared bend budgets", () => {
    expect(CANONICAL_EDGES).toHaveLength(29);
    for (const edge of CANONICAL_EDGES) {
      const validation = validatePathCommands(edge.path);
      expect(validation.valid, `${edge.id}: ${validation.errors.join(" ")}`).toBe(
        true,
      );
      expect(normalizeCanonicalPath(edge.path)).toBe(edge.path);
      expect(countPathBends(edge.path)).toBeLessThanOrEqual(edge.bendCount);
      expect(countPathBends(edge.path)).toBeLessThanOrEqual(3);
    }

    for (const edgeId of [
      "struct-user-verification",
      "struct-verification-number",
      "struct-number-operator-service",
      "struct-number-operator-alloc",
      "struct-account-bill",
      "struct-bill-payment",
      "struct-port-donor",
      "struct-donor-step",
      "struct-step-auth",
      "struct-auth-exception",
      "struct-exception-impact",
      "struct-safety-condition",
      "struct-safety-block",
      "struct-block-remediation",
      "struct-block-evidence",
      "struct-evidence-operator",
    ]) {
      expect(CANONICAL_EDGES.find((edge) => edge.id === edgeId)?.bendCount).toBe(0);
    }
  });

  it("renders one shared service bus and the primary/secondary marker", () => {
    expect(CANONICAL_BUSES).toHaveLength(1);
    expect(CANONICAL_BUSES[0].id).toBe("service-offering-bus");
    expect(CANONICAL_BUSES[0].path).toBe(
      "M 1066 114 V 350 H 366 M 366 350 H 1456",
    );
    expect(validatePathCommands(CANONICAL_BUSES[0].path).valid).toBe(true);
    expect(normalizeCanonicalPath(CANONICAL_BUSES[0].path)).toBe(
      CANONICAL_BUSES[0].path,
    );
    expect(countPathBends(CANONICAL_BUSES[0].path)).toBeLessThanOrEqual(
      CANONICAL_BUSES[0].bendCount,
    );
    expect(CANONICAL_BUSES[0].edgeIds).toHaveLength(5);
    expect(CANONICAL_EDGES.filter((edge) => edge.busId)).toHaveLength(5);
    expect(CANONICAL_MARKERS).toHaveLength(1);
    expect(CANONICAL_MARKERS[0].rect).toEqual({
      x: 1045,
      y: 126,
      width: 48,
      height: 42,
    });
    expect(CANONICAL_MARKERS[0].arrows).toHaveLength(2);
    for (const arrow of CANONICAL_MARKERS[0].arrows) {
      expect(validatePathCommands(arrow.path).valid).toBe(true);
      expect(countPathBends(arrow.path)).toBe(0);
    }
  });
});
