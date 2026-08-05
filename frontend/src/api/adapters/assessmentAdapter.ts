import type {
  AssessmentDetail,
  BlockingReasonDetail,
  EvidenceItem,
  PipelineStep,
  ProcessState,
  RuleResult,
} from "../../app/types/assessment";
import type { Decision, PublicationStatus } from "../../app/types/common";
import { array, bool, number, record, text } from "./guards";

export interface TraceNodeView {
  id: string;
  label: string;
  type: string;
  localId?: string;
  evidenceType?: string;
  x: number;
  y: number;
}

export interface TraceEdgeView {
  source: string;
  target: string;
  relation: string;
}

export interface AssessmentTraceView {
  caseId: string;
  executionId: string;
  nodes: TraceNodeView[];
  edges: TraceEdgeView[];
  nodeCount: number;
  edgeCount: number;
}

export interface AssessmentTimelineView {
  executionId: string;
  timeline: PipelineStep[];
}

export interface AssessmentArtifactsView {
  executionId: string;
  artifacts: Array<{ name: string; path: string }>;
}

export interface AssessmentComparisonView {
  decisionChanged: boolean;
  before: Record<string, unknown>;
  after: Record<string, unknown>;
  addedBlockingReasons: string[];
  removedBlockingReasons: string[];
  changedRuleVersions: Array<Record<string, unknown>>;
  changedEvidence: Record<string, unknown>;
  ruleChanges: Array<Record<string, unknown>>;
}

export interface AssessmentViewModel extends AssessmentDetail {
  validationSteps: PipelineStep[];
  traceNodes: TraceNodeView[];
  traceEdges: TraceEdgeView[];
  timeline: PipelineStep[];
  whatIfBaseline: {
    contractStatus: string;
    outstandingAmount: number;
    daysSinceLastPort: number;
  };
}

const decisions = new Set(["ELIGIBLE", "BLOCKED", "MANUAL_REVIEW", "CONDITIONAL", "UNKNOWN"]);

function decision(value: unknown): Decision {
  const valueText = text(value);
  return decisions.has(valueText) ? (valueText as Decision) : "UNKNOWN";
}

function evidenceItem(value: unknown): EvidenceItem {
  const item = record(value);
  return {
    evidenceId: text(item.evidence_id ?? item.id),
    evidenceType: text(item.evidence_type),
    sourceSystem: text(item.source_system),
    status: text(item.status, "UNKNOWN") as EvidenceItem["status"],
    generatedAt: text(item.generated_at),
    validUntil: text(item.valid_until),
    valueSummary: text(item.value_summary, "证据详情由后端提供"),
    identityMatchFlag: typeof item.matched === "boolean" ? item.matched : undefined,
    numberStatusCode: text(item.status_code) || undefined,
    outstandingAmount:
      typeof item.outstanding_amount === "number" ? item.outstanding_amount : undefined,
    currencyCode: text(item.currency) || undefined,
    hasPaymentArrangement:
      typeof item.has_payment_arrangement === "boolean"
        ? item.has_payment_arrangement
        : undefined,
    contractStatusCode: text(item.contract_status) || undefined,
    contractEndTime: text(item.contract_end_time) || undefined,
    daysSinceLastPort:
      typeof item.days_since_last_port === "number" ? item.days_since_last_port : undefined,
  };
}

function ruleResult(value: unknown): RuleResult {
  const item = record(value);
  return {
    ruleId: text(item.rule_id),
    version: text(item.version),
    status: text(item.status, "SKIP") as RuleResult["status"],
    effectiveFrom: text(item.effective_from) || null,
    effectiveTo: text(item.effective_to) || null,
    selectedForAssessmentTime: bool(item.selected_for_assessment_time, true),
    reasonCode: text(item.reason_code) || null,
    actionCode: text(item.action_code) || null,
    regulatoryClause: text(item.regulatory_clause) || null,
  };
}

function blockingReason(value: unknown): BlockingReasonDetail {
  const item = record(value);
  const evidence = record(item.evidence);
  return {
    reasonCode: text(item.reason_code ?? item.reason),
    ruleId: text(item.rule_id ?? item.rule),
    ruleVersion: text(item.rule_version),
    regulatoryClause: text(item.regulatory_clause ?? item.clause),
    actionCode: text(item.action_code ?? item.action),
    evidenceIds: [text(evidence.evidence_id)].filter(Boolean),
    description: text(item.reason_text),
  };
}

function processState(value: unknown): ProcessState {
  const item = record(value);
  const auth = record(item.authorization_code);
  return {
    currentStep: text(item.current_step),
    nextStep: text(item.next_step) || null,
    canAdvance: bool(item.can_advance),
    processBlockingReasons: array(item.blocking_reasons).map((raw) => {
      const reason = record(raw);
      return { code: text(reason.code), message: text(reason.message) };
    }),
    authorizationCode: Object.keys(auth).length
      ? {
          status: text(auth.status),
          issuedAt: text(auth.issued_at) || null,
          validUntil: text(auth.valid_until) || null,
          maskedValue: text(auth.masked_value) || null,
        }
      : null,
    eligibilityDecision: decision(item.eligibility_decision),
  };
}

function pipelineStep(value: unknown): PipelineStep {
  const item = record(value);
  return {
    id: text(item.id),
    labelKey: text(item.id),
    label: text(item.label),
    description: text(item.description),
    input: text(item.input),
    output: text(item.output),
    failure: text(item.failure),
    status: text(item.status, "PENDING") as PipelineStep["status"],
  };
}

