import { LANE_STYLES } from "../../ontology/ontologyLaneConfig";
import type { PositionedOntologyNode } from "../../types/ontology";

interface OntologyNodeCardProps {
  node: PositionedOntologyNode;
  label: string;
  selected: boolean;
  opacity: number;
  onSelect: (nodeId: string) => void;
}

export function OntologyNodeCard({
  node,
  label,
  selected,
  opacity,
  onSelect,
}: OntologyNodeCardProps) {
  const style = LANE_STYLES[node.laneId];
  return (
    <g
      role="button"
      tabIndex={0}
      data-testid={`ontology-node-${node.localName}`}
      opacity={opacity}
      className="cursor-pointer outline-none"
      onClick={() => onSelect(node.id)}
      onKeyDown={(event) => {
        if (event.key === "Enter" || event.key === " ") {
          event.preventDefault();
          onSelect(node.id);
        }
        if (event.key === "Escape") {
          event.preventDefault();
          onSelect("");
        }
      }}
    >
      <rect
        x={node.x}
        y={node.y}
        width={node.width}
        height={node.height}
        rx={5}
        fill="#ffffff"
        stroke={selected ? style.accent : style.border}
        strokeWidth={selected ? 2 : 1}
      />
      <text
        x={node.x + node.width / 2}
        y={node.y + node.height / 2 + 4}
        fontSize={11}
        fontWeight={node.overview ? 600 : 500}
        fill={style.accent}
        textAnchor="middle"
      >
        {label}
      </text>
    </g>
  );
}
