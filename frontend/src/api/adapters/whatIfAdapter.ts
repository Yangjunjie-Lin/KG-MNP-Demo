import type { Decision } from "../../app/types/common";
import { array, bool, number, record, text } from "./guards";

export interface WhatIfScenarioChanges {
  contractStatus?: string;
  outstandingAmount?: number;
  daysSinceLastPort?: number;
}

export interface WhatIfRuleChangeView {
  ruleId: string;
  versionBefore: string;
  versionAfter: string;
  statusBefore: string;
  statusAfter: string;
  changed: boolean;
  changeKind: string;
}

export interface WhatIfReasonChangesView {
  added: string[];
  removed: string[];
}

export interface WhatIfEvidenceChangesView {
  addedCount: number;
  removedCount: number;
  modifiedCount: number;
}

export interface WhatIfTraceChangesView {
  baselineEdgeCount: number;
  scenarioEdgeCount: number;
  baselineNodeCount: number;
  scenarioNodeCount: number;
  edgeCountDelta: number;
  nodeCountDelta: number;
}

export interface WhatIfViewModel {
  baselineDecision: Decision;
  scenarioDecision: Decision;
  decisionChanged: boolean;
  ruleChanges: WhatIfRuleChangeView[];
  reasonChanges: WhatIfReasonChangesView;
  evidenceChanges: WhatIfEvidenceChangesView;
  traceChanges: WhatIfTraceChangesView;
}

function safeDecision(value: unknown): Decision {
  const raw = text(value);
  return ["ELIGIBLE", "BLOCKED", "CONDITIONAL", "MANUAL_REVIEW", "UNKNOWN"].includes(raw)
    ? (raw as Decision)
    : "UNKNOWN";
}

export function toWhatIfDtoChanges(changes: WhatIfScenarioChanges): Record<string, unknown> {
  const evidence: Record<string, unknown> = {};
  if (changes.contractStatus !== undefined) {
    evidence.contract = { contract_status: changes.contractStatus };
  }
  if (changes.outstandingAmount !== undefined) {
    evidence.billing = { outstanding_amount: changes.outstandingAmount };
  }
  if (changes.daysSinceLastPort !== undefined) {
    evidence.porting_history = { days_since_last_port: changes.daysSinceLastPort };
  }
  return Object.keys(evidence).length ? { evidence } : {};
}

function adaptRuleChange(value: unknown): WhatIfRuleChangeView {
  const item = record(value);
  return {
    ruleId: text(item.rule_id),
    versionBefore: text(item.version_before),
    versionAfter: text(item.version_after),
    statusBefore: text(item.status_before, "SKIP"),
    statusAfter: text(item.status_after, "SKIP"),
    changed: bool(item.changed),
    changeKind: text(item.change_kind),
  };
}

export function adaptWhatIf(dto: unknown): WhatIfViewModel {
  const result = record(dto);
  const baseline = record(result.baseline);
  const scenario = record(result.scenario);
  if (scenario.error) throw new Error("SCENARIO_ERROR");
  const decisionChange = record(result.decision_change);
  const reasons = record(result.reason_changes);
  const evidence = record(result.evidence_changes);
  const trace = record(result.trace_changes);
  const changedEvidence = array(evidence.changed);
  return {
    baselineDecision: safeDecision(baseline.decision),
    scenarioDecision: safeDecision(scenario.decision),
    decisionChanged: typeof result.decision_changed === "boolean"
      ? result.decision_changed
      : bool(decisionChange.changed),
    ruleChanges: array(result.rule_changes).map(adaptRuleChange),
    reasonChanges: {
      added: array(reasons.added).map((value) => text(value)).filter(Boolean),
      removed: array(reasons.removed).map((value) => text(value)).filter(Boolean),
    },
    evidenceChanges: {
      addedCount: array(evidence.added).length,
      removedCount: array(evidence.removed).length,
      modifiedCount: Math.max(array(evidence.modified).length, changedEvidence.length),
    },
    traceChanges: {
      baselineEdgeCount: number(trace.baseline_edge_count),
      scenarioEdgeCount: number(trace.scenario_edge_count),
      baselineNodeCount: number(trace.baseline_node_count),
      scenarioNodeCount: number(trace.scenario_node_count),
      edgeCountDelta: number(trace.edge_count_delta),
      nodeCountDelta: number(trace.node_count_delta),
    },
  };
}
