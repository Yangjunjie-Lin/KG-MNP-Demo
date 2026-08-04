import { LANE_STYLES } from "../../ontology/ontologyLaneConfig";
import type { LaneGeometry } from "../../ontology/ontologyGraphTypes";

interface OntologyLaneBackgroundProps {
  lanes: LaneGeometry[];
  contentRight: number;
  height: number;
  width: number;
}

export function OntologyLaneBackground({
  lanes,
  contentRight,
  height,
  width,
}: OntologyLaneBackgroundProps) {
  return (
    <g data-testid="ontology-lane-background">
      <rect
        x={contentRight}
        y={0}
        width={Math.max(0, width - contentRight)}
        height={height}
        fill="#f8fafc"
        opacity={0.7}
      />
      {lanes.map((lane) => {
        const style = LANE_STYLES[lane.id];
        return (
          <g key={lane.id} data-testid={`ontology-lane-${lane.id}`}>
            <rect
              x={lane.x}
              y={lane.y}
              width={lane.width}
              height={lane.height}
              rx={6}
              fill={style.background}
              stroke={style.border}
              strokeWidth={1}
            />
            <rect
              x={lane.x}
              y={lane.y}
              width={190}
              height={lane.height}
              rx={6}
              fill={style.background}
              stroke="none"
            />
            <text
              x={lane.x + 16}
              y={lane.y + 28}
              fontSize={12}
              fontWeight={600}
              fill={style.accent}
            >
              {lane.label}
            </text>
          </g>
        );
      })}
    </g>
  );
}
