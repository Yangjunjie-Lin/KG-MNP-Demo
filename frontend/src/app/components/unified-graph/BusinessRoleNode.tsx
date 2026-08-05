import { wrapNodeLabel } from "../../unified-graph/graphLabels";
import { LAYER_STYLES } from "../../unified-graph/businessLayerConfig";
import type { CanonicalDiagramStyle } from "../../unified-graph/canonicalDiagramTypes";
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
  subtitle?: string;
  monochrome?: boolean;
  canonicalStyle?: CanonicalDiagramStyle;
}

export function BusinessRoleNode({
  node,
  selected,
  opacity,
  onSelect,
  subtitle,
  monochrome = false,
  canonicalStyle,
}: BusinessRoleNodeProps) {
  const style = LAYER_STYLES[node.layerId];
  const state = node.state ?? "DEFAULT";
  const lines = wrapNodeLabel(node.labelZh, node.width > 160 ? 10 : 8);
  const canonicalStateStroke =
    state === "PASS"
      ? canonicalStyle?.trace.pass ?? "#14532d"
      : state === "BLOCK"
        ? canonicalStyle?.trace.block ?? "#7f1d1d"
        : state === "WARN"
          ? canonicalStyle?.trace.warning ?? "#9a3412"
          : canonicalStyle?.node_border ?? "#111111";
  const stroke = monochrome
    ? canonicalStateStroke
    : selected
      ? "#2563eb"
      : STATE_STROKE[state] ?? style.accent;
  const fill = monochrome
    ? canonicalStyle?.node_background ?? "#ffffff"
    : selected
      ? "#dbeafe"
      : STATE_FILL[state] ?? "#ffffff";
  const safety = node.roleId === "SAFETY_CHECK";

  return (
    <g
      data-testid={`graph-node-${node.projectionId}`}
      data-projection-id={node.projectionId}
      data-source-node-id={node.sourceNodeId}
      data-role-id={node.roleId ?? ""}
      data-node-x={node.x}
      data-node-y={node.y}
      data-node-kind={node.kind}
      data-node-width={node.width}
      data-node-height={node.height}
      data-node-background={fill}
      data-node-radius={monochrome ? canonicalStyle?.node_radius ?? 0 : 6}
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
      {monochrome && node.mappedCount === 0 ? (
        <title>当前无对应本体概念</title>
      ) : null}
      <rect
        x={node.x}
        y={node.y}
        width={node.width}
        height={node.height}
        rx={monochrome ? canonicalStyle?.node_radius ?? 0 : 6}
        fill={fill}
        stroke={stroke}
        strokeWidth={monochrome ? (safety ? canonicalStyle?.safety_check.node_border_width ?? 3.5 : selected ? 2.5 : canonicalStyle?.node_border_width ?? 1.5) : selected ? 2.5 : 1.5}
        vectorEffect="non-scaling-stroke"
        data-node-border-width={monochrome ? (safety ? canonicalStyle?.safety_check.node_border_width ?? 3.5 : canonicalStyle?.node_border_width ?? 1.5) : selected ? 2.5 : 1.5}
      />
      {monochrome ? (
        <text
          x={node.x + node.width / 2}
          y={node.y + node.height / 2}
          textAnchor="middle"
          dominantBaseline="middle"
          fill={canonicalStateStroke}
          data-canonical-node-label={node.roleId ?? ""}
        >
          <tspan
            x={node.x + node.width / 2}
            dy={subtitle ? (safety ? -12 : -10) : 0}
            fontSize={safety ? canonicalStyle?.safety_check.zh_font_size ?? 24 : canonicalStyle?.node_text.zh_font_size ?? 18}
            fontWeight={safety ? canonicalStyle?.safety_check.font_weight ?? 700 : canonicalStyle?.node_text.zh_font_weight ?? 700}
          >
            {node.labelZh}
          </tspan>
          {subtitle ? (
            <tspan
              x={node.x + node.width / 2}
              dy={safety ? 28 : 23}
              fontSize={safety ? canonicalStyle?.safety_check.en_font_size ?? 19 : canonicalStyle?.node_text.en_font_size ?? 15}
              fontWeight={canonicalStyle?.node_text.en_font_weight ?? 400}
            >
              ({subtitle})
            </tspan>
          ) : null}
        </text>
      ) : (
        lines.map((line, index) => (
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
        ))
      )}
      {!monochrome && typeof node.mappedCount === "number" && node.kind === "CORE_ROLE" ? (
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
