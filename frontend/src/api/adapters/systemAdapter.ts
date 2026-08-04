import { array, bool, number, record, text } from "./guards";

export interface SystemStatusView {
  reachable: boolean;
  databaseReady: boolean;
  healthStatus: string;
  readinessStatus: string;
  apiVersion: string;
  schemaVersion: string;
  backend: string;
  neo4jRequired: boolean;
  checkedAt: string;
}

export function adaptSystemStatus(healthDto: unknown, readyDto: unknown, metaDto: unknown): SystemStatusView {
  const health = record(healthDto);
  const ready = record(readyDto);
  const meta = record(metaDto);
  return {
    reachable: text(health.status) === "ok",
    databaseReady: bool(ready.sqlite),
    healthStatus: text(health.status),
    readinessStatus: text(ready.status),
    apiVersion: text(meta.api_version),
    schemaVersion: text(meta.schema_version),
    backend: text(meta.backend),
    neo4jRequired: bool(meta.neo4j_required),
    checkedAt: text(health.time),
  };
}

export interface DashboardViewModel {
  ontology: {
    modules: number;
    classes: number;
    objectProperties: number;
    dataProperties: number;
    shapes: number;
    rules: number;
    competencyQuestions: number;
  };
  examples: number;
  exampleCaseIds: string[];
  executions: number;
  executionStates: DashboardCaseCounts;
  latestCaseStates: DashboardCaseCounts;
  pipelineSteps: Array<Record<string, unknown>>;
}

export interface DashboardCaseCounts {
  total: number;
  eligible: number;
  blocked: number;
  manualReview: number;
}

function adaptCaseCounts(value: unknown): DashboardCaseCounts {
  const counts = record(value);
  return {
    total: number(counts.total),
    eligible: number(counts.eligible),
    blocked: number(counts.blocked),
    manualReview: number(counts.manual_review),
  };
}

export function adaptDashboard(dto: unknown, examplesDto?: unknown): DashboardViewModel {
  const dashboard = record(dto);
  const ontology = record(dashboard.ontology);
  const examples = array(record(examplesDto).items);
  const exampleCaseIds = examples
    .map((item) => text(record(item).case_id))
    .filter(Boolean);
  const executionStates = adaptCaseCounts(dashboard.executions);
  const latestCaseStates = adaptCaseCounts(dashboard.latest_case_states);
  return {
    ontology: {
      modules: number(ontology.module_count),
      classes: number(ontology.class_count),
      objectProperties: number(ontology.object_property_count),
      dataProperties: number(ontology.data_property_count),
      shapes: number(ontology.shape_count),
      rules: number(ontology.rule_count),
      competencyQuestions: number(ontology.competency_question_count),
    },
    examples: examplesDto === undefined
      ? number(record(dashboard.example_cases).total)
      : exampleCaseIds.length,
    exampleCaseIds,
    executions: executionStates.total,
    executionStates,
    latestCaseStates,
    pipelineSteps: Array.isArray(dashboard.pipeline_steps)
      ? dashboard.pipeline_steps.map(record)
      : [],
  };
}
