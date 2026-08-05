import { describe, expect, it } from "vitest";
import {
  canonicalPathEndpoints,
  countPathBends,
  normalizeCanonicalPath,
  parseCanonicalPath,
  validatePathCommands,
} from "../canonicalPath";

describe("canonicalPath", () => {
  it("parses the canonical M/H/V command subset", () => {
    expect(parseCanonicalPath("M 10 20 H 30 V 40 H -2.5")).toEqual([
      { command: "M", x: 10, y: 20 },
      { command: "H", x: 30 },
      { command: "V", y: 40 },
      { command: "H", x: -2.5 },
    ]);
  });

  it.each(["L", "C", "Q", "S", "T", "A"])(
    "rejects forbidden %s commands",
    (command) => {
      const result = validatePathCommands(`M 0 0 ${command} 10 10`);
      expect(result.valid).toBe(false);
      expect(result.errors.join(" ")).toContain(`Unsupported path command ${command}`);
      expect(() => parseCanonicalPath(`M 0 0 ${command} 10 10`)).toThrow();
    },
  );

  it("rejects lowercase, malformed, and non-M-leading paths", () => {
    expect(validatePathCommands("m 0 0 h 10").valid).toBe(false);
    expect(validatePathCommands("M 0 H 10").valid).toBe(false);
    expect(validatePathCommands("H 10").valid).toBe(false);
    expect(validatePathCommands("M 0 0 X! 10").valid).toBe(false);
  });

  it("merges continuous directions and removes zero-length segments", () => {
    expect(
      normalizeCanonicalPath(
        "M 100 100 H 120 H 160 H 160 V 100 V 130 V 130",
      ),
    ).toBe("M 100 100 H 160 V 130");
  });

  it("removes immediate backtracks and loops returning to an earlier point", () => {
    expect(normalizeCanonicalPath("M 0 0 H 20 H 0 V 10")).toBe(
      "M 0 0 V 10",
    );
    expect(
      normalizeCanonicalPath("M 0 0 H 10 V 10 H 0 V 0 H 20"),
    ).toBe("M 0 0 H 20");
  });

  it("counts only normalized H/V direction changes", () => {
    expect(countPathBends("M 0 0 H 10 H 20")).toBe(0);
    expect(countPathBends("M 0 0 H 10 V 10")).toBe(1);
    expect(countPathBends("M 0 0 H 10 V 10 H 20 V 20")).toBe(3);
    expect(countPathBends("M 0 0 H 10 H 0 V 20")).toBe(0);
  });

  it("returns the normalized first and final endpoints", () => {
    expect(canonicalPathEndpoints("M 10 20 H 40 V 50")).toEqual({
      start: { x: 10, y: 20 },
      end: { x: 40, y: 50 },
    });
  });
});
