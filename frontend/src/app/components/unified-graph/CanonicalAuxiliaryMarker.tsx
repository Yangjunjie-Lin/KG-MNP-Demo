import type {
  CanonicalAuxiliaryMarker as CanonicalAuxiliaryMarkerConfig,
  CanonicalDiagramStyle,
} from "../../unified-graph/canonicalDiagramTypes";

interface CanonicalAuxiliaryMarkerProps {
  marker: CanonicalAuxiliaryMarkerConfig;
  opacity?: number;
  diagramStyle: CanonicalDiagramStyle;
}

export function CanonicalAuxiliaryMarker({
  marker,
  opacity = 1,
  diagramStyle,
}: CanonicalAuxiliaryMarkerProps) {
  return (
    <g
      data-testid={`canonical-marker-${marker.id}`}
      data-canonical-marker={marker.id}
      opacity={opacity}
    >
      <rect
        x={marker.rect.x}
        y={marker.rect.y}
        width={marker.rect.width}
        height={marker.rect.height}
        fill={marker.style.fill}
        stroke={marker.style.stroke}
        strokeWidth={marker.style.strokeWidth}
        strokeDasharray={marker.style.strokeDasharray}
        vectorEffect="non-scaling-stroke"
      />
      {marker.arrows.map((arrow) => (
        <path
          key={arrow.id}
          d={arrow.path}
          fill="none"
          stroke={marker.style.stroke}
          strokeWidth={marker.style.strokeWidth}
          strokeDasharray={marker.style.strokeDasharray}
          markerEnd="url(#arrow-unified)"
          vectorEffect="non-scaling-stroke"
          data-canonical-marker-arrow={arrow.id}
        />
      ))}
      <text
        x={marker.labelX}
        y={marker.labelY}
        dominantBaseline="middle"
        fontSize={15}
        fill={diagramStyle.primary_text}
        stroke={diagramStyle.label_background}
        strokeWidth={5}
        paintOrder="stroke"
      >
        {marker.labelZh}
      </text>
    </g>
  );
}
