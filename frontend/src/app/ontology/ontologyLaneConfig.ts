import type { OntologyNode } from "../types/ontology";
import type { OntologyLaneId, OntologyViewMode } from "./ontologyGraphTypes";

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

/** Exact localName → lane overrides (priority 1). */
export const LOCAL_NAME_LANE_MAP: Record<string, OntologyLaneId> = {
  MappingRecord: "QUALIFICATION_COMPLIANCE",
  CodeListEntry: "QUALIFICATION_COMPLIANCE",
};

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
 * Assign a node to exactly one business lane.
 * Priority: localName map → backend module → CORE exact map → technical fallback → null.
 */
export function assignOntologyLane(node: OntologyNode): OntologyLaneId | null {
  const byLocalName = LOCAL_NAME_LANE_MAP[node.localName];
  if (byLocalName) return byLocalName;

  const module = normalizeModule(node.module);
  const byModule = BACKEND_MODULE_LANE.get(module);
  if (byModule) return byModule;

  if (module === "CORE") {
    const byCore = CORE_NODE_LANE.get(node.localName);
    if (byCore) return byCore;
  }

  if (TECHNICAL_MODULES.has(module)) {
    return LOCAL_NAME_LANE_MAP[node.localName] ?? "QUALIFICATION_COMPLIANCE";
  }

  return null;
}

export function assignAllOntologyLanes(
  nodes: OntologyNode[],
): {
  assignments: Map<string, OntologyLaneId>;
  unmapped: OntologyNode[];
} {
  const assignments = new Map<string, OntologyLaneId>();
  const unmapped: OntologyNode[] = [];

  for (const node of nodes) {
    const lane = assignOntologyLane(node);
    if (!lane) {
      console.warn("[ontology-layout] unmapped node", {
        id: node.id,
        localName: node.localName,
        module: node.module,
      });
      unmapped.push(node);
      continue;
    }
    if (assignments.has(node.id)) {
      throw new Error(`Duplicate lane assignment for node ${node.id}`);
    }
    assignments.set(node.id, lane);
  }

  return { assignments, unmapped };
}
