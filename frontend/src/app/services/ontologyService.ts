import { apiGet } from "../../api/client";
import {
  adaptOntologyClasses,
  adaptOntologyGraph,
  adaptOntologyModules,
  adaptOntologyProperties,
  adaptOntologySummary,
  adaptOntologyView,
} from "../../api/adapters/ontologyAdapter";

export async function getOntologyView(signal?: AbortSignal) {
  const [view, properties] = await Promise.all([
    apiGet("/api/v1/views/ontology", { signal }),
    apiGet("/api/v1/ontology/properties", { signal }),
  ]);
  return adaptOntologyView(view, properties);
}

export const getOntology = getOntologyView;

export async function getOntologySummary(signal?: AbortSignal) {
  return adaptOntologySummary(
    await apiGet("/api/v1/ontology/summary", { signal }),
  );
}

export async function getOntologyModules(signal?: AbortSignal) {
  return adaptOntologyModules(
    await apiGet("/api/v1/ontology/modules", { signal }),
  );
}

export async function getOntologyClasses(signal?: AbortSignal) {
  return adaptOntologyClasses(
    await apiGet("/api/v1/ontology/classes", { signal }),
  );
}

export async function getOntologyProperties(signal?: AbortSignal) {
  return adaptOntologyProperties(
    await apiGet("/api/v1/ontology/properties", { signal }),
  );
}

export async function getOntologyGraph(module?: string, signal?: AbortSignal) {
  const [graph, properties] = await Promise.all([
    apiGet("/api/v1/ontology/graph", { query: { module }, signal }),
    apiGet("/api/v1/ontology/properties", { signal }),
  ]);
  return adaptOntologyGraph(graph, properties);
}

export async function getNodes(signal?: AbortSignal) {
  return (await getOntology(signal)).nodes;
}

export async function getEdges(signal?: AbortSignal) {
  return (await getOntology(signal)).edges;
}

export async function getModules(signal?: AbortSignal) {
  return getOntologyModules(signal);
}
