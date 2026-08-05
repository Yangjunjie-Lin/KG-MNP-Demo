import { useCallback, useEffect, useMemo, useRef, useState } from "react";
import { BusinessLayerBackground } from "./BusinessLayerBackground";
import { BusinessRoleNode } from "./BusinessRoleNode";
import { CanonicalAuxiliaryMarker } from "./CanonicalAuxiliaryMarker";
import { ExtensionNode } from "./ExtensionNode";
import { GraphMinimap } from "./GraphMinimap";
import { GraphNodeDetails } from "./GraphNodeDetails";
import { GraphToolbar } from "./GraphToolbar";
import { GraphViewport } from "./GraphViewport";
import { OrthogonalEdge } from "./OrthogonalEdge";
import { SharedRelationBus } from "./SharedRelationBus";
import {
  CANONICAL_BUSES,
  CANONICAL_EDGES,
  CANONICAL_LAYERS,
  CANONICAL_MARKERS,
  CANONICAL_NODE_BY_ID,
  CANONICAL_STYLE,
  canonicalDiagramConfig,
} from "../../unified-graph/canonicalDiagramConfig";
import { validateCanonicalEdgeEndpoints } from "../../unified-graph/canonicalEdgeEndpoints";
import { validateCanonicalDiagramGeometry } from "../../unified-graph/canonicalGeometry";
import {
  canonicalPathSubpaths,
  countPathBends,
} from "../../unified-graph/canonicalPath";
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
  scaleAt100Percent,
  zoomByFactor,
} from "../../unified-graph/graphTransform";
import type {
  GraphBuildInputEdge,
  GraphBuildInputNode,
  GraphTransformState,
  ProjectedGraphEdge,
  RoutedProjectedEdge,
  UnifiedGraphMode,
} from "../../unified-graph/graphTypes";

const CANONICAL_ENDPOINT_RESULTS = validateCanonicalEdgeEndpoints({
  edges: CANONICAL_EDGES,
  nodes: [...CANONICAL_NODE_BY_ID.values()],
  buses: CANONICAL_BUSES,
});
const CANONICAL_GEOMETRY = validateCanonicalDiagramGeometry(
  canonicalDiagramConfig,
);

