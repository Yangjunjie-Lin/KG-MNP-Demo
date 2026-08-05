import { LAYER_STYLES } from "../../unified-graph/businessLayerConfig";
import type { CanonicalDiagramStyle } from "../../unified-graph/canonicalDiagramTypes";
import type { LayerGeometry } from "../../unified-graph/graphTypes";

interface BusinessLayerBackgroundProps {
  layers: LayerGeometry[];
  worldWidth: number;
  worldHeight: number;
  monochrome?: boolean;
  titleLines?: Partial<Record<LayerGeometry["id"], string[]>>;
  titleWidth?: number;
  canonicalStyle?: CanonicalDiagramStyle;
}

export function BusinessLayerBackground({
  layers,
  worldWidth,
  worldHeight,
  monochrome = false,
  titleLines = {},
  titleWidth = 214,
  canonicalStyle,
}: BusinessLayerBackgroundProps) {
  return (
    <g data-testid="business-layer-background">
      <rect
        x={0}
        y={0}
        width={worldWidth}
        height={worldHeight}
        fill={monochrome ? canonicalStyle?.canvas_background ?? "#ffffff" : "#f1f5f9"}
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
              fill={monochrome ? canonicalStyle?.layer_background ?? "#ffffff" : style.background}
              stroke={monochrome ? canonicalStyle?.layer_border ?? "#111111" : style.border}
              strokeWidth={monochrome ? canonicalStyle?.layer_border_width ?? 1.5 : 1}
              rx={monochrome ? 0 : 8}
              vectorEffect="non-scaling-stroke"
              data-layer-background={monochrome ? canonicalStyle?.layer_background ?? "#ffffff" : style.background}
            />
            {monochrome ? (
              <>
                <path
                  d={`M ${layer.x + titleWidth} ${layer.y} V ${layer.y + layer.height}`}
                  fill="none"
                  stroke={canonicalStyle?.layer_border ?? "#111111"}
                  strokeWidth={canonicalStyle?.layer_separator_width ?? 1.5}
                  vectorEffect="non-scaling-stroke"
                />
                <text
                  x={layer.x + titleWidth / 2}
                  y={layer.y + layer.height / 2}
                  textAnchor="middle"
                  dominantBaseline="middle"
                  fill={canonicalStyle?.primary_text ?? "#111111"}
                >
                  {(titleLines[layer.id] ?? [layer.label]).map((line, index, lines) => (
                    <tspan
                      key={`${layer.id}-${line}`}
                      x={layer.x + titleWidth / 2}
                      dy={index === 0 ? -((lines.length - 1) * 11) : 22}
                      fontSize={index === 0 ? 17 : 14}
                      fontWeight={index === 0 ? 700 : 400}
                    >
                      {line}
                    </tspan>
                  ))}
                </text>
              </>
            ) : (
              <>
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
              </>
            )}
          </g>
        );
      })}
    </g>
  );
}
