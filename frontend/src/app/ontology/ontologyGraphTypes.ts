import type { OntologyEdge, OntologyNode } from "../types/ontology";

export type OntologyViewMode =
  | "OVERVIEW"
  | "USER_IDENTITY"
  | "ACCOUNT_BILLING"
  | "SERVICE_OFFERING"
  | "PORTABILITY_PROCESS"
  | "QUALIFICATION_COMPLIANCE";

export type OntologyLaneId =
  | "USER_IDENTITY"
  | "ACCOUNT_BILLING"
  | "SERVICE_OFFERING"
  | "PORTABILITY_PROCESS"
  | "QUALIFICATION_COMPLIANCE";

export interface Point {
  x: number;
  y: number;
}

export interface NodePorts {
  left: Point;
  right: Point;
  top: Point;
  bottom: Point;
}

export interface CollapsedOntologyEdge {
  id: string;
  from: string;
  to: string;
  relations: OntologyEdge[];
}

export interface RoutedOntologyEdge {
  id: string;
  from: string;
  to: string;
  relations: OntologyEdge[];
  points: Point[];
  path: string;
  labelX: number;
  labelY: number;
  kind: "INTRA_LANE" | "CROSS_LANE";
  channel: number;
}

export interface LaneGeometry {
  id: OntologyLaneId;
  label: string;
  x: number;
  y: number;
  width: number;
  height: number;
  contentX: number;
  contentY: number;
  contentWidth: number;
  contentHeight: number;
  routeBottomY: number;
}

export interface OntologyOverviewGraph {
  overviewNodes: OntologyNode[];
  overviewEdges: OntologyEdge[];
  collapsedEdges: CollapsedOntologyEdge[];
  allLaneNodes: Map<OntologyLaneId, OntologyNode[]>;
  unmappedNodes: OntologyNode[];
  secondaryRelationCount: number;
  whitelistRelationCount: number;
}

export interface OntologyLayoutResult {
  nodes: import("../types/ontology").PositionedOntologyNode[];
  lanes: LaneGeometry[];
  width: number;
  height: number;
  contentRight: number;
}

export interface GeometryViolation {
  kind: string;
  message: string;
  details?: Record<string, unknown>;
}
