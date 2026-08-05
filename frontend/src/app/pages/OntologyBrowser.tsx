import { useEffect, useMemo, useState } from "react";
import { ApiErrorState, EmptyState, PageSkeleton } from "../components/dataStates";
import { OntologyGraphToolbar } from "../components/ontology/OntologyGraphToolbar";
import { OntologyLaneGraph } from "../components/ontology/OntologyLaneGraph";
import { OntologyNodeDetails } from "../components/ontology/OntologyNodeDetails";
import {
  ontologyClassLabels,
  ontologyRelationLabels,
  translateOrUnknown,
  ui,
} from "../i18n/zh-CN";
import {
  ONTOLOGY_VIEW_LABELS,
  ONTOLOGY_LANE_LABELS,
} from "../ontology/ontologyLaneConfig";
import {
  summarizeGeometryViolations,
  validateGraphGeometry,
} from "../ontology/ontologyGeometry";
import { layoutOntologyGraph } from "../ontology/ontologyLayout";
import {
  buildOntologyOverview,
  collapseParallelEdges,
  getDetailEdgesForLane,
  getDetailNodesForLane,
} from "../ontology/ontologyOverviewBuilder";
import { routeOntologyEdges } from "../ontology/orthogonalRouter";
import type { OntologyLaneId, OntologyViewMode } from "../ontology/ontologyGraphTypes";
import { useOntology } from "../query/hooks/useAppQueries";
import type { OntologyEdge, OntologyNode, PositionedOntologyNode } from "../types/ontology";
import { cn } from "../utils/cn";

function containsChinese(value: string): boolean {
  return /[\u3400-\u9fff]/u.test(value);
}

function nodeDisplayLabel(node: OntologyNode): string {
  if (containsChinese(node.label)) return node.label;
  return translateOrUnknown(
    ontologyClassLabels,
    node.localName || node.id,
    ui.unknownOntologyClass,
  );
}

function edgeDisplayLabel(edge: OntologyEdge): string {
  if (containsChinese(edge.label)) return edge.label;
  return translateOrUnknown(
    ontologyRelationLabels,
    edge.relation,
    ui.unknownOntologyRelation,
  );
}

const VIEW_MODES: OntologyViewMode[] = [
  "OVERVIEW",
  "USER_IDENTITY",
  "ACCOUNT_BILLING",
  "SERVICE_OFFERING",
  "PORTABILITY_PROCESS",
  "QUALIFICATION_COMPLIANCE",
];