function trace(value: unknown): { nodes: TraceNodeView[]; edges: TraceEdgeView[] } {
  const graph = record(value);
  const nodes = array(graph.nodes).map((raw) => {
    const node = record(raw);
    return {
      id: text(node.id),
      label: text(node.label ?? node.local_id),
      type: text(node.type),
      localId: text(node.local_id) || undefined,
      evidenceType: text(node.evidence_type) || undefined,
      // World coordinates are assigned by the unified graph layout — not array index.
      x: 0,
      y: 0,
    };
  });
  return {
    nodes,
    edges: array(graph.edges).map((raw) => {
      const edge = record(raw);
      return {
        source: text(edge.source),
        target: text(edge.target),
        relation: text(edge.predicate),
      };
    }),
  };
}

function whatIfBaseline(value: unknown): AssessmentViewModel["whatIfBaseline"] {
  const input = record(value);
  const evidence = record(input.evidence);
  return {
    contractStatus: text(record(evidence.contract).contract_status, "ACTIVE"),
    outstandingAmount: number(record(evidence.billing).outstanding_amount),
    daysSinceLastPort: number(record(evidence.porting_history).days_since_last_port),
  };
}

export function adaptAssessmentTrace(dto: unknown): AssessmentTraceView {
  const value = record(dto);
  const graphValue = Object.prototype.hasOwnProperty.call(value, "graph")
    ? value.graph
    : value;
  const graph = trace(graphValue);
  return {
    caseId: text(value.case_id ?? record(graphValue).case_id),
    executionId: text(value.execution_id),
    nodes: graph.nodes,
    edges: graph.edges,
    nodeCount: number(value.node_count, graph.nodes.length),
    edgeCount: number(value.edge_count, graph.edges.length),
  };
}

export function adaptAssessmentTimeline(dto: unknown): AssessmentTimelineView {
  const value = record(dto);
  return {
    executionId: text(value.execution_id),
    timeline: array(value.timeline).map(pipelineStep),
  };
}

export function adaptAssessmentArtifacts(dto: unknown): AssessmentArtifactsView {
  const value = record(dto);
  return {
    executionId: text(value.execution_id),
    artifacts: Object.entries(record(value.artifacts))
      .sort(([left], [right]) => left.localeCompare(right))
      .map(([name, path]) => ({ name, path: text(path) })),
  };
}

export function adaptAssessmentComparison(dto: unknown): AssessmentComparisonView {
  const value = record(dto);
  return {
    decisionChanged: bool(value.decision_changed),
    before: record(value.before),
    after: record(value.after),
    addedBlockingReasons: array(value.added_blocking_reasons).map((item) => text(item)),
    removedBlockingReasons: array(value.removed_blocking_reasons).map((item) => text(item)),
    changedRuleVersions: array(value.changed_rule_versions).map(record),
    changedEvidence: record(value.changed_evidence),
    ruleChanges: array(value.rule_changes).map(record),
  };
}

export function adaptAssessmentRecord(dto: unknown): AssessmentViewModel {
  const outer = record(dto);
  const result = record(outer.result ?? outer);
  const publication = record(result.publication);
  const validations = record(result.validations);
  const inputSummary = record(result.input_summary);
  const process = processState(result.process);
  const graph = trace(result.trace_subgraph);
  const validationSteps = [
    { id: "json_schema", ...record(validations.json_schema) },
    { id: "input_graph", ...record(validations.input_graph) },
    { id: "assessment_graph", ...record(validations.assessment_graph) },
  ].map(pipelineStep);
  const timeline = validationSteps;
  const caseId = text(result.case_id ?? outer.case_id);
  const executionId = text(result.execution_id ?? outer.execution_id);
  return {
    caseId,
    executionId,
    assessmentTime: text(result.assessment_time ?? outer.assessment_time),
    decision: decision(result.decision ?? outer.decision),
    publicationStatus: text(publication.status, "NOT_PUBLISHABLE") as PublicationStatus,
    published: bool(publication.publishable),
    evidence: array(result.evidence).map(evidenceItem),
    ruleResults: array(result.rule_results).map(ruleResult),
    blockingReasonDetails: array(result.blocking_reasons).map(blockingReason),
    pipelineSteps: validationSteps,
    validationSteps,
    process,
    executionCount: number(outer.execution_count, 1),
    maskedNumber: text(inputSummary.masked_number, "已脱敏"),
    title: "真实资格评估",
    scenario: "后端资格评估结果",
    traceNodes: graph.nodes,
    traceEdges: graph.edges,
    timeline,
    whatIfBaseline: whatIfBaseline(outer.input),
  };
}

export function adaptAssessmentView(dto: unknown, recordDto?: unknown): AssessmentViewModel {
  const view = record(dto);
  const header = record(view.header);
  const card = record(view.decision_card);
  const publication = record(card.publication);
  const graph = trace(view.trace_graph);
  const validationSteps = array(view.validation_steps).map(pipelineStep);
  return {
    caseId: text(header.case_id),
    executionId: text(header.execution_id),
    assessmentTime: text(header.assessment_time),
    decision: decision(card.decision),
    publicationStatus: text(publication.status, "NOT_PUBLISHABLE") as PublicationStatus,
    published: bool(publication.publishable),
    evidence: array(view.evidence_table).map(evidenceItem),
    ruleResults: array(view.rule_execution_table).map(ruleResult),
    blockingReasonDetails: array(view.blocking_reason_cards).map(blockingReason),
    pipelineSteps: validationSteps,
    validationSteps,
    process: processState(view.process_status),
    executionCount: 1,
    maskedNumber: text(record(view.input_summary).masked_number, "已脱敏"),
    title: "真实资格评估",
    scenario: "后端资格评估结果",
    traceNodes: graph.nodes,
    traceEdges: graph.edges,
    timeline: array(view.timeline).map(pipelineStep),
    whatIfBaseline: whatIfBaseline(record(recordDto).input),
  };
}
