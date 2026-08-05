import { useCallback, useEffect, useMemo, useRef, useState } from "react";
import { BusinessLayerBackground } from "./BusinessLayerBackground";
import { BusinessRoleNode } from "./BusinessRoleNode";
import { ExtensionNode } from "./ExtensionNode";
import { GraphMinimap } from "./GraphMinimap";
import { GraphNodeDetails } from "./GraphNodeDetails";
import { GraphToolbar } from "./GraphToolbar";
import { GraphViewport } from "./GraphViewport";
import { OrthogonalEdge } from "./OrthogonalEdge";
import { SharedRelationBus } from "./SharedRelationBus";
import { BUSINESS_WORLD } from "../../unified-graph/businessLayerConfig";
import {
  summarizeGeometryViolations,
  validateUnifiedGraphGeometry,
} from "../../unified-graph/graphGeometry";
import { buildUnifiedGraph } from "../../unified-graph/layeredLayout";
import { routeProjectedEdges } from "../../unified-graph/orthogonalRouter";
import {
  relatedEdgeIds,
  relatedProjectionIds,
  selectNodeById,
} from "../../unified-graph/graphSelectors";
import {
  fitGraphToViewport,
  scaleAt100Percent,
  zoomByFactor,
} from "../../unified-graph/graphTransform";
import type {
  GraphBuildInputEdge,
  GraphBuildInputNode,
  GraphTransformState,
  UnifiedGraphMode,
} from "../../unified-graph/graphTypes";

interface UnifiedBusinessGraphProps {
  mode: UnifiedGraphMode;
  nodes: GraphBuildInputNode[];
  edges: GraphBuildInputEdge[];
  activeNodeIds?: Set<string>;
  activeEdgeIds?: Set<string>;
  showDetails?: boolean;
  testId?: string;
  graphTestId?: string;
}

