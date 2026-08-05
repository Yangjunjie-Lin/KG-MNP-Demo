import type { RoutedProjectedEdge } from "../../unified-graph/graphTypes";

interface OrthogonalEdgeProps {
  edge: RoutedProjectedEdge;
  opacity: number;
  highlighted: boolean;
  onSelect?: (edgeId: string) => void;
}

export function OrthogonalEdge({
  edge,
  opacity,
  highlighted,
  onSelect,
}: OrthogonalEdgeProps) {
  const stroke =
    edge.state === "BLOCK"
      ? "#dc2626"
      : edge.state === "PASS"
        ? "#16a34a"
        : edge.state === "WARN"
          ? "#ea580c"
          : highlighted
            ? "#2563eb"
            : edge.presentationType === "STRUCTURAL"
              ? "#94a3b8"
              : "#64748b";

  return (
    <g
      data-testid={`graph-edge-${edge.id}`}
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
        strokeWidth={highlighted ? 2.2 : 1.4}
        markerEnd="url(#arrow-unified)"
        vectorEffect="non-scaling-stroke"
      />
      <text
        x={edge.labelX}
        y={edge.labelY}
        textAnchor="middle"
        fontSize={9}
        fill="#64748b"
      >
        {edge.labelZh}
      </text>
    </g>
  );
}
