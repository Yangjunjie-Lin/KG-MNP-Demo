import type { SharedEdgeBus } from "../../unified-graph/graphTypes";
import type {
  CanonicalDiagramStyle,
  CanonicalStructuralEdge,
} from "../../unified-graph/canonicalDiagramTypes";

interface SharedRelationBusProps {
  bus: SharedEdgeBus;
  monochrome?: boolean;
  opacity?: number;
  trunkOpacity?: number;
  branchEdges?: readonly CanonicalStructuralEdge[];
  edgeOpacities?: Readonly<Record<string, number>>;
  canonicalStyle?: CanonicalDiagramStyle;
}

export function SharedRelationBus({
  bus,
  monochrome = false,
  opacity = 1,
  trunkOpacity = 1,
  branchEdges = [],
  edgeOpacities = {},
  canonicalStyle,
}: SharedRelationBusProps) {
  const edgeById = new Map(branchEdges.map((edge) => [edge.id, edge]));
  return (
    <g
      data-testid={`shared-bus-${bus.id}`}
      data-canonical-bus={monochrome ? bus.id : undefined}
      opacity={opacity}
    >
      <path
        d={bus.trunkPath}
        fill="none"
        stroke={monochrome ? canonicalStyle?.edge ?? "#111111" : "#6366f1"}
        strokeWidth={monochrome ? canonicalStyle?.edge_width ?? 1.5 : 1.6}
        vectorEffect="non-scaling-stroke"
        data-canonical-bus-trunk={monochrome ? bus.id : undefined}
        opacity={trunkOpacity}
      />
      {Object.entries(bus.branchPaths).map(([key, path]) => {
        const edge = edgeById.get(key);
        return (
          <g
            key={`${bus.id}-${key}`}
            opacity={edgeOpacities[key] ?? 1}
            data-canonical-edge={monochrome ? key : undefined}
          >
            <path
              d={path}
              fill="none"
              stroke={monochrome ? canonicalStyle?.edge ?? "#111111" : "#6366f1"}
              strokeWidth={monochrome ? canonicalStyle?.edge_width ?? 1.5 : 1.4}
              markerEnd="url(#arrow-unified)"
              vectorEffect="non-scaling-stroke"
              data-canonical-edge-path={monochrome ? key : undefined}
              data-declared-bend-count={edge?.bendCount}
              data-source-role={edge?.sourceRole}
              data-target-role={edge?.targetRole}
            />
            {edge ? (
              <text
                x={edge.labelX}
                y={edge.labelY}
                textAnchor="middle"
                fontSize={14}
                fill={canonicalStyle?.primary_text ?? "#111111"}
                stroke={canonicalStyle?.label_background ?? "#ffffff"}
                strokeWidth={5}
                paintOrder="stroke"
              >
                {edge.labelZh}
              </text>
            ) : null}
          </g>
        );
      })}
      {bus.labelZh ? (
        <text
          x={bus.labelX}
          y={bus.labelY}
          textAnchor="middle"
          fontSize={monochrome ? 14 : 10}
          fill={monochrome ? canonicalStyle?.primary_text ?? "#111111" : "#4f46e5"}
          stroke={monochrome ? canonicalStyle?.label_background ?? "#ffffff" : undefined}
          strokeWidth={monochrome ? 5 : undefined}
          paintOrder={monochrome ? "stroke" : undefined}
        >
          {bus.labelZh}
        </text>
      ) : null}
    </g>
  );
}
