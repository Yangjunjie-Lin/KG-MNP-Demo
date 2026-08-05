import type { OntologyEdge, OntologyNode } from "../types/ontology";
import type {
  LaneAssignment,
  OntologyLaneId,
  OntologyViewMode,
} from "./ontologyGraphTypes";

export const ONTOLOGY_LANE_ORDER: OntologyLaneId[] = [
  "USER_IDENTITY",
  "ACCOUNT_BILLING",
  "SERVICE_OFFERING",
  "PORTABILITY_PROCESS",
  "QUALIFICATION_COMPLIANCE",
];

export const ONTOLOGY_LANE_LABELS: Record<OntologyLaneId, string> = {
  USER_IDENTITY: "1. 用户与身份层",
  ACCOUNT_BILLING: "2. 账户与计费层",
  SERVICE_OFFERING: "3. 业务与服务层",
  PORTABILITY_PROCESS: "4. 携号转网流程层",
  QUALIFICATION_COMPLIANCE: "5. 资格与合规层",
};

export const ONTOLOGY_VIEW_LABELS: Record<OntologyViewMode, string> = {
  OVERVIEW: "总览图",
  USER_IDENTITY: "用户与身份层",
  ACCOUNT_BILLING: "账户与计费层",
  SERVICE_OFFERING: "业务与服务层",
  PORTABILITY_PROCESS: "携号转网流程层",
  QUALIFICATION_COMPLIANCE: "资格与合规层",
};

export const LANE_STYLES: Record<
  OntologyLaneId,
  { border: string; background: string; accent: string }
> = {
  USER_IDENTITY: {
    border: "#94a3b8",
    background: "#f8fafc",
    accent: "#475569",
  },
  ACCOUNT_BILLING: {
    border: "#7dd3fc",
    background: "#f0f9ff",
    accent: "#0369a1",
  },
  SERVICE_OFFERING: {
    border: "#a5b4fc",
    background: "#eef2ff",
    accent: "#4338ca",
  },
  PORTABILITY_PROCESS: {
    border: "#5eead4",
    background: "#f0fdfa",
    accent: "#0f766e",
  },
  QUALIFICATION_COMPLIANCE: {
    border: "#86efac",
    background: "#f0fdf4",
    accent: "#15803d",
  },
};

export interface OntologyLaneConfig {
  id: OntologyLaneId;
  backendModules: string[];
  coreNodes: string[];
  overviewNodeOrder: string[];
  emphasized?: string[];
}

export const ONTOLOGY_LANE_CONFIGS: OntologyLaneConfig[] = [
  {
    id: "USER_IDENTITY",
    backendModules: ["IDENTITY"],
    coreNodes: ["Subscriber", "PhoneNumber"],
    overviewNodeOrder: [
      "Subscriber",
      "NaturalPerson",
      "OrganisationSubscriber",
      "IdentityDocument",
      "RealNameRegistration",
      "IdentityVerification",
      "PhoneNumberOwnership",
      "PhoneNumber",
    ],
  },
  {
    id: "ACCOUNT_BILLING",
    backendModules: ["ACCOUNT_BILLING"],
    coreNodes: ["TelecomAccount"],
    overviewNodeOrder: [
      "TelecomAccount",
      "BillingAccount",
      "Bill",
      "Charge",
      "Payment",
      "PaymentArrangement",
      "BillingSettlement",
      "OutstandingBalanceObservation",
    ],
  },
  {
    id: "SERVICE_OFFERING",
    backendModules: ["SERVICE_CONTRACT"],
    coreNodes: ["TelecomService", "ServiceSubscription", "ServiceContract"],
    overviewNodeOrder: [
      "ServiceSubscription",
      "TelecomService",
      "MobilePlan",
      "BroadbandService",
      "ValueAddedService",
      "SupplementaryCardService",
      "ConvergedService",
      "ServiceContract",
      "CommitmentPeriod",
      "TerminationAgreement",
    ],
  },
  {
    id: "PORTABILITY_PROCESS",
    backendModules: ["PROCESS"],
    coreNodes: ["MNPCase"],
    overviewNodeOrder: [
      "MNPCase",
      "MNPRequest",
      "EligibilityCheck",
      "AuthorizationCodeRequest",
      "AuthorizationCode",
      "PortInSubmission",
      "PortingExecution",
      "PortingConfirmation",
      "ProcessEvent",
      "MNPCaseStatus",
    ],
  },
  {
    id: "QUALIFICATION_COMPLIANCE",
    backendModules: ["COMPLIANCE", "EVIDENCE_TIME"],
    coreNodes: [
      "EligibilityAssessment",
      "EligibilityDecision",
      "EligibleDecision",
      "BlockingDecision",
      "ConditionalDecision",
      "ManualReviewDecision",
      "EvidenceRecord",
      "SystemObservation",
      "EligibilityRule",
      "RuleVersion",
      "BlockingReason",
      "RemediationAction",
      "RegulatoryClause",
      "RegulatoryDocument",
      "InformationSystem",
      "AssessmentDependency",
    ],
    overviewNodeOrder: [
      "EligibilityAssessment",
      "EligibilityRule",
      "RuleVersion",
      "RegulatoryClause",
      "EvidenceRecord",
      "EligibilityDecision",
      "BlockingReason",
      "RemediationAction",
    ],
    emphasized: ["EligibilityAssessment"],
  },
];

