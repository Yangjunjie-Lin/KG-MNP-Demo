import { OntologyEdgePath } from "./OntologyEdgePath";
import { OntologyLaneBackground } from "./OntologyLaneBackground";
import { OntologyNodeCard } from "./OntologyNodeCard";
import type {
  LaneGeometry,
  OntologyGeometryDiagnostics,
  RoutedOntologyEdge,
} from "../../ontology/ontologyGraphTypes";
import type { PositionedOntologyNode } from "../../types/ontology";

interface OntologyLaneGraphProps {
  width: number;
  height: number;
  contentRight: number;
  lanes: LaneGeometry[];
  nodes: PositionedOntologyNode[];
  edges: RoutedOntologyEdge[];
  diagnostics: OntologyGeometryDiagnostics;
  unmappedNodeCount: number;
  runtimeNodeCount: number;
  runtimeEdgeCount: number;
  renderedNodeCount: number;
  renderedEdgeCount: number;
  nodeLabel: (node: PositionedOntologyNode) => string;
  nodeOpacity: (nodeId: string) => number;
  edgeOpacity: (edgeId: string) => number;
  edgeHighlighted: (edgeId: string) => boolean;
  selectedNodeId: string | null;
  onSelectNode: (nodeId: string | null) => void;
  onSelectEdge?: (edgeId: string | null) => void;
  testId?: string;
}

export function OntologyLaneGraph({
  width,
  height,
  contentRight,
  lanes,
  nodes,
  edges,
  diagnostics,
  unmappedNodeCount,
  runtimeNodeCount,
  runtimeEdgeCount,
  renderedNodeCount,
  renderedEdgeCount,
  nodeLabel,
  nodeOpacity,
  edgeOpacity,
  edgeHighlighted,
  selectedNodeId,
  onSelectNode,
  onSelectEdge,
  testId = "ontology-overview-graph",
}: OntologyLaneGraphProps) {
  return (
    <svg
      data-testid={testId}
      data-geometry-violation-count={diagnostics.total}
      data-edge-through-node-count={diagnostics.edgeThroughNode}
      data-segment-overlap-count={diagnostics.segmentOverlap}
      data-label-inside-node-count={diagnostics.labelInsideNode}
      data-node-outside-lane-count={diagnostics.nodeOutsideLane}
      data-duplicate-cross-channel-count={diagnostics.duplicateCrossChannel}
      data-unmapped-node-count={unmappedNodeCount}
      data-overview-width={width}
      data-runtime-node-count={runtimeNodeCount}
      data-runtime-edge-count={runtimeEdgeCount}
      data-rendered-node-count={renderedNodeCount}
      data-rendered-edge-count={renderedEdgeCount}
      width={width}
      height={height}
      viewBox={`0 0 ${width} ${height}`}
      style={{ width, height, minWidth: width }}
      aria-label="本体关系图"
    >
      <defs>
        <marker
          id="arrow-ontology"
          markerWidth="7"
          markerHeight="7"
          refX="6"
          refY="2.5"
          orient="auto"
          markerUnits="strokeWidth"
        >
          <path d="M0,0 L0,5 L7,2.5 z" fill="context-stroke" />
        </marker>
      </defs>

      <OntologyLaneBackground
        lanes={lanes}
        contentRight={contentRight}
        height={height}
        width={width}
      />

      <g data-testid="ontology-edges">
        {edges.map((edge) => (
          <OntologyEdgePath
            key={edge.id}
            edge={edge}
            opacity={edgeOpacity(edge.id)}
            highlighted={edgeHighlighted(edge.id)}
            onSelect={(edgeId) => onSelectEdge?.(edgeId)}
          />
        ))}
      </g>

      <g data-testid="ontology-nodes">
        {nodes.map((node) => (
          <OntologyNodeCard
            key={node.id}
            node={node}
            label={nodeLabel(node)}
            selected={selectedNodeId === node.id}
            opacity={nodeOpacity(node.id)}
            onSelect={(nodeId) => {
              if (!nodeId) {
                onSelectNode(null);
                return;
              }
              onSelectNode(selectedNodeId === nodeId ? null : nodeId);
            }}
          />
        ))}
      </g>
    </svg>
  );
}
