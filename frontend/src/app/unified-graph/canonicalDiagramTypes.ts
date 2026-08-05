import type { BusinessLayerId, BusinessRoleId } from "./graphTypes";

export type CanonicalPort = "LEFT" | "RIGHT" | "TOP" | "BOTTOM";

export interface CanonicalCanvas {
  width: number;
  height: number;
  view_box: string;
  preserve_aspect_ratio: string;
}

export interface CanonicalLayerTitleArea {
  x: number;
  width: number;
}

export interface CanonicalBusinessLayer {
  id: BusinessLayerId;
  order: number;
  titleZh: string;
  subtitleLines: string[];
  x: number;
  y: number;
  width: number;
  height: number;
  titleArea: CanonicalLayerTitleArea;
  contentX: number;
}

export type CanonicalNodeStyleKey = "ordinary" | "safety_check";

export interface CanonicalBusinessNode {
  id: BusinessRoleId;
  layerId: BusinessLayerId;
  labelZh: string;
  labelEn: string;
  x: number;
  y: number;
  width: number;
  height: number;
  styleKey: CanonicalNodeStyleKey;
}

export interface CanonicalNodeTextStyle {
  zh_font_size: number;
  zh_font_weight: number;
  en_font_size: number;
  en_font_weight: number;
}

export interface CanonicalSafetyCheckStyle {
  node_border_width: number;
  font_weight: number;
  zh_font_size: number;
  en_font_size: number;
}

export interface CanonicalTraceOverlayStyle {
  pass: string;
  block: string;
  warning: string;
  inactive_node_opacity: number;
  active_node_opacity: number;
  inactive_edge_opacity: number;
  active_edge_opacity: number;
}

export interface CanonicalDiagramStyle {
  canvas_background: string;
  layer_background: string;
  layer_border: string;
  layer_border_width: number;
  layer_separator_width: number;
  node_background: string;
  node_border: string;
  node_border_width: number;
  node_radius: number;
  primary_text: string;
  secondary_text: string;
  edge: string;
  edge_width: number;
  arrow_fill: string;
  label_background: string;
  label_border: string;
  shadow: "none";
  gradient: "none";
  node_text: CanonicalNodeTextStyle;
  safety_check: CanonicalSafetyCheckStyle;
  trace: CanonicalTraceOverlayStyle;
}

export interface CanonicalStructuralEdge {
  id: string;
  fromRole: BusinessRoleId;
  toRole: BusinessRoleId;
  sourceRole: BusinessRoleId;
  targetRole: BusinessRoleId;
  sourcePort: CanonicalPort;
  targetPort: CanonicalPort;
  labelZh: string;
  path: string;
  labelX: number;
  labelY: number;
  bendCount: number;
  auxiliaryLabelZh?: string;
  busId?: string;
}

export interface CanonicalSharedBus {
  id: string;
  sourceRole: BusinessRoleId;
  sourcePort: CanonicalPort;
  path: string;
  bendCount: number;
  edgeIds: string[];
}

export interface CanonicalMarkerArrow {
  id: string;
  path: string;
  targetRole: BusinessRoleId;
  targetPort: CanonicalPort;
  markerEnd: boolean;
}

export interface CanonicalMarkerStyle {
  stroke: string;
  strokeWidth: number;
  strokeDasharray: string;
  fill: string;
}

export interface CanonicalAuxiliaryMarker {
  id: string;
  type: string;
  anchorRole: BusinessRoleId;
  rect: {
    x: number;
    y: number;
    width: number;
    height: number;
  };
  arrows: CanonicalMarkerArrow[];
  labelZh: string;
  labelX: number;
  labelY: number;
  style: CanonicalMarkerStyle;
}

export interface CanonicalBusinessDiagramConfig {
  $schema?: string;
  version: "2.0";
  view_id: "KG_MNP_CANONICAL_BUSINESS_DIAGRAM";
  canvas: CanonicalCanvas;
  style: CanonicalDiagramStyle;
  layers: CanonicalBusinessLayer[];
  nodes: CanonicalBusinessNode[];
  buses: CanonicalSharedBus[];
  edges: CanonicalStructuralEdge[];
  markers: CanonicalAuxiliaryMarker[];
}

export type CanonicalDiagramConfig = CanonicalBusinessDiagramConfig;
