import { collapsedEdgeDisplayLabel } from "../../ontology/orthogonalRouter";
import type { RoutedOntologyEdge } from "../../ontology/ontologyGraphTypes";

interface OntologyEdgePathProps {
  edge: RoutedOntologyEdge;
  opacity: number;
  highlighted: boolean;
  onSelect?: (edgeId: string) => void;
}

export function OntologyEdgePath({
  edge,
  opacity,
  highlighted,
  onSelect,
}: OntologyEdgePathProps) {
  const label = collapsedEdgeDisplayLabel(edge);
  const labelWidth = Math.max(36, label.length * 7 + 8);
  const labelHeight = 16;

  return (
    <g
      data-testid={`ontology-edge-${edge.id}`}
      opacity={opacity}
      className={onSelect ? "cursor-pointer" : undefined}
      onClick={() => onSelect?.(edge.id)}
    >
      <path
        d={edge.path}
        fill="none"
        stroke={highlighted ? "#334155" : "#94a3b8"}
        strokeWidth={highlighted ? 2 : 1.25}
        markerEnd="url(#arrow-ontology)"
      />
      <rect
        x={edge.labelX - labelWidth / 2}
        y={edge.labelY - labelHeight / 2}
        width={labelWidth}
        height={labelHeight}
        rx={2}
        fill="#ffffff"
        stroke="#e2e8f0"
        strokeWidth={1}
      />
      <text
        x={edge.labelX}
        y={edge.labelY + 3.5}
        fontSize={9}
        fill="#64748b"
        textAnchor="middle"
      >
        {label}
      </text>
    </g>
  );
}
