import type { Point } from "./graphTypes";

export type CanonicalPathCommand =
  | { command: "M"; x: number; y: number }
  | { command: "H"; x: number }
  | { command: "V"; y: number };

export interface CanonicalPathValidationResult {
  valid: boolean;
  errors: string[];
}

interface LexedCommandToken {
  kind: "command";
  value: string;
  index: number;
}

interface LexedNumberToken {
  kind: "number";
  value: number;
  raw: string;
  index: number;
}

type LexedToken = LexedCommandToken | LexedNumberToken;

interface LexResult {
  tokens: LexedToken[];
  errors: string[];
}

const PATH_TOKEN =
  /[A-Za-z]|[-+]?(?:(?:\d+\.\d*)|(?:\.\d+)|(?:\d+))(?:[eE][-+]?\d+)?/g;
const SEPARATOR = /^[\s,]*$/;

function lexPath(path: string): LexResult {
  const tokens: LexedToken[] = [];
  const errors: string[] = [];
  let consumedUntil = 0;

  PATH_TOKEN.lastIndex = 0;
  for (let match = PATH_TOKEN.exec(path); match; match = PATH_TOKEN.exec(path)) {
    const gap = path.slice(consumedUntil, match.index);
    if (!SEPARATOR.test(gap)) {
      errors.push(`Invalid path token at index ${consumedUntil}: ${gap.trim()}`);
    }

    const raw = match[0];
    if (/^[A-Za-z]$/.test(raw)) {
      tokens.push({ kind: "command", value: raw, index: match.index });
    } else {
      const value = Number(raw);
      if (!Number.isFinite(value)) {
        errors.push(`Coordinate at index ${match.index} is not finite: ${raw}`);
      }
      tokens.push({ kind: "number", value, raw, index: match.index });
    }
    consumedUntil = PATH_TOKEN.lastIndex;
  }

  const trailing = path.slice(consumedUntil);
  if (!SEPARATOR.test(trailing)) {
    errors.push(`Invalid path token at index ${consumedUntil}: ${trailing.trim()}`);
  }
  if (!path.trim()) errors.push("Path is empty");

  return { tokens, errors };
}

function parsePath(path: string): {
  commands: CanonicalPathCommand[];
  errors: string[];
} {
  const { tokens, errors } = lexPath(path);
  const commands: CanonicalPathCommand[] = [];
  let cursor = 0;

  while (cursor < tokens.length) {
    const token = tokens[cursor];
    if (token.kind !== "command") {
      errors.push(
        `Expected M, H, or V at index ${token.index}; found coordinate ${token.raw}`,
      );
      cursor += 1;
      continue;
    }

    if (token.value !== "M" && token.value !== "H" && token.value !== "V") {
      errors.push(
        `Unsupported path command ${token.value} at index ${token.index}; only M, H, and V are allowed`,
      );
      cursor += 1;
      while (cursor < tokens.length && tokens[cursor].kind === "number") {
        cursor += 1;
      }
      continue;
    }

    const arity = token.value === "M" ? 2 : 1;
    const operands = tokens.slice(cursor + 1, cursor + 1 + arity);
    if (
      operands.length !== arity ||
      operands.some((operand) => operand.kind !== "number")
    ) {
      errors.push(
        `Command ${token.value} at index ${token.index} requires ${arity} numeric ${
          arity === 1 ? "operand" : "operands"
        }`,
      );
      cursor += 1;
      continue;
    }

    const values = operands as LexedNumberToken[];
    if (token.value === "M") {
      commands.push({ command: "M", x: values[0].value, y: values[1].value });
    } else if (token.value === "H") {
      commands.push({ command: "H", x: values[0].value });
    } else {
      commands.push({ command: "V", y: values[0].value });
    }
    cursor += arity + 1;
  }

  if (commands.length > 0 && commands[0].command !== "M") {
    errors.push("Canonical path must start with M");
  }
  if (commands.length === 0 && errors.length === 0) {
    errors.push("Path contains no commands");
  }

  return { commands, errors };
}

export function validatePathCommands(
  path: string,
): CanonicalPathValidationResult {
  const { errors } = parsePath(path);
  return { valid: errors.length === 0, errors };
}

export function parseCanonicalPath(path: string): CanonicalPathCommand[] {
  const { commands, errors } = parsePath(path);
  if (errors.length > 0) {
    throw new Error(`Invalid canonical path: ${errors.join("; ")}`);
  }
  return commands;
}

function pointsEqual(a: Point, b: Point): boolean {
  return a.x === b.x && a.y === b.y;
}

function areCollinear(a: Point, b: Point, c: Point): boolean {
  return (a.x === b.x && b.x === c.x) || (a.y === b.y && b.y === c.y);
}

function appendSimplifiedPoint(points: Point[], point: Point): void {
  for (let index = points.length - 1; index >= 0; index -= 1) {
    if (!pointsEqual(points[index], point)) continue;
    points.splice(index + 1);
    return;
  }

  if (points.length >= 2) {
    const before = points[points.length - 2];
    const current = points[points.length - 1];
    if (areCollinear(before, current, point)) {
      points[points.length - 1] = point;
      return;
    }
  }

  points.push(point);
}

export function canonicalPathSubpaths(path: string): Point[][] {
  const commands = parseCanonicalPath(path);
  const subpaths: Point[][] = [];
  let current: Point | null = null;
  let active: Point[] | null = null;

  for (const command of commands) {
    if (command.command === "M") {
      current = { x: command.x, y: command.y };
      active = [current];
      subpaths.push(active);
      continue;
    }
    if (!current || !active) {
      throw new Error("Invalid canonical path: drawing command appears before M");
    }

    const next =
      command.command === "H"
        ? { x: command.x, y: current.y }
        : { x: current.x, y: command.y };
    appendSimplifiedPoint(active, next);
    current = active[active.length - 1];
  }

  return subpaths;
}

function formatCoordinate(value: number): string {
  const normalized = Object.is(value, -0) ? 0 : value;
  return Number(normalized.toFixed(12)).toString();
}

export function normalizeCanonicalPath(path: string): string {
  const normalizedCommands: string[] = [];
  for (const points of canonicalPathSubpaths(path)) {
    if (points.length === 0) continue;
    normalizedCommands.push(
      `M ${formatCoordinate(points[0].x)} ${formatCoordinate(points[0].y)}`,
    );
    for (let index = 1; index < points.length; index += 1) {
      const previous = points[index - 1];
      const point = points[index];
      normalizedCommands.push(
        previous.y === point.y
          ? `H ${formatCoordinate(point.x)}`
          : `V ${formatCoordinate(point.y)}`,
      );
    }
  }
  return normalizedCommands.join(" ");
}

export function countPathBends(path: string): number {
  let bends = 0;
  for (const points of canonicalPathSubpaths(path)) {
    let previousDirection: "H" | "V" | null = null;
    for (let index = 1; index < points.length; index += 1) {
      const direction = points[index - 1].y === points[index].y ? "H" : "V";
      if (previousDirection && previousDirection !== direction) bends += 1;
      previousDirection = direction;
    }
  }
  return bends;
}

export function canonicalPathEndpoints(path: string): {
  start: Point;
  end: Point;
} {
  const subpaths = canonicalPathSubpaths(path);
  const first = subpaths[0]?.[0];
  const lastSubpath = subpaths[subpaths.length - 1];
  const last = lastSubpath?.[lastSubpath.length - 1];
  if (!first || !last) {
    throw new Error("Invalid canonical path: no path endpoints");
  }
  return { start: { ...first }, end: { ...last } };
}
