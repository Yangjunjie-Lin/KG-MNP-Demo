const time = "2026-07-01T00:00:00Z";

export const healthFixture = { status: "ok", time };
export const readyFixture = { status: "ready", sqlite: true, neo4j_required: false };
export const metaFixture = {
  name: "演示服务",
  api_version: "1.0",
  schema_version: "1.0",
  backend: "rdf",
  neo4j_required: false,
};

export const dashboardFixture = {
  project: {},
  capabilities: [],
  ontology: {
    module_count: 8,
    class_count: 61,
    object_property_count: 56,
    data_property_count: 66,
    shape_count: 49,
    rule_count: 6,
    competency_question_count: 15,
  },
  example_cases: { total: 9, eligible: 2, blocked: 6, manual_review: 1 },
  executions: { total: 10, eligible: 3, blocked: 6, manual_review: 1 },
  latest_case_states: { total: 9, eligible: 2, blocked: 6, manual_review: 1 },
  pipeline_steps: [],
  example_case_ids: Array.from({ length: 9 }, (_, index) => `CASE-0${index + 1}`),
};

export const caseCatalogFixture = {
  items: Array.from({ length: 9 }, (_, index) => ({
    case_id: `CASE-0${index + 1}`,
    scenario: `后端案例情景${index + 1}`,
  })),
};

export const historiesFixture: Record<string, Array<Record<string, unknown>>> = {
  "CASE-03": [
    {
      execution_id: "exec-case03",
      case_id: "CASE-03",
      assessment_time: time,
      decision: "BLOCKED",
      publishable: true,
      publication_status: "PUBLISHABLE",
    },
  ],
  "CASE-06": [
    {
      execution_id: "exec-case06-current",
      case_id: "CASE-06",
      assessment_time: "2026-07-01T00:00:00Z",
      decision: "BLOCKED",
      publishable: true,
      publication_status: "PUBLISHABLE",
    },
    {
      execution_id: "exec-case06-history",
      case_id: "CASE-06",
      assessment_time: "2026-05-15T00:00:00Z",
      decision: "ELIGIBLE",
      publishable: true,
      publication_status: "PUBLISHABLE",
    },
  ],
  "CASE-07": [
    {
      execution_id: "exec-case07",
      case_id: "CASE-07",
      assessment_time: time,
      decision: "ELIGIBLE",
      publishable: true,
      publication_status: "PUBLISHABLE",
    },
  ],
};

export const caseCatalogViewFixture = {
  items: caseCatalogFixture.items.map((item) => {
    const history = historiesFixture[item.case_id] ?? [];
    const latest = [...history].sort((left, right) =>
      String(right.assessment_time ?? "").localeCompare(String(left.assessment_time ?? "")),
    )[0];
    const expectedDecisions: Record<string, string> = {
      "CASE-01": "ELIGIBLE",
      "CASE-02": "BLOCKED",
      "CASE-03": "BLOCKED",
      "CASE-04": "BLOCKED",
      "CASE-05": "MANUAL_REVIEW",
      "CASE-06": "BLOCKED",
      "CASE-07": "ELIGIBLE",
      "CASE-08": "BLOCKED",
      "CASE-09": "BLOCKED",
    };
    return {
      ...item,
      expected_decision: expectedDecisions[item.case_id],
      latest_execution_id: latest?.execution_id ?? null,
      latest_assessment_time: latest?.assessment_time ?? null,
      latest_decision: latest?.decision ?? null,
      publication_status: latest?.publication_status ?? null,
      execution_count: history.length,
      has_history: history.length > 0,
    };
  }),
};

const validationSteps = [
  { id: "json_schema", status: "PASSED" },
  { id: "input_graph", status: "PASSED" },
  { id: "assessment_graph", status: "PASSED" },
];

