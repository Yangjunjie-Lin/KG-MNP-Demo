import type { GraphTransformState, LayerGeometry } from "../../unified-graph/graphTypes";
import { LAYER_STYLES } from "../../unified-graph/businessLayerConfig";

interface GraphMinimapProps {
  layers: LayerGeometry[];
  transform: GraphTransformState;
  viewportWidth: number;
  viewportHeight: number;
  onJump: (worldX: number, worldY: number) => void;
  hidden?: boolean;
  worldWidth: number;
  worldHeight: number;
  monochrome?: boolean;
}

export function GraphMinimap({
  layers,
  transform,
  viewportWidth,
  viewportHeight,
  onJump,
  hidden,
  worldWidth,
  worldHeight,
  monochrome = false,
}: GraphMinimapProps) {
  if (hidden) return null;
  const width = 180;
  const height = (worldHeight / worldWidth) * width;
  const sx = width / worldWidth;
  const sy = height / worldHeight;

  const viewX = -transform.translateX / transform.scale;
  const viewY = -transform.translateY / transform.scale;
  const viewW = viewportWidth / transform.scale;
  const viewH = viewportHeight / transform.scale;

  return (
    <div
      className="absolute bottom-3 right-3 hidden rounded border border-slate-300 bg-white/90 p-1 shadow-sm min-[900px]:block"
      data-testid="graph-minimap"
    >
      <svg
        width={width}
        height={height}
        viewBox={`0 0 ${width} ${height}`}
        onClick={(event) => {
          const rect = event.currentTarget.getBoundingClientRect();
          const x = ((event.clientX - rect.left) / width) * worldWidth;
          const y = ((event.clientY - rect.top) / height) * worldHeight;
          onJump(x, y);
        }}
      >
        {layers.map((layer) => (
          <rect
            key={layer.id}
            x={layer.x * sx}
            y={layer.y * sy}
            width={layer.width * sx}
            height={layer.height * sy}
            fill={monochrome ? "#ffffff" : LAYER_STYLES[layer.id].background}
            stroke={monochrome ? "#111111" : LAYER_STYLES[layer.id].border}
            strokeWidth={0.5}
          />
        ))}
        <rect
          x={viewX * sx}
          y={viewY * sy}
          width={viewW * sx}
          height={viewH * sy}
          fill="none"
          stroke="#2563eb"
          strokeWidth={1}
        />
        <text x={6} y={12} fontSize={9} fill="#64748b">
          {Math.round(transform.scale * 100)}%
        </text>
      </svg>
    </div>
  );
}