export function UnifiedBusinessGraph({
  mode,
  nodes,
  edges,
  activeNodeIds,
  activeEdgeIds,
  showDetails = true,
  testId = "unified-business-graph-root",
  graphTestId = "unified-business-graph",
}: UnifiedBusinessGraphProps) {
  const rootRef = useRef<HTMLDivElement | null>(null);
  const [selectedId, setSelectedId] = useState<string | null>(null);
  const [searchTerm, setSearchTerm] = useState("");
  const [viewportSize, setViewportSize] = useState({ width: 960, height: 640 });
  const [transform, setTransform] = useState<GraphTransformState>({
    scale: 1,
    translateX: 0,
    translateY: 0,
  });
  const initialTransformRef = useRef<GraphTransformState | null>(null);

  const graph = useMemo(
    () =>
      buildUnifiedGraph({
        mode,
        nodes,
        edges,
        activeNodeIds,
        activeEdgeIds,
      }),
    [mode, nodes, edges, activeNodeIds, activeEdgeIds],
  );

  const routedEdges = useMemo(
    () =>
      routeProjectedEdges({
        nodes: graph.nodes,
        collapsedEdges: graph.collapsedEdges,
        layers: graph.layers,
        contentRight: graph.contentRight,
      }),
    [graph],
  );

  const violations = useMemo(
    () =>
      validateUnifiedGraphGeometry({
        nodes: graph.nodes,
        edges: routedEdges,
        layers: graph.layers,
        buses: graph.buses,
        danglingEdgeCount: graph.danglingEdges.length,
      }),
    [graph, routedEdges],
  );
  const diagnostics = useMemo(
    () => summarizeGeometryViolations(violations),
    [violations],
  );

  useEffect(() => {
    if (violations.length) {
      console.error("[unified-graph] geometry violations", {
        diagnostics,
        violations,
      });
    }
  }, [diagnostics, violations]);

  const fit = useCallback(() => {
    const next = fitGraphToViewport({
      viewportWidth: viewportSize.width,
      viewportHeight: viewportSize.height,
      graphWorldWidth: BUSINESS_WORLD.width,
      graphWorldHeight: BUSINESS_WORLD.height,
    });
    setTransform(next);
    return next;
  }, [viewportSize.height, viewportSize.width]);

  useEffect(() => {
    const el = rootRef.current;
    if (!el) return;
    const update = () => {
      const rect = el.getBoundingClientRect();
      setViewportSize({
        width: Math.max(320, rect.width || 960),
        height: Math.max(360, (rect.height || 640) - 48),
      });
    };
    update();
    if (typeof ResizeObserver === "undefined") {
      return;
    }
    const observer = new ResizeObserver(update);
    observer.observe(el);
    return () => observer.disconnect();
  }, []);

  useEffect(() => {
    const next = fit();
    if (!initialTransformRef.current) {
      initialTransformRef.current = next;
    }
  }, [fit, mode]);

  useEffect(() => {
    const onKeyDown = (event: KeyboardEvent) => {
      const centerX = viewportSize.width / 2;
      const centerY = viewportSize.height / 2;
      if (event.key === "+" || event.key === "=") {
        setTransform((prev) => zoomByFactor(prev, 1.2, centerX, centerY));
      } else if (event.key === "-") {
        setTransform((prev) => zoomByFactor(prev, 1 / 1.2, centerX, centerY));
      } else if (event.key === "0") {
        setTransform(initialTransformRef.current ?? fit());
      } else if (event.key.toLowerCase() === "f") {
        fit();
      } else if (event.key === "Escape") {
        setSelectedId(null);
      }
    };
    window.addEventListener("keydown", onKeyDown);
    return () => window.removeEventListener("keydown", onKeyDown);
  }, [fit, viewportSize.height, viewportSize.width]);

  const selectedNode = selectNodeById(graph.nodes, selectedId);
  const relatedIds = relatedProjectionIds(selectedId, routedEdges);
  const relatedEdges = relatedEdgeIds(selectedId, routedEdges);

  const searchMatches = useMemo(() => {
    const term = searchTerm.trim();
    if (!term) return null;
    return new Set(
      graph.nodes
        .filter((node) => node.labelZh.includes(term))
        .map((node) => node.projectionId),
    );
  }, [graph.nodes, searchTerm]);

  const nodeOpacity = (projectionId: string) => {
    if (searchMatches) return searchMatches.has(projectionId) ? 1 : 0.15;
    if (!selectedId) return 1;
    return relatedIds.has(projectionId) ? 1 : 0.2;
  };

  const edgeOpacity = (edgeId: string) => {
    if (!selectedId) return 1;
    return relatedEdges.has(edgeId) ? 1 : 0.1;
  };

  const relatedDetailNodes = graph.nodes.filter(
    (node) => relatedIds.has(node.projectionId) && node.projectionId !== selectedId,
  );

  return (
    <div ref={rootRef} className="flex h-full min-h-[520px] flex-col" data-testid={testId}>
      <GraphToolbar
        scale={transform.scale}
        onZoomIn={() =>
          setTransform((prev) =>
            zoomByFactor(prev, 1.2, viewportSize.width / 2, viewportSize.height / 2),
          )
        }
        onZoomOut={() =>
          setTransform((prev) =>
            zoomByFactor(prev, 1 / 1.2, viewportSize.width / 2, viewportSize.height / 2),
          )
        }
        onFit={() => fit()}
        onReset={() => setTransform(initialTransformRef.current ?? fit())}
        onScale100={() =>
          setTransform((prev) =>
            scaleAt100Percent(prev, viewportSize.width / 2, viewportSize.height / 2),
          )
        }
        searchTerm={searchTerm}
        onSearchChange={setSearchTerm}
      />

      <div className="relative min-h-0 flex-1">
        <div
          className={
            showDetails
              ? "flex h-full min-h-0 flex-col lg:flex-row"
              : "h-full min-h-0"
          }
        >
          <div className="min-h-0 min-w-0 flex-1">
            <GraphViewport
              transform={transform}
              onTransformChange={setTransform}
              graphTestId={graphTestId}
              diagnosticsAttrs={{
                "data-graph-node-count": graph.nodes.length,
                "data-graph-edge-count": routedEdges.length,
                "data-graph-dangling-edge-count": graph.danglingEdges.length,
                "data-graph-geometry-violation-count": diagnostics.total,
                "data-graph-unmapped-node-count": graph.unmappedNodeIds.length,
                "data-geometry-violation-count": diagnostics.total,
                "data-unmapped-node-count": graph.unmappedNodeIds.length,
                "data-runtime-node-count": nodes.length,
                "data-runtime-edge-count": edges.length,
                "data-rendered-node-count": graph.nodes.length,
                "data-rendered-edge-count": routedEdges.length,
                "data-overview-width": BUSINESS_WORLD.width,
                "data-edge-through-node-count": diagnostics.edgeThroughNode,
                "data-segment-overlap-count": diagnostics.segmentOverlap,
                "data-label-inside-node-count": diagnostics.labelInsideNode,
                "data-node-outside-lane-count": diagnostics.nodeOutsideLayer,
                "data-duplicate-cross-channel-count": diagnostics.duplicateCrossChannel,
              }}
            >
              <BusinessLayerBackground
                layers={graph.layers}
                worldWidth={BUSINESS_WORLD.width}
                worldHeight={BUSINESS_WORLD.height}
              />
              {graph.buses.map((bus) => (
                <SharedRelationBus key={bus.id} bus={bus} />
              ))}
              <g data-testid="unified-graph-edges">
                {routedEdges.map((edge) => (
                  <OrthogonalEdge
                    key={edge.id}
                    edge={edge}
                    opacity={edgeOpacity(edge.id)}
                    highlighted={relatedEdges.has(edge.id)}
                  />
                ))}
              </g>
              <g data-testid="unified-graph-nodes">
                {graph.nodes.map((node) =>
                  node.kind === "EXTENSION" ? (
                    <ExtensionNode
                      key={node.projectionId}
                      node={node}
                      selected={selectedId === node.projectionId}
                      opacity={nodeOpacity(node.projectionId)}
                      onSelect={(id) =>
                        setSelectedId((prev) => (prev === id ? null : id))
                      }
                    />
                  ) : (
                    <BusinessRoleNode
                      key={node.projectionId}
                      node={node}
                      selected={selectedId === node.projectionId}
                      opacity={nodeOpacity(node.projectionId)}
                      onSelect={(id) =>
                        setSelectedId((prev) => (prev === id ? null : id))
                      }
                    />
                  ),
                )}
              </g>
            </GraphViewport>
          </div>
          {showDetails ? (
            <aside className="max-h-[220px] w-full flex-shrink-0 overflow-y-auto border-t border-slate-200 bg-white p-4 lg:max-h-none lg:w-[280px] lg:border-l lg:border-t-0">
              <GraphNodeDetails
                node={selectedNode}
                edges={graph.edges}
                relatedNodes={relatedDetailNodes}
                onClose={() => setSelectedId(null)}
              />
            </aside>
          ) : null}
        </div>

        <GraphMinimap
          layers={graph.layers}
          transform={transform}
          viewportWidth={viewportSize.width}
          viewportHeight={viewportSize.height}
          onJump={(worldX, worldY) => {
            setTransform((prev) => ({
              ...prev,
              translateX: viewportSize.width / 2 - worldX * prev.scale,
              translateY: viewportSize.height / 2 - worldY * prev.scale,
            }));
          }}
        />
      </div>
    </div>
  );
}
