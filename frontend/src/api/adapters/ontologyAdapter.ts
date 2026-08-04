import type {
  OntologyEdge,
  OntologyKeyPath,
  OntologyModule,
  OntologyNode,
} from "../../app/types/ontology";
import { array, bool, number, record, text } from "./guards";

export interface OntologyViewModel {
  nodes: OntologyNode[];
  edges: OntologyEdge[];
  modules: OntologyModule[];
  keyPaths: OntologyKeyPath[];
  stats: Record<string, unknown>;
}

export interface OntologySummaryViewModel {
  moduleCount: number;
  allModuleCount: number;
  classCount: number;
  objectPropertyCount: number;
  dataPropertyCount: number;
  runtimeFiles: string[];
}

export interface OntologyClassViewModel {
  iri: string;
  localName: string;
  label: string;
  module: string;
  type: string;
}

export interface OntologyPropertyViewModel {
  iri: string;
  localName: string;
  label: string;
  module: string;
  domain: string[];
  range: string[];
}

export interface OntologyPropertiesViewModel {
  objectProperties: OntologyPropertyViewModel[];
  dataProperties: OntologyPropertyViewModel[];
}

export interface OntologyGraphViewModel {
  nodes: OntologyNode[];
  edges: OntologyEdge[];
}

function chineseLabel(value: unknown): string {
  const label = text(value);
  return /[\u3400-\u9fff]/u.test(label) ? label : "";
}

export function adaptOntologySummary(dto: unknown): OntologySummaryViewModel {
  const value = record(dto);
  return {
    moduleCount: number(value.module_count),
    allModuleCount: number(value.module_count_all, number(value.module_count)),
    classCount: number(value.class_count),
    objectPropertyCount: number(value.object_property_count),
    dataPropertyCount: number(value.data_property_count),
    runtimeFiles: array(value.runtime_files).map((item) => text(item)),
  };
}

export function adaptOntologyModules(dto: unknown): OntologyModule[] {
  return array(record(dto).items).map((raw) => {
    const module = record(raw);
    return {
      id: text(module.module),
      label: text(module.label_zh),
      description: text(module.description),
    } satisfies OntologyModule;
  });
}

export function adaptOntologyClasses(dto: unknown): OntologyClassViewModel[] {
  return array(record(dto).items).map((raw) => {
    const item = record(raw);
    return {
      iri: text(item.iri),
      localName: text(item.local_name),
      label: chineseLabel(item.label),
      module: text(item.module),
      type: text(item.type, "Class"),
    };
  });
}

function adaptProperty(value: unknown): OntologyPropertyViewModel {
  const item = record(value);
  return {
    iri: text(item.iri),
    localName: text(item.local_name),
    label: chineseLabel(item.label_zh) || chineseLabel(item.label),
    module: text(item.module),
    domain: array(item.domain).map((entry) => text(entry)),
    range: array(item.range).map((entry) => text(entry)),
  };
}

export function adaptOntologyProperties(dto: unknown): OntologyPropertiesViewModel {
  const value = record(dto);
  return {
    objectProperties: array(value.object_properties).map(adaptProperty),
    dataProperties: array(value.data_properties).map(adaptProperty),
  };
}

export function adaptOntologyGraph(dto: unknown, propertiesDto?: unknown): OntologyGraphViewModel {
  const graph = record(dto);
  const properties = adaptOntologyProperties(propertiesDto);
  const propertyLabels = new Map(
    properties.objectProperties
      .filter((property) => property.localName && property.label)
      .map((property) => [property.localName, property.label]),
  );
  return {
    nodes: array(graph.nodes).map((raw) => {
      const node = record(raw);
      return {
        id: text(node.id),
        label: chineseLabel(node.label),
        localName: text(node.local_name),
        module: text(node.module, "CORE"),
        type: text(node.type, "Class"),
        definition: "",
      } satisfies OntologyNode;
    }),
    edges: array(graph.edges).map((raw) => {
      const edge = record(raw);
      const relation = text(edge.predicate);
      return {
        from: text(edge.source),
        to: text(edge.target),
        relation,
        label: propertyLabels.get(relation) ?? "",
      } satisfies OntologyEdge;
    }),
  };
}

export function adaptOntologyView(dto: unknown, propertiesDto?: unknown): OntologyViewModel {
  const view = record(dto);
  const graph = adaptOntologyGraph(view.graph, propertiesDto);
  return {
    nodes: graph.nodes,
    edges: graph.edges,
    modules: adaptOntologyModules({ items: view.modules }),
    keyPaths: array(view.key_paths).map((raw) => {
      const path = record(raw);
      return {
        id: text(path.id),
        sourceClass: text(path.source_class),
        predicate: text(path.predicate),
        targetClass: text(path.target_class),
        existsInRdf: bool(path.exists_in_rdf),
      } satisfies OntologyKeyPath;
    }),
    stats: record(view.stats),
  };
}
