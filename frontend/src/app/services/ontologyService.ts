// 后续在这里连接本地 FastAPI
import type { OntologyEdge, OntologyModule, OntologyNode } from "../types/ontology";
import {
  mockOntologyEdges,
  mockOntologyModules,
  mockOntologyNodes,
} from "../data/mockOntology";

export async function getNodes(): Promise<OntologyNode[]> {
  return Promise.resolve(mockOntologyNodes);
}

export async function getEdges(): Promise<OntologyEdge[]> {
  return Promise.resolve(mockOntologyEdges);
}

export async function getModules(): Promise<OntologyModule[]> {
  return Promise.resolve(mockOntologyModules);
}