/** Exact localName → lane overrides (priority 1). Technical nodes are not listed here. */
export const LOCAL_NAME_LANE_MAP: Record<string, OntologyLaneId> = {};

export const OVERVIEW_RELATION_ALLOWLIST = new Set([
  // 用户与身份
  "ownsPhoneNumber",
  "hasIdentityDocument",
  "hasRealNameRegistration",
  "verifiedBy",
  "assertsOwnership",
  "ownershipHolder",

  // 账户与计费
  "billedThrough",
  "relatedAccount",
  "hasBill",
  "hasCharge",
  "hasPayment",
  "observesAccount",
  "hasPaymentArrangementRecord",
  "settlesAccount",

  // 业务与服务
  "hasSubscription",
  "subscribesToService",
  "governedByContract",
  "hasCommitmentPeriod",
  "hasTerminationAgreement",
  "coversService",

  // 携转流程
  "requestedBy",
  "concernsNumber",
  "hasProcessStep",
  "currentProcessStep",
  "nextProcessStep",
  "hasAuthorizationCode",
  "hasProcessEvent",
  "hasCaseStatus",

  // 资格与合规
  "hasEligibilityAssessment",
  "usesEvidence",
  "evaluatedByRule",
  "usesRuleVersion",
  "producesDecision",
  "producesBlockingReason",
  "recommendsAction",
  "operationalizesClause",
  "partOfDocument",
  "hasSourceSystem",
  "supportedByEvidence",
  "triggeredByRule",
  "triggeredByRuleVersion",
  "citesClause",
  "dependsOn",
  "dependsOnRuleVersion",
  "dependsOnEvidence",
]);

const TECHNICAL_MODULES = new Set(["CODE_LIST", "ALIGNMENTS"]);

function normalizeModule(module: string): string {
  return module.trim().toUpperCase();
}

function buildCoreNodeLaneIndex(): Map<string, OntologyLaneId> {
  const map = new Map<string, OntologyLaneId>();
  for (const config of ONTOLOGY_LANE_CONFIGS) {
    for (const localName of config.coreNodes) {
      map.set(localName, config.id);
    }
  }
  return map;
}

function buildBackendModuleLaneIndex(): Map<string, OntologyLaneId> {
  const map = new Map<string, OntologyLaneId>();
  for (const config of ONTOLOGY_LANE_CONFIGS) {
    for (const module of config.backendModules) {
      map.set(normalizeModule(module), config.id);
    }
  }
  return map;
}

const CORE_NODE_LANE = buildCoreNodeLaneIndex();
const BACKEND_MODULE_LANE = buildBackendModuleLaneIndex();

export function getLaneConfig(laneId: OntologyLaneId): OntologyLaneConfig {
  const config = ONTOLOGY_LANE_CONFIGS.find((item) => item.id === laneId);
  if (!config) {
    throw new Error(`Unknown ontology lane: ${laneId}`);
  }
  return config;
}

export function isTechnicalSupportNode(node: OntologyNode): boolean {
  if (TECHNICAL_MODULES.has(normalizeModule(node.module))) return true;
  if (node.localName === "MappingRecord" || node.localName === "CodeListEntry") {
    return true;
  }
  return false;
}

export function isEmphasizedNode(laneId: OntologyLaneId, localName: string): boolean {
  const config = getLaneConfig(laneId);
  return (config.emphasized ?? []).includes(localName);
}

/**
 * Phase-1 assignment only. Technical support nodes are deferred to adjacency.
 */
export function assignOntologyLane(node: OntologyNode): OntologyLaneId | null {
  const phase1 = assignPhase1(node);
  return phase1?.laneId ?? null;
}

function assignPhase1(node: OntologyNode): LaneAssignment | null {
  const byLocalName = LOCAL_NAME_LANE_MAP[node.localName];
  if (byLocalName) {
    return { laneId: byLocalName, reason: "EXACT_LOCAL_NAME" };
  }

  if (isTechnicalSupportNode(node)) {
    return null;
  }

  const module = normalizeModule(node.module);
  const byModule = BACKEND_MODULE_LANE.get(module);
  if (byModule) {
    return { laneId: byModule, reason: "BACKEND_MODULE" };
  }

  if (module === "CORE") {
    const byCore = CORE_NODE_LANE.get(node.localName);
    if (byCore) {
      return { laneId: byCore, reason: "CORE_NODE" };
    }
  }

  return null;
}