const traceGraph = {
  nodes: [
    { id: "case-node", label: "CASE-03", type: "MNPCase" },
    { id: "assessment-node", label: "assessment", type: "EligibilityAssessment" },
    { id: "rule-node", label: "MNP-ELIG-004", type: "EligibilityRule" },
  ],
  edges: [
    { source: "case-node", target: "assessment-node", predicate: "hasAssessment" },
    { source: "assessment-node", target: "rule-node", predicate: "evaluatedBy" },
  ],
};

interface AssessmentViewOptions {
  executionId: string;
  caseId: string;
  decision: "ELIGIBLE" | "BLOCKED" | "MANUAL_REVIEW";
  assessmentTime?: string;
  ruleId?: string;
  ruleVersion?: string;
  blocked?: boolean;
  authorizationExpired?: boolean;
}

export function assessmentViewFixture({
  executionId,
  caseId,
  decision,
  assessmentTime = time,
  ruleId = "MNP-ELIG-004",
  ruleVersion = "1.0",
  blocked = decision === "BLOCKED",
  authorizationExpired = false,
}: AssessmentViewOptions) {
  return {
    header: { execution_id: executionId, case_id: caseId, assessment_time: assessmentTime },
    decision_card: {
      decision,
      publication: { status: "PUBLISHABLE", publishable: true },
    },
    input_summary: { masked_number: "138****0003" },
    validation_steps: validationSteps,
    evidence_table: [
      {
        evidence_id: "contract-evidence",
        evidence_type: "ContractEvidence",
        source_system: "CONTRACT",
        status: "VALID",
        generated_at: "2026-06-01T00:00:00Z",
        valid_until: "2026-12-01T00:00:00Z",
      },
    ],
    rule_execution_table: [
      {
        rule_id: ruleId,
        version: ruleVersion,
        status: blocked ? "FAIL" : "PASS",
        selected_for_assessment_time: true,
      },
    ],
    blocking_reason_cards: blocked
      ? [
          {
            reason_code:
              ruleId === "MNP-ELIG-005"
                ? "PORTING_INTERVAL_NOT_MET"
                : "ACTIVE_CONTRACT_RESTRICTION",
            rule_id: ruleId,
            rule_version: ruleVersion,
            regulatory_clause:
              ruleId === "MNP-ELIG-005" ? "REG-MNP-CLAUSE-05" : "REG-MNP-CLAUSE-04",
            action_code:
              ruleId === "MNP-ELIG-005"
                ? "WAIT_UNTIL_INTERVAL_MET"
                : "WAIT_OR_TERMINATE_CONTRACT",
            evidence: { evidence_id: "contract-evidence" },
          },
        ]
      : [],
    remediation_actions: [],
    process_status: {
      eligibility_decision: decision,
      current_step: authorizationExpired ? "AUTHORIZATION" : "ELIGIBILITY_ASSESSMENT",
      next_step: authorizationExpired ? null : "AUTHORIZATION",
      can_advance: !authorizationExpired && decision === "ELIGIBLE",
      blocking_reasons: authorizationExpired
        ? [{ code: "AUTHORIZATION_CODE_EXPIRED", message: "expired" }]
        : [],
      authorization_code: authorizationExpired
        ? {
            status: "EXPIRED",
            issued_at: "2026-06-01T00:00:00Z",
            valid_until: "2026-06-02T00:00:00Z",
            masked_value: "****",
          }
        : {},
    },
    trace_graph: traceGraph,
    timeline: validationSteps,
    artifacts: [],
    technical_details: {},
  };
}

export const assessmentViewsFixture: Record<string, ReturnType<typeof assessmentViewFixture>> = {
  "exec-case03": assessmentViewFixture({
    executionId: "exec-case03",
    caseId: "CASE-03",
    decision: "BLOCKED",
  }),
  "exec-case06-current": assessmentViewFixture({
    executionId: "exec-case06-current",
    caseId: "CASE-06",
    decision: "BLOCKED",
    ruleId: "MNP-ELIG-005",
    ruleVersion: "1.1",
  }),
  "exec-case06-history": assessmentViewFixture({
    executionId: "exec-case06-history",
    caseId: "CASE-06",
    decision: "ELIGIBLE",
    assessmentTime: "2026-05-15T00:00:00Z",
    ruleId: "MNP-ELIG-005",
    ruleVersion: "1.0",
    blocked: false,
  }),
  "exec-case07": assessmentViewFixture({
    executionId: "exec-case07",
    caseId: "CASE-07",
    decision: "ELIGIBLE",
    blocked: false,
    authorizationExpired: true,
  }),
};