export function OntologyBrowser() {
  const query = useOntology();
  const [selectedNodeId, setSelectedNodeId] = useState<string | null>(null);
  const [selectedEdgeId, setSelectedEdgeId] = useState<string | null>(null);
  const [viewMode, setViewMode] = useState<OntologyViewMode>("OVERVIEW");
  const [searchTerm, setSearchTerm] = useState("");

  const data = query.data;
  const nodes = data?.nodes ?? [];
  const edges = data?.edges ?? [];

  const overview = useMemo(
    () => buildOntologyOverview(nodes, edges),
    [nodes, edges],
  );

  const activeLaneId: OntologyLaneId | null =
    viewMode === "OVERVIEW" ? null : viewMode;

  const visibleSourceNodes = useMemo(() => {
    if (!activeLaneId) return overview.overviewNodes;
    return getDetailNodesForLane(activeLaneId, overview.allLaneNodes);
  }, [activeLaneId, overview]);

  const visibleSourceEdges = useMemo(() => {
    if (!activeLaneId) return overview.overviewEdges;
    return getDetailEdgesForLane(activeLaneId, visibleSourceNodes, edges);
  }, [activeLaneId, visibleSourceNodes, edges, overview.overviewEdges]);

  const collapsedEdges = useMemo(() => {
    if (viewMode === "OVERVIEW") return overview.collapsedEdges;
    return collapseParallelEdges(visibleSourceEdges);
  }, [viewMode, overview.collapsedEdges, visibleSourceEdges]);

  const layout = useMemo(
    () =>
      layoutOntologyGraph(nodes, collapsedEdges, {
        overview: viewMode === "OVERVIEW",
        laneFilter: activeLaneId ?? undefined,
        allEdges: edges,
      }),
    [nodes, collapsedEdges, viewMode, activeLaneId, edges],
  );

  const routedEdges = useMemo(
    () =>
      routeOntologyEdges({
        nodes: layout.nodes,
        collapsedEdges,
        lanes: layout.lanes,
        contentRight: layout.contentRight,
      }),
    [layout, collapsedEdges],
  );

  const geometryViolations = useMemo(
    () =>
      validateGraphGeometry({
        nodes: layout.nodes,
        edges: routedEdges,
        lanes: layout.lanes,
        contentRight: layout.contentRight,
      }),
    [layout, routedEdges],
  );

  const geometryDiagnostics = useMemo(
    () => summarizeGeometryViolations(geometryViolations),
    [geometryViolations],
  );

  useEffect(() => {
    if (geometryViolations.length === 0) return;
    console.error("[ontology-layout] runtime geometry violations", {
      diagnostics: geometryDiagnostics,
      violations: geometryViolations,
    });
  }, [geometryDiagnostics, geometryViolations]);

  const adjacency = useMemo(() => {
    const map = new Map<string, Set<string>>();
    const ensure = (id: string) => {
      if (!map.has(id)) map.set(id, new Set());
      return map.get(id)!;
    };
    for (const edge of visibleSourceEdges) {
      ensure(edge.from).add(edge.to);
      ensure(edge.to).add(edge.from);
    }
    return map;
  }, [visibleSourceEdges]);

  const nodeMap = useMemo(
    () => new Map(layout.nodes.map((node) => [node.id, node])),
    [layout.nodes],
  );

  const selectedNode = selectedNodeId
    ? (nodeMap.get(selectedNodeId) ?? null)
    : null;

  const relatedNodeIds = useMemo(() => {
    if (!selectedNodeId) return new Set<string>();
    const neighbors = adjacency.get(selectedNodeId) ?? new Set<string>();
    return new Set([selectedNodeId, ...neighbors]);
  }, [selectedNodeId, adjacency]);

  const relatedEdgeIds = useMemo(() => {
    if (!selectedNodeId) return new Set<string>();
    return new Set(
      routedEdges
        .filter(
          (edge) =>
            edge.from === selectedNodeId || edge.to === selectedNodeId,
        )
        .map((edge) => edge.id),
    );
  }, [selectedNodeId, routedEdges]);

  const normalizedSearch = searchTerm.trim();
  const searchMatches = useMemo(() => {
    if (!normalizedSearch) return null;
    const matched = new Set<string>();
    for (const node of layout.nodes) {
      const label = nodeDisplayLabel(node);
      const laneLabel = ONTOLOGY_LANE_LABELS[node.laneId];
      if (label.includes(normalizedSearch) || laneLabel.includes(normalizedSearch)) {
        matched.add(node.id);
      }
    }
    return matched;
  }, [layout.nodes, normalizedSearch]);

  const searchNeighborIds = useMemo(() => {
    if (!searchMatches) return null;
    const neighbors = new Set<string>();
    for (const id of searchMatches) {
      for (const neighbor of adjacency.get(id) ?? []) {
        if (!searchMatches.has(neighbor)) neighbors.add(neighbor);
      }
    }
    return neighbors;
  }, [searchMatches, adjacency]);

  const nodeOpacity = (nodeId: string): number => {
    if (searchMatches) {
      if (searchMatches.has(nodeId)) return 1;
      if (searchNeighborIds?.has(nodeId)) return 0.65;
      return 0.12;
    }
    if (selectedNodeId) {
      return relatedNodeIds.has(nodeId) ? 1 : 0.18;
    }
    return 1;
  };

  const edgeOpacity = (edgeId: string): number => {
    if (selectedNodeId) {
      return relatedEdgeIds.has(edgeId) ? 1 : 0.08;
    }
    if (searchMatches) {
      const edge = routedEdges.find((item) => item.id === edgeId);
      if (!edge) return 0.12;
      if (searchMatches.has(edge.from) || searchMatches.has(edge.to)) return 1;
      return 0.12;
    }
    return 1;
  };

  const edgeHighlighted = (edgeId: string): boolean =>
    Boolean(selectedNodeId && relatedEdgeIds.has(edgeId)) ||
    selectedEdgeId === edgeId;

  const relatedDetailNodes: PositionedOntologyNode[] = useMemo(() => {
    if (!selectedNodeId) return [];
    return [...(adjacency.get(selectedNodeId) ?? [])]
      .map((id) => nodeMap.get(id))
      .filter((node): node is PositionedOntologyNode => Boolean(node));
  }, [selectedNodeId, adjacency, nodeMap]);

  useEffect(() => {
    const onKeyDown = (event: KeyboardEvent) => {
      if (event.key === "Escape") {
        setSelectedNodeId(null);
        setSelectedEdgeId(null);
      }
    };
    window.addEventListener("keydown", onKeyDown);
    return () => window.removeEventListener("keydown", onKeyDown);
  }, []);

  if (query.isLoading) return <PageSkeleton />;
  if (query.isError) {
    return <ApiErrorState error={query.error} onRetry={() => void query.refetch()} />;
  }
  if (!data || nodes.length === 0) return <EmptyState message="暂无本体图数据" />;

  const nav = (
    <div className="space-y-0.5">
      <div className="mb-2 px-1 text-[10px] font-semibold tracking-wider text-slate-400">
        {ui.ontologyViewNav}
      </div>
      {VIEW_MODES.map((mode) => (
        <button
          key={mode}
          type="button"
          onClick={() => {
            setViewMode(mode);
            setSelectedNodeId(null);
            setSelectedEdgeId(null);
          }}
          className={cn(
            "mb-0.5 w-full rounded px-2 py-1.5 text-left text-xs transition-colors",
            viewMode === mode
              ? "bg-blue-50 font-medium text-blue-700"
              : "text-slate-600 hover:bg-slate-50",
          )}
        >
          {ONTOLOGY_VIEW_LABELS[mode]}
        </button>
      ))}
    </div>
  );

  return (
    <div className="flex h-full min-w-0 flex-col overflow-x-hidden lg:flex-row">
      <aside className="hidden w-[190px] flex-shrink-0 overflow-y-auto border-r border-slate-200 bg-white p-3 lg:block">
        {nav}
      </aside>

      <div className="border-b border-slate-200 bg-white p-3 lg:hidden">
        <label className="block text-xs text-slate-500">
          {ui.ontologyViewNav}
          <select
            className="mt-1 w-full rounded border border-slate-200 px-2 py-1.5 text-sm text-slate-700"
            value={viewMode}
            onChange={(event) => {
              setViewMode(event.target.value as OntologyViewMode);
              setSelectedNodeId(null);
              setSelectedEdgeId(null);
            }}
          >
            {VIEW_MODES.map((mode) => (
              <option key={mode} value={mode}>
                {ONTOLOGY_VIEW_LABELS[mode]}
              </option>
            ))}
          </select>
        </label>
      </div>

      <section className="relative min-w-0 flex-1 overflow-auto bg-slate-50">
        <OntologyGraphToolbar
          searchTerm={searchTerm}
          onSearchChange={setSearchTerm}
          overviewRelationCount={
            viewMode === "OVERVIEW"
              ? overview.whitelistRelationCount
              : visibleSourceEdges.length
          }
          secondaryRelationCount={
            viewMode === "OVERVIEW" ? overview.secondaryRelationCount : 0
          }
          unmappedCount={overview.unmappedNodes.length}
          technicalAdjacencyCount={overview.technicalAdjacencyCount}
          technicalFallbackCount={overview.technicalFallbackCount}
          geometryViolationCount={geometryDiagnostics.total}
          isFetching={query.isFetching}
        />
        <div className="overflow-auto p-3 pt-2">
          <OntologyLaneGraph
            width={layout.width}
            height={layout.height}
            contentRight={layout.contentRight}
            lanes={layout.lanes}
            nodes={layout.nodes}
            edges={routedEdges}
            diagnostics={geometryDiagnostics}
            unmappedNodeCount={overview.unmappedNodes.length}
            runtimeNodeCount={
              viewMode === "OVERVIEW"
                ? overview.overviewNodes.length
                : visibleSourceNodes.length
            }
            runtimeEdgeCount={collapsedEdges.length}
            renderedNodeCount={layout.nodes.length}
            renderedEdgeCount={routedEdges.length}
            nodeLabel={nodeDisplayLabel}
            nodeOpacity={nodeOpacity}
            edgeOpacity={edgeOpacity}
            edgeHighlighted={edgeHighlighted}
            selectedNodeId={selectedNodeId}
            onSelectNode={setSelectedNodeId}
            onSelectEdge={setSelectedEdgeId}
            testId={
              viewMode === "OVERVIEW"
                ? "ontology-overview-graph"
                : `ontology-lane-graph-${viewMode}`
            }
          />
        </div>
      </section>

      <aside className="w-full flex-shrink-0 overflow-y-auto border-t border-slate-200 bg-white p-4 lg:w-[280px] lg:border-l lg:border-t-0">
        <OntologyNodeDetails
          node={selectedNode}
          edges={visibleSourceEdges}
          nodeLabel={nodeDisplayLabel}
          edgeLabel={edgeDisplayLabel}
          relatedNodes={relatedDetailNodes}
          onClose={() => {
            setSelectedNodeId(null);
            setSelectedEdgeId(null);
          }}
        />
      </aside>
    </div>
  );
}
