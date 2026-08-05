import type { RoutedProjectedEdge } from "../../unified-graph/graphTypes";
import type { CanonicalDiagramStyle } from "../../unified-graph/canonicalDiagramTypes";

interface OrthogonalEdgeProps {
  edge: RoutedProjectedEdge;
  opacity: number;
  highlighted: boolean;
  onSelect?: (edgeId: string) => void;
  monochrome?: boolean;
  declaredBends?: number;
  sourceRole?: string;
  targetRole?: string;
  canonicalStyle?: CanonicalDiagramStyle;
}

export function OrthogonalEdge({
  edge,
  opacity,
  highlighted,
  onSelect,
  monochrome = false,
  declaredBends,
  sourceRole,
  targetRole,
  canonicalStyle,
}: OrthogonalEdgeProps) {
  const stateStroke =
    edge.state === "BLOCK"
      ? monochrome ? canonicalStyle?.trace.block ?? "#7f1d1d" : "#dc2626"
      : edge.state === "PASS"
        ? monochrome ? canonicalStyle?.trace.pass ?? "#14532d" : "#16a34a"
        : edge.state === "WARN"
          ? monochrome ? canonicalStyle?.trace.warning ?? "#9a3412" : "#ea580c"
          : null;
  const stroke = stateStroke ??
    (monochrome
      ? canonicalStyle?.edge ?? "#111111"
      : highlighted
        ? "#2563eb"
        : edge.presentationType === "STRUCTURAL"
          ? "#94a3b8"
          : "#64748b");

  return (
    <g
      data-testid={`graph-edge-${edge.id}`}
      data-canonical-edge={monochrome ? edge.id : undefined}
      data-source-role={sourceRole}
      data-target-role={targetRole}
      data-declared-bend-count={declaredBends}
      opacity={opacity}
      style={{ cursor: onSelect ? "pointer" : "default" }}
      onClick={(event) => {
        event.stopPropagation();
        onSelect?.(edge.id);
      }}
    >
      <path
        d={edge.path}
        fill="none"
        stroke={stroke}
        strokeWidth={monochrome ? (highlighted ? 2.2 : canonicalStyle?.edge_width ?? 1.5) : highlighted ? 2.2 : 1.4}
        markerEnd="url(#arrow-unified)"
        vectorEffect="non-scaling-stroke"
        data-canonical-edge-path={monochrome ? edge.id : undefined}
      />
      <text
        x={edge.labelX}
        y={edge.labelY}
        textAnchor="middle"
        fontSize={monochrome ? 14 : 9}
        fill={monochrome ? canonicalStyle?.primary_text ?? "#111111" : "#64748b"}
        stroke={monochrome ? canonicalStyle?.label_background ?? "#ffffff" : undefined}
        strokeWidth={monochrome ? 5 : undefined}
        paintOrder={monochrome ? "stroke" : undefined}
      >
        {edge.labelZh}
      </text>
    </g>
  );
}
