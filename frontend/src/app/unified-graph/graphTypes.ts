export type BusinessLayerId =
  | "USER_IDENTITY"
  | "ACCOUNT_BILLING"
  | "SERVICE_OFFERING"
  | "PORTABILITY_PROCESS"
  | "QUALIFICATION_COMPLIANCE";

export type BusinessRoleId =
  | "USER"
  | "VERIFICATION"
  | "MOBILE_NUMBER_IDENTITY"
  | "OPERATOR_CURRENT"
  | "ACCOUNT"
  | "BILL"
  | "PAYMENT"
  | "TARIFF_PLAN"
  | "CONTRACT"
  | "BROADBAND"
  | "VALUE_ADDED_SERVICE"
  | "USER_RIGHT"
  | "PORT_REQUEST"
  | "MOBILE_NUMBER_PORT"
  | "OPERATOR_DONOR"
  | "OPERATOR_RECIPIENT"
  | "PORT_STEP"
  | "AUTH_CODE"
  | "EXCEPTION_EVENT"
  | "IMPACT"
  | "ELIGIBILITY_CONDITION"
  | "REGULATION_RULE"
  | "SAFETY_CHECK"
  | "BLOCK_REASON"
  | "REMEDIATION_ACTION"
  | "EVIDENCE"
  | "OPERATOR_EVIDENCE";

export type UnifiedGraphMode =
  | "BUSINESS_OVERVIEW"
  | "COMPLETE_ONTOLOGY"
  | "ASSESSMENT_TRACE"
  | "HISTORY_TRACE"
  | "IMPORT_PREVIEW";

export type NodeVisualKind = "CORE_ROLE" | "EXTENSION" | "PROJECTION";

export type EdgePresentationType =
  | "STRUCTURAL"
  | "ONTOLOGY"
  | "TRACE"
  | "IMPORT";

export type NodeState =
  | "DEFAULT"
  | "ACTIVE"
  | "PASS"
  | "BLOCK"
  | "WARN"
  | "CURRENT"
  | "DIMMED"
  | "ADDED"
  | "MODIFIED"
  | "CONFLICT";

export interface Point {
  x: number;
  y: number;
}

export interface Rect {
  x: number;
  y: number;
  width: number;
  height: number;
}

export interface GraphTransformState {
  scale: number;
  translateX: number;
  translateY: number;
}

export interface DragState {
  pointerId: number;
  startClientX: number;
  startClientY: number;
  startTranslateX: number;
  startTranslateY: number;
  moved: boolean;
}

export interface VisualProjection {
  projectionId: string;
  sourceNodeId: string;
  roleId: BusinessRoleId | null;
  layerId: BusinessLayerId;
  kind: NodeVisualKind;
  labelZh: string;
  localName?: string;
  mappedCount?: number;
  extensionCount?: number;
  state?: NodeState;
  x: number;
  y: number;
  width: number;
  height: number;
  order: number;
}

export interface ProjectedGraphEdge {
  id: string;
  sourceProjectionId: string;
  targetProjectionId: string;
  relationId: string;
  labelZh: string;
  sourceEdgeIds: string[];
  presentationType: EdgePresentationType;
  state?: NodeState;
}

export interface CollapsedProjectedEdge {
  id: string;
  from: string;
  to: string;
  edges: ProjectedGraphEdge[];
}

export interface RoutedProjectedEdge {
  id: string;
  from: string;
  to: string;
  edges: ProjectedGraphEdge[];
  points: Point[];
  path: string;
  labelX: number;
  labelY: number;
  labelZh: string;
  kind: "INTRA_LAYER" | "CROSS_LAYER";
  channel: number;
  presentationType: EdgePresentationType;
  state?: NodeState;
}

export interface LayerGeometry {
  id: BusinessLayerId;
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

export interface SharedEdgeBus {
  id: string;
  trunkPath: string;
  branchPaths: Record<string, string>;
  sourceEdgeIds: string[];
  labelZh: string;
  labelX: number;
  labelY: number;
}

export interface NodePorts {
  left: Point;
  right: Point;
  top: Point;
  bottom: Point;
}

export interface PortAssignment {
  edgeId: string;
  nodeId: string;
  side: "left" | "right" | "top" | "bottom";
  offset: number;
}

export interface GeometryViolation {
  kind: string;
  message: string;
  details?: Record<string, unknown>;
}

export interface GraphGeometryDiagnostics {
  total: number;
  edgeThroughNode: number;
  segmentOverlap: number;
  labelInsideNode: number;
  nodeOutsideLayer: number;
  duplicateCrossChannel: number;
  sharedBusDuplicated: number;
  danglingEdge: number;
  duplicateNodeId: number;
}

export interface GraphProjectionResult {
  mode: UnifiedGraphMode;
  layers: LayerGeometry[];
  nodes: VisualProjection[];
  edges: ProjectedGraphEdge[];
  collapsedEdges: CollapsedProjectedEdge[];
  buses: SharedEdgeBus[];
  worldWidth: number;
  worldHeight: number;
  contentRight: number;
  unmappedNodeIds: string[];
  danglingEdges: ProjectedGraphEdge[];
  silentlyDroppedNodes: string[];
  silentlyDroppedEdges: string[];
  extensionNodeCount: number;
  coreRoleCount: number;
}

export interface GraphBuildInputNode {
  id: string;
  label?: string;
  localName?: string;
  module?: string;
  type?: string;
  businessLane?: BusinessLayerId;
  canonicalRole?: BusinessRoleId | null;
  state?: NodeState;
}

export interface GraphBuildInputEdge {
  id?: string;
  from: string;
  to: string;
  relation: string;
  label?: string;
  presentationType?: EdgePresentationType;
  state?: NodeState;
}