export function assessmentRecordFixture(
  executionId = "exec-created",
  caseId = "CASE-03",
) {
  return {
    execution_id: executionId,
    case_id: caseId,
    result: {
      execution_id: executionId,
      case_id: caseId,
      assessment_time: time,
      decision: "BLOCKED",
      publication: { status: "PUBLISHABLE", publishable: true },
      validations: {
        json_schema: { status: "PASSED" },
        input_graph: { status: "PASSED" },
        assessment_graph: { status: "PASSED" },
      },
      input_summary: { masked_number: "138****0003" },
      evidence: [],
      rule_results: [],
      blocking_reasons: [],
      process: { eligibility_decision: "BLOCKED", can_advance: false },
      trace_subgraph: traceGraph,
    },
  };
}

export const exampleInputFixture = {
  schema_version: "1.0",
  case_id: "CASE-03",
  assessment_time: time,
  subscriber: { subscriber_id: "subscriber-03" },
  phone_number: { masked_number: "138****0003" },
  account: { account_id: "account-03" },
  evidence: {
    identity: {
      matched: true,
      source_system: "CRM",
      generated_at: "2026-06-01T00:00:00Z",
      valid_until: "2026-12-01T00:00:00Z",
      status: "VALID",
    },
    number_status: {
      status_code: "ACTIVE",
      source_system: "HLR",
      generated_at: "2026-06-01T00:00:00Z",
      valid_until: "2026-12-01T00:00:00Z",
      status: "VALID",
    },
    billing: {
      outstanding_amount: 0,
      currency: "CNY",
      has_payment_arrangement: false,
      source_system: "BILLING",
      generated_at: "2026-06-01T00:00:00Z",
      valid_until: "2026-12-01T00:00:00Z",
      status: "VALID",
    },
    contract: {
      contract_status: "ACTIVE",
      contract_end_time: "2026-12-01T00:00:00Z",
      source_system: "CONTRACT",
      generated_at: "2026-06-01T00:00:00Z",
      valid_until: "2026-12-01T00:00:00Z",
      status: "VALID",
    },
    porting_history: {
      days_since_last_port: 250,
      source_system: "MNP_HISTORY",
      generated_at: "2026-06-01T00:00:00Z",
      valid_until: "2026-12-01T00:00:00Z",
      status: "VALID",
    },
  },
};

export const examplesFixture = {
  items: caseCatalogFixture.items.map((item) => ({
    ...item,
    expected_decision: item.case_id === "CASE-03" ? "BLOCKED" : "ELIGIBLE",
  })),
};

