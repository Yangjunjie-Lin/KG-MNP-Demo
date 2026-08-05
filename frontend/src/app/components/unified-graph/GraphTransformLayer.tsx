import type { ReactNode } from "react";
import type { GraphTransformState } from "../../unified-graph/graphTypes";

interface GraphTransformLayerProps {
  transform: GraphTransformState;
  children: ReactNode;
}

export function GraphTransformLayer({
  transform,
  children,
}: GraphTransformLayerProps) {
  return (
    <g
      data-testid="graph-transform-layer"
      transform={`translate(${transform.translateX} ${transform.translateY}) scale(${transform.scale})`}
    >
      {children}
    </g>
  );
}
