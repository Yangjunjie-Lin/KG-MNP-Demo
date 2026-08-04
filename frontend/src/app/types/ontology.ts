import type { OntologyLaneId } from "../ontology/ontologyGraphTypes";

export interface OntologyNode {
  id: string;
  label: string;
  localName: string;
  module: string;
  type: "Class" | "Individual" | string;
  definition: string;
}

export interface PositionedOntologyNode extends OntologyNode {
  laneId: OntologyLaneId;
  x: number;
  y: number;
  width: number;
  height: number;
  order: number;
  overview: boolean;
  technicalSupport: boolean;
}

export interface OntologyEdge {
  from: string;
  to: string;
  relation: string;
  label: string;
}

export interface OntologyModule {
  id: string;
  label: string;
  description: string;
}

export interface OntologyKeyPath {
  id: string;
  sourceClass: string;
  predicate: string;
  targetClass: string;
  existsInRdf: boolean;
}