export const ontologyViewFixture = {
  modules: [
    { module: "IDENTITY", label_zh: "用户与身份层", description: "身份" },
    { module: "ACCOUNT_BILLING", label_zh: "账户与计费层", description: "计费" },
    { module: "SERVICE_CONTRACT", label_zh: "业务与服务层", description: "业务" },
    { module: "PROCESS", label_zh: "携转流程层", description: "流程" },
    { module: "COMPLIANCE", label_zh: "资格与合规层", description: "合规" },
  ],
  graph: {
    nodes: [
      { id: "urn:mnp:Subscriber", local_name: "Subscriber", label: "订户", type: "Class", module: "IDENTITY" },
      { id: "urn:mnp:NaturalPerson", local_name: "NaturalPerson", label: "自然人订户", type: "Class", module: "IDENTITY" },
      { id: "urn:mnp:IdentityDocument", local_name: "IdentityDocument", label: "身份证件", type: "Class", module: "IDENTITY" },
      { id: "urn:mnp:RealNameRegistration", local_name: "RealNameRegistration", label: "实名登记", type: "Class", module: "IDENTITY" },
      { id: "urn:mnp:PhoneNumber", local_name: "PhoneNumber", label: "电话号码", type: "Class", module: "IDENTITY" },
      { id: "urn:mnp:TelecomAccount", local_name: "TelecomAccount", label: "电信账户", type: "Class", module: "ACCOUNT_BILLING" },
      { id: "urn:mnp:BillingAccount", local_name: "BillingAccount", label: "计费账户", type: "Class", module: "ACCOUNT_BILLING" },
      { id: "urn:mnp:Bill", local_name: "Bill", label: "账单", type: "Class", module: "ACCOUNT_BILLING" },
      { id: "urn:mnp:MobilePlan", local_name: "MobilePlan", label: "移动套餐", type: "Class", module: "SERVICE_CONTRACT" },
      { id: "urn:mnp:TelecomService", local_name: "TelecomService", label: "电信业务", type: "Class", module: "SERVICE_CONTRACT" },
      { id: "urn:mnp:ServiceSubscription", local_name: "ServiceSubscription", label: "业务订阅", type: "Class", module: "SERVICE_CONTRACT" },
      { id: "urn:mnp:ServiceContract", local_name: "ServiceContract", label: "服务合约", type: "Class", module: "SERVICE_CONTRACT" },
      { id: "urn:mnp:case", local_name: "MNPCase", label: "携转案例", type: "Class", module: "PROCESS" },
      { id: "urn:mnp:MNPRequest", local_name: "MNPRequest", label: "携转申请", type: "Class", module: "PROCESS" },
      { id: "urn:mnp:assessment", local_name: "EligibilityAssessment", label: "资格评估", type: "Class", module: "COMPLIANCE" },
      { id: "urn:mnp:EligibilityRule", local_name: "EligibilityRule", label: "资格规则", type: "Class", module: "COMPLIANCE" },
      { id: "urn:mnp:EvidenceRecord", local_name: "EvidenceRecord", label: "证据记录", type: "Class", module: "EVIDENCE_TIME" },
      { id: "urn:mnp:BlockingReason", local_name: "BlockingReason", label: "阻塞原因", type: "Class", module: "COMPLIANCE" },
    ],
    edges: [
      { source: "urn:mnp:case", target: "urn:mnp:assessment", predicate: "hasEligibilityAssessment" },
      { source: "urn:mnp:Subscriber", target: "urn:mnp:PhoneNumber", predicate: "ownsPhoneNumber" },
      { source: "urn:mnp:Subscriber", target: "urn:mnp:RealNameRegistration", predicate: "hasRealNameRegistration" },
      { source: "urn:mnp:Subscriber", target: "urn:mnp:IdentityDocument", predicate: "hasIdentityDocument" },
      { source: "urn:mnp:TelecomAccount", target: "urn:mnp:BillingAccount", predicate: "relatedAccount" },
      { source: "urn:mnp:BillingAccount", target: "urn:mnp:Bill", predicate: "hasBill" },
      { source: "urn:mnp:ServiceSubscription", target: "urn:mnp:TelecomService", predicate: "subscribesToService" },
      { source: "urn:mnp:assessment", target: "urn:mnp:EvidenceRecord", predicate: "usesEvidence" },
      { source: "urn:mnp:assessment", target: "urn:mnp:EligibilityRule", predicate: "evaluatedByRule" },
      { source: "urn:mnp:MNPRequest", target: "urn:mnp:Subscriber", predicate: "requestedBy" },
      { source: "urn:mnp:case", target: "urn:mnp:assessment", predicate: "aboutCase" },
    ],
  },
  key_paths: [
    {
      id: "case-assessment",
      source_class: "MNPCase",
      predicate: "hasEligibilityAssessment",
      target_class: "EligibilityAssessment",
      exists_in_rdf: true,
    },
  ],
  stats: { class_count: 18, edge_count: 11 },
};

