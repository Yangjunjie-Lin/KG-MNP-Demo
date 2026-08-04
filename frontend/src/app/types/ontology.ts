export interface OntologyNode {
  id: string;
  label: string;
  /** Raw local name / class code kept for data layer */
  localName: string;
  module: string;
  type: "Class" | "Individual" | string;
  x: number;
  y: number;
  definition: string;
}

export interface OntologyEdge {
  from: string;
  to: string;
  /** Raw relation code */
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