function pickLaneByNeighborScores(
  scores: Map<OntologyLaneId, number>,
): OntologyLaneId | null {
  let bestLane: OntologyLaneId | null = null;
  let bestScore = -1;
  for (const laneId of ONTOLOGY_LANE_ORDER) {
    const score = scores.get(laneId) ?? 0;
    if (score > bestScore) {
      bestScore = score;
      bestLane = laneId;
    }
  }
  return bestScore > 0 ? bestLane : null;
}

export function assignAllOntologyLanes(
  nodes: OntologyNode[],
  edges: OntologyEdge[] = [],
): {
  assignments: Map<string, OntologyLaneId>;
  assignmentMeta: Map<string, LaneAssignment>;
  unmapped: OntologyNode[];
  technicalAdjacencyCount: number;
  technicalFallbackCount: number;
} {
  const nodeById = new Map(nodes.map((node) => [node.id, node]));
  const assignments = new Map<string, OntologyLaneId>();
  const assignmentMeta = new Map<string, LaneAssignment>();
  const pendingTechnical: OntologyNode[] = [];

  const sortedNodes = [...nodes].sort((a, b) =>
    a.id.localeCompare(b.id) || a.localName.localeCompare(b.localName),
  );

  for (const node of sortedNodes) {
    const phase1 = assignPhase1(node);
    if (phase1) {
      if (assignments.has(node.id)) {
        throw new Error(`Duplicate lane assignment for node ${node.id}`);
      }
      assignments.set(node.id, phase1.laneId);
      assignmentMeta.set(node.id, phase1);
      continue;
    }
    if (isTechnicalSupportNode(node)) {
      pendingTechnical.push(node);
      continue;
    }
  }

  const adjacency = new Map<string, string[]>();
  const sortedEdges = [...edges].sort(
    (a, b) =>
      a.from.localeCompare(b.from) ||
      a.to.localeCompare(b.to) ||
      a.relation.localeCompare(b.relation),
  );
  for (const edge of sortedEdges) {
    if (!adjacency.has(edge.from)) adjacency.set(edge.from, []);
    if (!adjacency.has(edge.to)) adjacency.set(edge.to, []);
    adjacency.get(edge.from)?.push(edge.to);
    adjacency.get(edge.to)?.push(edge.from);
  }

  let progressed = true;
  while (progressed) {
    progressed = false;
    const stillPending: OntologyNode[] = [];
    const orderedPending = [...pendingTechnical].sort((a, b) =>
      a.id.localeCompare(b.id),
    );
    for (const node of orderedPending) {
      if (assignments.has(node.id)) continue;
      const scores = new Map<OntologyLaneId, number>();
      for (const neighborId of adjacency.get(node.id) ?? []) {
        const laneId = assignments.get(neighborId);
        if (!laneId) continue;
        scores.set(laneId, (scores.get(laneId) ?? 0) + 1);
      }
      const chosen = pickLaneByNeighborScores(scores);
      if (!chosen) {
        stillPending.push(node);
        continue;
      }
      const meta: LaneAssignment = {
        laneId: chosen,
        reason: "TECHNICAL_ADJACENCY",
      };
      assignments.set(node.id, meta.laneId);
      assignmentMeta.set(node.id, meta);
      progressed = true;
    }
    pendingTechnical.length = 0;
    pendingTechnical.push(...stillPending);
  }

  let technicalFallbackCount = 0;
  for (const node of [...pendingTechnical].sort((a, b) => a.id.localeCompare(b.id))) {
    const meta: LaneAssignment = {
      laneId: "QUALIFICATION_COMPLIANCE",
      reason: "TECHNICAL_FALLBACK",
    };
    assignments.set(node.id, meta.laneId);
    assignmentMeta.set(node.id, meta);
    technicalFallbackCount += 1;
  }

  const unmapped: OntologyNode[] = [];
  for (const node of sortedNodes) {
    if (assignments.has(node.id)) continue;
    console.warn("[ontology-layout] unmapped node", {
      id: node.id,
      localName: node.localName,
      module: node.module,
    });
    unmapped.push(node);
  }

  // Validate referenced edge endpoints exist in node set (ignore dangling).
  for (const edge of sortedEdges) {
    void nodeById.get(edge.from);
    void nodeById.get(edge.to);
  }

  let technicalAdjacencyCount = 0;
  for (const meta of assignmentMeta.values()) {
    if (meta.reason === "TECHNICAL_ADJACENCY") technicalAdjacencyCount += 1;
  }

  return {
    assignments,
    assignmentMeta,
    unmapped,
    technicalAdjacencyCount,
    technicalFallbackCount,
  };
}