export const ontologyPropertiesFixture = {
  object_properties: [
    { local_name: "hasEligibilityAssessment", label_zh: "关联评估" },
    { local_name: "ownsPhoneNumber", label_zh: "持有号码" },
    { local_name: "hasRealNameRegistration", label_zh: "具有实名登记" },
    { local_name: "hasIdentityDocument", label_zh: "持有身份证件" },
    { local_name: "relatedAccount", label_zh: "关联账户" },
    { local_name: "hasBill", label_zh: "包含账单" },
    { local_name: "subscribesToService", label_zh: "订阅业务" },
    { local_name: "usesEvidence", label_zh: "使用证据" },
    { local_name: "evaluatedByRule", label_zh: "依据规则评估" },
    { local_name: "requestedBy", label_zh: "由订户申请" },
    { local_name: "aboutCase", label_zh: "关于案件" },
  ],
  data_properties: [],
};

const rule4 = {
  rule_id: "MNP-ELIG-004",
  version: "1.0",
  effective_from: "2024-01-01",
  effective_to: null,
  reason_code: "ACTIVE_CONTRACT_RESTRICTION",
  action_code: "WAIT_OR_TERMINATE_CONTRACT",
  regulatory_clause: "REG-MNP-CLAUSE-04",
  inputs: [{ evidence_type: "ContractEvidence", required: true, fields: ["contract_status"] }],
  check: {},
};

const rule5History = {
  rule_id: "MNP-ELIG-005",
  version: "1.0",
  effective_from: "2024-01-01",
  effective_to: "2026-06-30",
  reason_code: "PORTING_INTERVAL_NOT_MET",
  action_code: "WAIT_UNTIL_INTERVAL_MET",
  regulatory_clause: "REG-MNP-CLAUSE-05",
  inputs: [{ evidence_type: "PortingHistoryEvidence", required: true, fields: ["days_since_last_port"] }],
  check: { minimum: 120 },
};

const rule5Current = {
  ...rule5History,
  version: "1.1",
  effective_from: "2026-07-01",
  effective_to: null,
  supersedes_version: "1.0",
  check: { minimum: 180 },
};

export const ruleCatalogFixture = {
  items: [rule4, rule5Current],
};

export const ruleVersionsFixture: Record<string, Array<Record<string, unknown>>> = {
  "MNP-ELIG-004": [rule4],
  "MNP-ELIG-005": [rule5History, rule5Current],
};

export const affectedAssessmentsFixture = {
  rule_id: "MNP-ELIG-005",
  old_version: "1.0",
  new_version: "1.1",
  items: [
    {
      execution_id: "exec-case06-history",
      case_id: "CASE-06",
      assessment_time: "2026-05-15T00:00:00Z",
      requires_reassessment: true,
    },
  ],
};

export const competencyQuestionsFixture = {
  items: [
    {
      id: "CQ-01",
      title_zh: "哪些案例存在资格阻塞？",
      required_inputs: ["case_id"],
      return_fields: ["caseId", "decision"],
      example_case: "CASE-03",
    },
  ],
};

export const competencyResultFixture = {
  question_id: "CQ-01",
  status: "success",
  columns: ["caseId", "decision"],
  rows: [{ caseId: "CASE-03", decision: "BLOCKED" }],
};

export const whatIfFixture = {
  baseline: { decision: "BLOCKED" },
  scenario: { decision: "ELIGIBLE" },
  decision_changed: true,
  rule_changes: [
    {
      rule_id: "MNP-ELIG-004",
      status_before: "FAIL",
      status_after: "PASS",
      changed: true,
    },
  ],
  reason_changes: { removed: ["ACTIVE_CONTRACT_RESTRICTION"] },
  evidence_changes: { changed: ["contract"] },
  trace_changes: { edge_count_delta: 0 },
};
