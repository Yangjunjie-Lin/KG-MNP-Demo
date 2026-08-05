import {
  useCallback,
  useEffect,
  useRef,
  type ReactNode,
  type PointerEvent as ReactPointerEvent,
  type WheelEvent as ReactWheelEvent,
} from "react";
import type { DragState, GraphTransformState, Rect } from "../../unified-graph/graphTypes";
import {
  BUSINESS_WORLD,
} from "../../unified-graph/businessLayerConfig";
import {
  DRAG_THRESHOLD_PX,
  clampTranslation,
  exceedsDragThreshold,
  panByDelta,
  zoomAtPointer,
} from "../../unified-graph/graphTransform";
import { GraphTransformLayer } from "./GraphTransformLayer";

interface GraphViewportProps {
  transform: GraphTransformState;
  onTransformChange: (next: GraphTransformState) => void;
  worldWidth?: number;
  worldHeight?: number;
  diagnosticsAttrs: Record<string, string | number>;
  children: ReactNode;
  cursor?: "grab" | "grabbing" | "default";
  graphTestId?: string;
  canvasBackground?: string;
}

export function GraphViewport({
  transform,
  onTransformChange,
  worldWidth = BUSINESS_WORLD.width,
  worldHeight = BUSINESS_WORLD.height,
  diagnosticsAttrs,
  children,
  cursor = "grab",
  graphTestId = "unified-business-graph",
  canvasBackground = "#f1f5f9",
}: GraphViewportProps) {
  const containerRef = useRef<HTMLDivElement | null>(null);
  const svgRef = useRef<SVGSVGElement | null>(null);
  const dragRef = useRef<DragState | null>(null);

  const applyClamped = useCallback(
    (next: GraphTransformState) => {
      const rect = containerRef.current?.getBoundingClientRect();
      if (!rect) {
        onTransformChange(next);
        return;
      }
      const viewport: Rect = { x: 0, y: 0, width: worldWidth, height: worldHeight };
      const world: Rect = { x: 0, y: 0, width: worldWidth, height: worldHeight };
      onTransformChange(clampTranslation(next, viewport, world));
    },
    [onTransformChange, worldHeight, worldWidth],
  );

  const clientToSvg = useCallback((clientX: number, clientY: number) => {
    const svg = svgRef.current;
    const matrix = svg?.getScreenCTM();
    if (!svg || !matrix) return null;
    const point = svg.createSVGPoint();
    point.x = clientX;
    point.y = clientY;
    return point.matrixTransform(matrix.inverse());
  }, []);

  const onWheel = (event: ReactWheelEvent<SVGSVGElement>) => {
    event.preventDefault();
    event.stopPropagation();
    const pointer = clientToSvg(event.clientX, event.clientY);
    if (!pointer) return;
    const nextScale = transform.scale * Math.exp(-event.deltaY * 0.0015);
    applyClamped(
      zoomAtPointer({
        transform,
        pointerX: pointer.x,
        pointerY: pointer.y,
        nextScale,
      }),
    );
  };

  const onPointerDown = (event: ReactPointerEvent<SVGSVGElement>) => {
    if (event.button !== 0) return;
    const target = event.target as Element;
    if (target.closest("[data-projection-id]")) return;
    dragRef.current = {
      pointerId: event.pointerId,
      startClientX: event.clientX,
      startClientY: event.clientY,
      startTranslateX: transform.translateX,
      startTranslateY: transform.translateY,
      moved: false,
    };
    svgRef.current?.setPointerCapture(event.pointerId);
  };

  const onPointerMove = (event: ReactPointerEvent<SVGSVGElement>) => {
    const drag = dragRef.current;
    if (!drag || drag.pointerId !== event.pointerId) return;
    if (
      !drag.moved &&
      !exceedsDragThreshold(
        drag.startClientX,
        drag.startClientY,
        event.clientX,
        event.clientY,
        DRAG_THRESHOLD_PX,
      )
    ) {
      return;
    }
    drag.moved = true;
    const start = clientToSvg(drag.startClientX, drag.startClientY);
    const current = clientToSvg(event.clientX, event.clientY);
    if (!start || !current) return;
    const dx = current.x - start.x;
    const dy = current.y - start.y;
    applyClamped(
      panByDelta(
        {
          scale: transform.scale,
          translateX: drag.startTranslateX,
          translateY: drag.startTranslateY,
        },
        dx,
        dy,
      ),
    );
  };

  const endDrag = (event: ReactPointerEvent<SVGSVGElement>) => {
    const drag = dragRef.current;
    if (!drag || drag.pointerId !== event.pointerId) return;
    dragRef.current = null;
    try {
      svgRef.current?.releasePointerCapture(event.pointerId);
    } catch {
      // ignore
    }
  };

  useEffect(() => {
    const node = svgRef.current;
    if (!node) return;
    const handler = (event: WheelEvent) => {
      event.preventDefault();
    };
    node.addEventListener("wheel", handler, { passive: false });
    return () => node.removeEventListener("wheel", handler);
  }, []);

  return (
    <div
      ref={containerRef}
      className="relative h-full min-h-[480px] w-full overflow-hidden border border-slate-200"
      style={{ background: canvasBackground }}
      data-testid="graph-viewport"
    >
      <svg
        ref={svgRef}
        width="100%"
        height="100%"
        viewBox={`0 0 ${worldWidth} ${worldHeight}`}
        preserveAspectRatio="xMidYMid meet"
        className="h-full w-full touch-none"
        style={{ cursor: dragRef.current?.moved ? "grabbing" : cursor }}
        data-testid={graphTestId}
        data-graph-scale={transform.scale}
        data-graph-translate-x={transform.translateX}
        data-graph-translate-y={transform.translateY}
        {...Object.fromEntries(
          Object.entries(diagnosticsAttrs).map(([key, value]) => [key, String(value)]),
        )}
        onWheel={onWheel}
        onPointerDown={onPointerDown}
        onPointerMove={onPointerMove}
        onPointerUp={endDrag}
        onPointerCancel={endDrag}
      >
        <defs>
          <marker
            id="arrow-unified"
            markerWidth="7"
            markerHeight="7"
            refX="6"
            refY="2.5"
            orient="auto"
            markerUnits="strokeWidth"
          >
            <polygon points="0,0 0,5 7,2.5" fill="context-stroke" />
          </marker>
        </defs>
        <GraphTransformLayer transform={transform}>{children}</GraphTransformLayer>
      </svg>
    </div>
  );
}
