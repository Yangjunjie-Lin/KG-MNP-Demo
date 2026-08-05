import type { SharedEdgeBus } from "../../unified-graph/graphTypes";

interface SharedRelationBusProps {
  bus: SharedEdgeBus;
}

export function SharedRelationBus({ bus }: SharedRelationBusProps) {
  return (
    <g data-testid={`shared-bus-${bus.id}`}>
      <path
        d={bus.trunkPath}
        fill="none"
        stroke="#6366f1"
        strokeWidth={1.6}
        vectorEffect="non-scaling-stroke"
      />
      {Object.entries(bus.branchPaths).map(([key, path]) => (
        <path
          key={`${bus.id}-${key}`}
          d={path}
          fill="none"
          stroke="#6366f1"
          strokeWidth={1.4}
          markerEnd={key === "trunk" ? undefined : "url(#arrow-unified)"}
          vectorEffect="non-scaling-stroke"
        />
      ))}
      <text
        x={bus.labelX}
        y={bus.labelY}
        textAnchor="middle"
        fontSize={10}
        fill="#4f46e5"
      >
        {bus.labelZh}
      </text>
    </g>
  );
}
