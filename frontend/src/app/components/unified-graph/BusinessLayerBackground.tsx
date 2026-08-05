import { LAYER_STYLES } from "../../unified-graph/businessLayerConfig";
import type { LayerGeometry } from "../../unified-graph/graphTypes";

interface BusinessLayerBackgroundProps {
  layers: LayerGeometry[];
  worldWidth: number;
  worldHeight: number;
}

export function BusinessLayerBackground({
  layers,
  worldWidth,
  worldHeight,
}: BusinessLayerBackgroundProps) {
  return (
    <g data-testid="business-layer-background">
      <rect
        x={0}
        y={0}
        width={worldWidth}
        height={worldHeight}
        fill="#f1f5f9"
      />
      {layers.map((layer) => {
        const style = LAYER_STYLES[layer.id];
        return (
          <g key={layer.id} data-testid={`ontology-lane-${layer.id}`}>
            <rect
              x={layer.x}
              y={layer.y}
              width={layer.width}
              height={layer.height}
              fill={style.background}
              stroke={style.border}
              strokeWidth={1}
              rx={8}
              vectorEffect="non-scaling-stroke"
            />
            <rect
              x={layer.x}
              y={layer.y}
              width={Math.min(200, layer.contentX - layer.x)}
              height={layer.height}
              fill={style.accent}
              opacity={0.08}
              rx={8}
            />
            <text
              x={layer.x + 14}
              y={layer.y + 28}
              fontSize={13}
              fontWeight={600}
              fill={style.accent}
            >
              {layer.label}
            </text>
          </g>
        );
      })}
    </g>
  );
}
