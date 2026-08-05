import { wrapNodeLabel } from "../../unified-graph/graphLabels";
import { LAYER_STYLES } from "../../unified-graph/businessLayerConfig";
import type { VisualProjection } from "../../unified-graph/graphTypes";

const STATE_STROKE: Record<string, string> = {
  DEFAULT: "#64748b",
  ACTIVE: "#2563eb",
  PASS: "#16a34a",
  BLOCK: "#dc2626",
  WARN: "#ea580c",
  CURRENT: "#2563eb",
  DIMMED: "#94a3b8",
  ADDED: "#0d9488",
  MODIFIED: "#ca8a04",
  CONFLICT: "#e11d48",
};

const STATE_FILL: Record<string, string> = {
  DEFAULT: "#ffffff",
  ACTIVE: "#dbeafe",
  PASS: "#dcfce7",
  BLOCK: "#fee2e2",
  WARN: "#ffedd5",
  CURRENT: "#dbeafe",
  DIMMED: "#f8fafc",
  ADDED: "#ccfbf1",
  MODIFIED: "#fef9c3",
  CONFLICT: "#ffe4e6",
};

interface BusinessRoleNodeProps {
  node: VisualProjection;
  selected: boolean;
  opacity: number;
  onSelect: (projectionId: string) => void;
}

export function BusinessRoleNode({
  node,
  selected,
  opacity,
  onSelect,
}: BusinessRoleNodeProps) {
  const style = LAYER_STYLES[node.layerId];
  const state = node.state ?? "DEFAULT";
  const lines = wrapNodeLabel(node.labelZh, node.width > 160 ? 10 : 8);
  const stroke = selected ? "#2563eb" : STATE_STROKE[state] ?? style.accent;
  const fill = selected ? "#dbeafe" : STATE_FILL[state] ?? "#ffffff";

  return (
    <g
      data-testid={`graph-node-${node.projectionId}`}
      data-projection-id={node.projectionId}
      data-source-node-id={node.sourceNodeId}
      data-role-id={node.roleId ?? ""}
      data-node-x={node.x}
      data-node-y={node.y}
      data-node-kind={node.kind}
      opacity={opacity}
      style={{ cursor: "pointer" }}
      onClick={(event) => {
        event.stopPropagation();
        onSelect(node.projectionId);
      }}
      onPointerDown={(event) => {
        // Prevent canvas pan when interacting with nodes.
        event.stopPropagation();
      }}
    >
      <rect
        x={node.x}
        y={node.y}
        width={node.width}
        height={node.height}
        rx={6}
        fill={fill}
        stroke={stroke}
        strokeWidth={selected ? 2.5 : 1.5}
        vectorEffect="non-scaling-stroke"
      />
      {lines.map((line, index) => (
        <text
          key={`${node.projectionId}-line-${index}`}
          x={node.x + node.width / 2}
          y={
            node.y +
            node.height / 2 -
            ((lines.length - 1) * 7) / 2 +
            index * 14
          }
          textAnchor="middle"
          dominantBaseline="middle"
          fontSize={11}
          fill="#334155"
        >
          {line}
        </text>
      ))}
      {typeof node.mappedCount === "number" && node.kind === "CORE_ROLE" ? (
        <text
          x={node.x + node.width - 8}
          y={node.y + 12}
          textAnchor="end"
          fontSize={9}
          fill="#64748b"
        >
          {node.mappedCount}
        </text>
      ) : null}
    </g>
  );
}
