import { OntologyEdgePath } from "./OntologyEdgePath";
import { OntologyLaneBackground } from "./OntologyLaneBackground";
import { OntologyNodeCard } from "./OntologyNodeCard";
import type {
  LaneGeometry,
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