function buildCanonicalRoutedEdges(
  projectedEdges: ProjectedGraphEdge[],
): RoutedProjectedEdge[] {
  const projectedById = new Map(projectedEdges.map((edge) => [edge.id, edge]));
  return CANONICAL_EDGES.map((edge, channel) => {
    const projected = projectedById.get(edge.id);
    const points = canonicalPathSubpaths(edge.path).flat();
    const source = CANONICAL_NODE_BY_ID.get(edge.sourceRole);
    const target = CANONICAL_NODE_BY_ID.get(edge.targetRole);
    return {
      id: edge.id,
      from: `role:${edge.sourceRole}`,
      to: `role:${edge.targetRole}`,
      edges: projected ? [projected] : [],
      points,
      path: edge.path,
      labelX: edge.labelX,
      labelY: edge.labelY,
      labelZh: edge.labelZh,
      kind:
        source?.layerId === target?.layerId
          ? "INTRA_LAYER"
          : "CROSS_LAYER",
      channel,
      presentationType: "STRUCTURAL",
      state: projected?.state,
    };
  });
}

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
  const isCanonicalMode = mode !== "COMPLETE_ONTOLOGY";

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
    () => {
      if (isCanonicalMode) return buildCanonicalRoutedEdges(graph.edges);
      return routeProjectedEdges({
        nodes: graph.nodes,
        collapsedEdges: graph.collapsedEdges,
        layers: graph.layers,
        contentRight: graph.contentRight,
      });
    },
    [graph, isCanonicalMode],
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
    const next = { scale: 1, translateX: 0, translateY: 0 };
    setTransform(next);
    return next;
  }, []);

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
      const centerX = graph.worldWidth / 2;
      const centerY = graph.worldHeight / 2;
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
  }, [fit, graph.worldHeight, graph.worldWidth]);

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
    const base =
      isCanonicalMode &&
      graph.nodes.find((node) => node.projectionId === projectionId)?.state ===
        "DIMMED"
        ? CANONICAL_STYLE.trace.inactive_node_opacity
        : 1;
    if (searchMatches) return searchMatches.has(projectionId) ? 1 : 0.15;
    if (!selectedId) return base;
    return relatedIds.has(projectionId) ? base : Math.min(base, 0.2);
  };

  const edgeOpacity = (edgeId: string) => {
    const base =
      isCanonicalMode &&
      routedEdges.find((edge) => edge.id === edgeId)?.state === "DIMMED"
        ? CANONICAL_STYLE.trace.inactive_edge_opacity
        : 1;
    if (!selectedId) return base;
    return relatedEdges.has(edgeId) ? base : Math.min(base, 0.1);
  };

  const canonicalEdgeById = new Map(CANONICAL_EDGES.map((edge) => [edge.id, edge]));
  const canonicalDirectEdges = routedEdges.filter(
    (edge) => !canonicalEdgeById.get(edge.id)?.busId,
  );
  const disconnectedSourceCount = CANONICAL_ENDPOINT_RESULTS.filter(
    (result) => !result.sourceConnected,
  ).length;
  const disconnectedTargetCount = CANONICAL_ENDPOINT_RESULTS.filter(
    (result) => !result.targetConnected,
  ).length;
  const excessiveBendCount = CANONICAL_EDGES.filter(
    (edge) =>
      countPathBends(edge.path) > edge.bendCount ||
      countPathBends(edge.path) > 3,
  ).length;
  const canonicalViolationCount =
    CANONICAL_GEOMETRY.total +
    disconnectedSourceCount +
    disconnectedTargetCount +
    excessiveBendCount;

  const relatedDetailNodes = graph.nodes.filter(
    (node) => relatedIds.has(node.projectionId) && node.projectionId !== selectedId,
  );

  return (
    <div ref={rootRef} className="flex h-full min-h-[520px] flex-col" data-testid={testId}>
      <GraphToolbar
        scale={transform.scale}
        onZoomIn={() =>
          setTransform((prev) =>
            zoomByFactor(prev, 1.2, graph.worldWidth / 2, graph.worldHeight / 2),
          )
        }
        onZoomOut={() =>
          setTransform((prev) =>
            zoomByFactor(prev, 1 / 1.2, graph.worldWidth / 2, graph.worldHeight / 2),
          )
        }
        onFit={() => fit()}
        onReset={() => setTransform(initialTransformRef.current ?? fit())}
        onScale100={() =>
          setTransform((prev) =>
            scaleAt100Percent(prev, graph.worldWidth / 2, graph.worldHeight / 2),
          )
        }
        searchTerm={searchTerm}
        onSearchChange={setSearchTerm}
      />

      <div className="relative min-h-0 flex-1">
        <div
          className={
            showDetails && selectedNode
              ? "flex h-full min-h-0 flex-col lg:flex-row"
              : "h-full min-h-0"
          }
        >
          <div className="min-h-0 min-w-0 flex-1">
            <GraphViewport
              transform={transform}
              onTransformChange={setTransform}
              graphTestId={graphTestId}
              worldWidth={graph.worldWidth}
              worldHeight={graph.worldHeight}
              canvasBackground={
                isCanonicalMode ? CANONICAL_STYLE.canvas_background : undefined
              }
              diagnosticsAttrs={{
                "data-graph-node-count": graph.nodes.length,
                "data-graph-edge-count": routedEdges.length,
                "data-graph-dangling-edge-count": graph.danglingEdges.length,
                "data-graph-geometry-violation-count": isCanonicalMode
                  ? canonicalViolationCount
                  : diagnostics.total,
                "data-graph-unmapped-node-count": graph.unmappedNodeIds.length,
                "data-geometry-violation-count": isCanonicalMode
                  ? canonicalViolationCount
                  : diagnostics.total,
                "data-unmapped-node-count": graph.unmappedNodeIds.length,
                "data-runtime-node-count": nodes.length,
                "data-runtime-edge-count": edges.length,
                "data-rendered-node-count": graph.nodes.length,
                "data-rendered-edge-count": routedEdges.length,
                "data-overview-width": graph.worldWidth,
                "data-edge-through-node-count": isCanonicalMode
                  ? CANONICAL_GEOMETRY.edgeThroughNode
                  : diagnostics.edgeThroughNode,
                "data-segment-overlap-count": isCanonicalMode
                  ? CANONICAL_GEOMETRY.unexpectedOverlap
                  : diagnostics.segmentOverlap,
                "data-label-inside-node-count": isCanonicalMode
                  ? CANONICAL_GEOMETRY.labelInsideNode
                  : diagnostics.labelInsideNode,
                "data-node-outside-lane-count": isCanonicalMode
                  ? CANONICAL_GEOMETRY.nodeOutsideCanvas
                  : diagnostics.nodeOutsideLayer,
                "data-duplicate-cross-channel-count": diagnostics.duplicateCrossChannel,
                "data-canonical-canvas-width": isCanonicalMode
                  ? graph.worldWidth
                  : "",
                "data-canonical-canvas-height": isCanonicalMode
                  ? graph.worldHeight
                  : "",
                "data-canonical-core-node-count": isCanonicalMode
                  ? graph.nodes.length
                  : "",
                "data-canonical-edge-count": isCanonicalMode
                  ? CANONICAL_EDGES.length
                  : "",
                "data-canonical-disconnected-source-count": isCanonicalMode
                  ? disconnectedSourceCount
                  : "",
                "data-canonical-disconnected-target-count": isCanonicalMode
                  ? disconnectedTargetCount
                  : "",
                "data-canonical-excessive-bend-count": isCanonicalMode
                  ? excessiveBendCount
                  : "",
                "data-canonical-geometry-violation-count": isCanonicalMode
                  ? canonicalViolationCount
                  : "",
                "data-canonical-shared-bus-duplicate-count": isCanonicalMode
                  ? CANONICAL_GEOMETRY.sharedBusDuplicate
                  : "",
              }}
            >
              <BusinessLayerBackground
                layers={graph.layers}
                worldWidth={graph.worldWidth}
                worldHeight={graph.worldHeight}
                monochrome={isCanonicalMode}
                titleWidth={CANONICAL_LAYERS[0]?.titleArea.width}
                titleLines={Object.fromEntries(
                  CANONICAL_LAYERS.map((layer) => [
                    layer.id,
                    [layer.titleZh, ...layer.subtitleLines],
                  ]),
                )}
                canonicalStyle={CANONICAL_STYLE}
              />
              {graph.buses.map((bus) => (
                <SharedRelationBus
                  key={bus.id}
                  bus={bus}
                  monochrome={isCanonicalMode}
                  opacity={
                    !selectedId ||
                    bus.sourceEdgeIds.some((edgeId) => relatedEdges.has(edgeId))
                      ? 1
                      : 0.1
                  }
                  trunkOpacity={
                    isCanonicalMode &&
                    graph.nodes.find(
                      (node) =>
                        node.roleId ===
                        CANONICAL_BUSES.find((item) => item.id === bus.id)
                          ?.sourceRole,
                    )?.state === "DIMMED"
                      ? CANONICAL_STYLE.trace.inactive_edge_opacity
                      : 1
                  }
                  branchEdges={CANONICAL_EDGES.filter(
                    (edge) => edge.busId === bus.id,
                  )}
                  edgeOpacities={Object.fromEntries(
                    bus.sourceEdgeIds.map((edgeId) => [
                      edgeId,
                      edgeOpacity(edgeId),
                    ]),
                  )}
                  canonicalStyle={CANONICAL_STYLE}
                />
              ))}
              <g data-testid="unified-graph-edges">
                {(isCanonicalMode ? canonicalDirectEdges : routedEdges).map((edge) => {
                  const canonicalEdge = canonicalEdgeById.get(edge.id);
                  return (
                  <OrthogonalEdge
                    key={edge.id}
                    edge={edge}
                    opacity={edgeOpacity(edge.id)}
                    highlighted={relatedEdges.has(edge.id)}
                    monochrome={isCanonicalMode}
                    declaredBends={canonicalEdge?.bendCount}
                    sourceRole={canonicalEdge?.sourceRole}
                    targetRole={canonicalEdge?.targetRole}
                    canonicalStyle={CANONICAL_STYLE}
                  />
                  );
                })}
              </g>
              {isCanonicalMode
                ? CANONICAL_MARKERS.map((marker) => (
                    <CanonicalAuxiliaryMarker
                      key={marker.id}
                      marker={marker}
                      diagramStyle={CANONICAL_STYLE}
                    />
                  ))
                : null}
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
                      monochrome={isCanonicalMode}
                      subtitle={
                        node.roleId
                          ? CANONICAL_NODE_BY_ID.get(node.roleId)?.labelEn
                          : undefined
                      }
                      canonicalStyle={CANONICAL_STYLE}
                      onSelect={(id) =>
                        setSelectedId((prev) => (prev === id ? null : id))
                      }
                    />
                  ),
                )}
              </g>
            </GraphViewport>
          </div>
          {showDetails && selectedNode ? (
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
          viewportWidth={graph.worldWidth}
          viewportHeight={graph.worldHeight}
          worldWidth={graph.worldWidth}
          worldHeight={graph.worldHeight}
          monochrome={isCanonicalMode}
          onJump={(worldX, worldY) => {
            setTransform((prev) => ({
              ...prev,
              translateX: graph.worldWidth / 2 - worldX * prev.scale,
              translateY: graph.worldHeight / 2 - worldY * prev.scale,
            }));
          }}
        />
      </div>
    </div>
  );
}
