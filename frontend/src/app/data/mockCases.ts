import type {
  BlockingReasonDetail,
  CaseDetail,
  CaseSummary,
  EvidenceItem,
  RuleResult,
} from "../types/assessment";
import type { EvidenceStatus, PublicationStatus } from "../types/common";

function evidenceBase(
  caseNum: string,
  kind: "IDENTITY" | "NUMBER" | "BILLING" | "CONTRACT" | "PORTING",
  type: string,
  source: string,
  status: EvidenceStatus,
  generatedAt: string,
  validUntil: string,
  valueSummary: string,
  extra: Partial<EvidenceItem> = {},
): EvidenceItem {
  return {
    evidenceId: `Evidence-CASE-${caseNum}-${kind}`,
    evidenceType: type,
    sourceSystem: source,
    status,
    generatedAt,
    validUntil,
    valueSummary,
    ...extra,
  };
}

function passRules(selectedPortingVersion = "1.1"): RuleResult[] {
  return [
    {
      ruleId: "MNP-ELIG-001",
      version: "1.0",
      status: "PASS",
      effectiveFrom: "2024-01-01T00:00:00Z",
      effectiveTo: null,
      selectedForAssessmentTime: true,
    },
    {
      ruleId: "MNP-ELIG-002",
      version: "1.0",
      status: "PASS",
      effectiveFrom: "2024-01-01T00:00:00Z",
      effectiveTo: null,
      selectedForAssessmentTime: true,
    },
    {
      ruleId: "MNP-ELIG-003",
      version: "1.0",
      status: "PASS",
      effectiveFrom: "2024-01-01T00:00:00Z",
      effectiveTo: null,
      selectedForAssessmentTime: true,
    },
    {
      ruleId: "MNP-ELIG-004",
      version: "1.0",
      status: "PASS",
      effectiveFrom: "2024-01-01T00:00:00Z",
      effectiveTo: null,
      selectedForAssessmentTime: true,
    },
    {
      ruleId: "MNP-ELIG-005",
      version: selectedPortingVersion,
      status: "PASS",
      effectiveFrom:
        selectedPortingVersion === "1.0"
          ? "2024-01-01T00:00:00Z"
          : "2026-06-01T00:00:00Z",
      effectiveTo:
        selectedPortingVersion === "1.0" ? "2026-05-31T23:59:59Z" : null,
      selectedForAssessmentTime: true,
    },
  ];
}

function withFail(
  results: RuleResult[],
  ruleId: string,
  reasonCode: string,
  actionCode: string,
  clause: string,
  version = "1.0",
): RuleResult[] {
  return results.map((r) =>
    r.ruleId === ruleId && r.version === version
      ? {
          ...r,
          status: "FAIL" as const,
          reasonCode,
          actionCode,
          regulatoryClause: clause,
        }
      : r,
  );
}

function withSkip(
  results: RuleResult[],
  ruleId: string,
  version = "1.0",
): RuleResult[] {
  return results.map((r) =>
    r.ruleId === ruleId && r.version === version
      ? { ...r, status: "SKIP" as const }
      : r,
  );
}

function blocking(
  reasonCode: string,
  ruleId: string,
  ruleVersion: string,
  clause: string,
  actionCode: string,
  evidenceIds: string[],
  description: string,
): BlockingReasonDetail {
  return {
    reasonCode,
    ruleId,
    ruleVersion,
    regulatoryClause: clause,
    actionCode,
    evidenceIds,
    description,
  };
}

function pub(published: boolean): PublicationStatus {
  return published ? "PUBLISHABLE" : "NOT_PUBLISHABLE";
}

const defaultIdentity = (n: string, matched = true): EvidenceItem =>
  evidenceBase(
    n,
    "IDENTITY",
    "IDENTITY_MATCH",
    "CRM",
    "VALID",
    "2026-06-20T10:00:00Z",
    "2026-12-31T23:59:59Z",
    matched ? "实名一致：是" : "实名一致：否",
    { identityMatchFlag: matched },
  );

const defaultNumber = (n: string): EvidenceItem =>
  evidenceBase(
    n,
    "NUMBER",
    "NUMBER_STATUS",
    "HLR",
    "VALID",
    "2026-06-20T10:05:00Z",
    "2026-12-31T23:59:59Z",
    "号码状态：正常",
    { numberStatusCode: "ACTIVE" },
  );

const defaultBilling = (
  n: string,
  amount: number,
  status: EvidenceStatus = "VALID",
  generatedAt = "2026-06-20T10:10:00Z",
  validUntil = "2026-12-31T23:59:59Z",
): EvidenceItem =>
  evidenceBase(
    n,
    "BILLING",
    "BILLING_BALANCE",
    "BILLING",
    status,
    generatedAt,
    validUntil,
    `未结费用：${amount} 元`,
    {
      outstandingAmount: amount,
      currencyCode: "CNY",
      hasPaymentArrangement: false,
    },
  );

const defaultContract = (
  n: string,
  statusCode: string,
  endTime: string,
): EvidenceItem =>
  evidenceBase(
    n,
    "CONTRACT",
    "CONTRACT_STATUS",
    "CONTRACT",
    "VALID",
    "2026-06-20T10:15:00Z",
    "2026-12-31T23:59:59Z",
    `合约状态：${statusCode === "ACTIVE" ? "有效" : "已到期"}，到期：${endTime.slice(0, 10)}`,
    { contractStatusCode: statusCode, contractEndTime: endTime },
  );

const defaultPorting = (n: string, days: number): EvidenceItem =>
  evidenceBase(
    n,
    "PORTING",
    "PORTING_HISTORY",
    "MNP_HISTORY",
    "VALID",
    "2026-06-20T10:20:00Z",
    "2026-12-31T23:59:59Z",
    `距上次携转：${days} 天`,
    { daysSinceLastPort: days },
  );

function makeCase(partial: CaseDetail): CaseDetail {
  return partial;
}

export const mockCases: CaseDetail[] = [
  makeCase({
    id: "CASE-01",
    title: "正常通过",
    scenario: "全部条件满足，可携转",
    decision: "ELIGIBLE",
    assessmentTime: "2026-07-01T00:00:00Z",
    blockingReasons: [],
    executionCount: 1,
    published: true,
    publicationStatus: pub(true),
    maskedNumber: "138****0001",
    daysSinceLastPort: 400,
    subscriberId: "SUB-01",
    accountId: "ACC-01",
    evidence: [
      defaultIdentity("01"),
      defaultNumber("01"),
      defaultBilling("01", 0),
      defaultContract("01", "EXPIRED", "2025-01-01T00:00:00Z"),
      defaultPorting("01", 400),
    ],
    ruleResults: passRules("1.1"),
    blockingReasonDetails: [],
    process: {
      currentStep: "AUTHORIZATION_CODE_REQUEST",
      nextStep: "PORT_IN_SUBMISSION",
      canAdvance: true,
      processBlockingReasons: [],
      eligibilityDecision: "ELIGIBLE",
    },
  }),
  makeCase({
    id: "CASE-02",
    title: "存在未结清费用",
    scenario: "存在未结清费用",
    decision: "BLOCKED",
    assessmentTime: "2026-07-01T00:00:00Z",
    blockingReasons: ["OUTSTANDING_BALANCE"],
    executionCount: 1,
    published: true,
    publicationStatus: pub(true),
    maskedNumber: "138****0002",
    daysSinceLastPort: 300,
    subscriberId: "SUB-02",
    accountId: "ACC-02",
    evidence: [
      defaultIdentity("02"),
      defaultNumber("02"),
      defaultBilling("02", 128.5),
      defaultContract("02", "EXPIRED", "2025-06-01T00:00:00Z"),
      defaultPorting("02", 300),
    ],
    ruleResults: withFail(
      passRules("1.1"),
      "MNP-ELIG-003",
      "OUTSTANDING_BALANCE",
      "SETTLE_OUTSTANDING_FEES",
      "REG-MNP-CLAUSE-03",
    ),
    blockingReasonDetails: [
      blocking(
        "OUTSTANDING_BALANCE",
        "MNP-ELIG-003",
        "1.0",
        "REG-MNP-CLAUSE-03",
        "SETTLE_OUTSTANDING_FEES",
        ["Evidence-CASE-02-BILLING"],
        "存在未结清欠费且无有效缴费安排，因此规则未通过。",
      ),
    ],
    process: {
      currentStep: "ELIGIBILITY_CHECK",
      nextStep: "AUTHORIZATION_CODE_REQUEST",
      canAdvance: false,
      processBlockingReasons: [
        { code: "ELIGIBILITY_NOT_PASSED", message: "资格评估未通过，不能进入授权码或提交阶段。" },
      ],
      eligibilityDecision: "BLOCKED",
    },
  }),
  makeCase({
    id: "CASE-03",
    title: "合约仍有效",
    scenario: "合约仍有效",
    decision: "BLOCKED",
    assessmentTime: "2026-07-01T00:00:00Z",
    blockingReasons: ["ACTIVE_CONTRACT_RESTRICTION"],
    executionCount: 1,
    published: true,
    publicationStatus: pub(true),
    maskedNumber: "138****0003",
    daysSinceLastPort: 250,
    subscriberId: "SUB-03",
    accountId: "ACC-03",
    evidence: [
      defaultIdentity("03"),
      defaultNumber("03"),
      defaultBilling("03", 0),
      defaultContract("03", "ACTIVE", "2027-01-01T00:00:00Z"),
      defaultPorting("03", 250),
    ],
    ruleResults: withFail(
      passRules("1.1"),
      "MNP-ELIG-004",
      "ACTIVE_CONTRACT_RESTRICTION",
      "WAIT_OR_TERMINATE_CONTRACT",
      "REG-MNP-CLAUSE-04",
    ),
    blockingReasonDetails: [
      blocking(
        "ACTIVE_CONTRACT_RESTRICTION",
        "MNP-ELIG-004",
        "1.0",
        "REG-MNP-CLAUSE-04",
        "WAIT_OR_TERMINATE_CONTRACT",
        ["Evidence-CASE-03-CONTRACT"],
        "合约在评估时点仍有效，因此规则未通过。",
      ),
    ],
    process: {
      currentStep: "ELIGIBILITY_CHECK",
      nextStep: "AUTHORIZATION_CODE_REQUEST",
      canAdvance: false,
      processBlockingReasons: [
        { code: "ELIGIBILITY_NOT_PASSED", message: "资格评估未通过，不能进入授权码或提交阶段。" },
      ],
      eligibilityDecision: "BLOCKED",
    },
  }),
  makeCase({
    id: "CASE-04",
    title: "多阻塞原因并存",
    scenario: "多阻塞原因并存",
    decision: "BLOCKED",
    assessmentTime: "2026-07-01T00:00:00Z",
    blockingReasons: ["OUTSTANDING_BALANCE", "ACTIVE_CONTRACT_RESTRICTION"],
    executionCount: 1,
    published: true,
    publicationStatus: pub(true),
    maskedNumber: "138****0004",
    daysSinceLastPort: 200,
    subscriberId: "SUB-04",
    accountId: "ACC-04",
    evidence: [
      defaultIdentity("04"),
      defaultNumber("04"),
      defaultBilling("04", 88),
      defaultContract("04", "ACTIVE", "2027-06-01T00:00:00Z"),
      defaultPorting("04", 200),
    ],
    ruleResults: withFail(
      withFail(
        passRules("1.1"),
        "MNP-ELIG-003",
        "OUTSTANDING_BALANCE",
        "SETTLE_OUTSTANDING_FEES",
        "REG-MNP-CLAUSE-03",
      ),
      "MNP-ELIG-004",
      "ACTIVE_CONTRACT_RESTRICTION",
      "WAIT_OR_TERMINATE_CONTRACT",
      "REG-MNP-CLAUSE-04",
    ),
    blockingReasonDetails: [
      blocking(
        "OUTSTANDING_BALANCE",
        "MNP-ELIG-003",
        "1.0",
        "REG-MNP-CLAUSE-03",
        "SETTLE_OUTSTANDING_FEES",
        ["Evidence-CASE-04-BILLING"],
        "存在未结清欠费且无有效缴费安排，因此规则未通过。",
      ),
      blocking(
        "ACTIVE_CONTRACT_RESTRICTION",
        "MNP-ELIG-004",
        "1.0",
        "REG-MNP-CLAUSE-04",
        "WAIT_OR_TERMINATE_CONTRACT",
        ["Evidence-CASE-04-CONTRACT"],
        "合约在评估时点仍有效，因此规则未通过。",
      ),
    ],
    process: {
      currentStep: "ELIGIBILITY_CHECK",
      nextStep: "AUTHORIZATION_CODE_REQUEST",
      canAdvance: false,
      processBlockingReasons: [
        { code: "ELIGIBILITY_NOT_PASSED", message: "资格评估未通过，不能进入授权码或提交阶段。" },
      ],
      eligibilityDecision: "BLOCKED",
    },
  }),
  makeCase({
    id: "CASE-05",
    title: "关键证据缺失或过期",
    scenario: "关键证据缺失或过期",
    decision: "MANUAL_REVIEW",
    assessmentTime: "2026-07-01T00:00:00Z",
    blockingReasons: ["MISSING_OR_EXPIRED_EVIDENCE"],
    executionCount: 1,
    published: false,
    publicationStatus: pub(false),
    maskedNumber: "138****0005",
    daysSinceLastPort: 500,
    subscriberId: "SUB-05",
    accountId: "ACC-05",
    evidence: [
      defaultIdentity("05"),
      defaultNumber("05"),
      defaultBilling(
        "05",
        0,
        "EXPIRED",
        "2025-01-01T10:10:00Z",
        "2025-02-01T00:00:00Z",
      ),
      defaultContract("05", "EXPIRED", "2025-01-01T00:00:00Z"),
      defaultPorting("05", 500),
    ],
    ruleResults: withSkip(passRules("1.1"), "MNP-ELIG-003"),
    blockingReasonDetails: [
      blocking(
        "MISSING_OR_EXPIRED_EVIDENCE",
        "MNP-ELIG-003",
        "1.0",
        "REG-MNP-CLAUSE-03",
        "SETTLE_OUTSTANDING_FEES",
        ["Evidence-CASE-05-BILLING"],
        "计费证据已过期，因此需要人工复核。",
      ),
    ],
    process: {
      currentStep: "ELIGIBILITY_CHECK",
      nextStep: "AUTHORIZATION_CODE_REQUEST",
      canAdvance: false,
      processBlockingReasons: [
        { code: "ELIGIBILITY_NOT_PASSED", message: "资格评估未通过，不能进入授权码或提交阶段。" },
      ],
      eligibilityDecision: "MANUAL_REVIEW",
    },
  }),
  makeCase({
    id: "CASE-06",
    title: "规则版本更新后携转间隔不足",
    scenario: "规则版本更新后携转间隔不足",
    decision: "BLOCKED",
    assessmentTime: "2026-07-01T00:00:00Z",
    blockingReasons: ["PORTING_INTERVAL_TOO_SHORT"],
    executionCount: 2,
    published: true,
    publicationStatus: pub(true),
    maskedNumber: "138****0006",
    daysSinceLastPort: 150,
    subscriberId: "SUB-06",
    accountId: "ACC-06",
    evidence: [
      defaultIdentity("06"),
      defaultNumber("06"),
      defaultBilling("06", 0),
      defaultContract("06", "EXPIRED", "2025-01-01T00:00:00Z"),
      defaultPorting("06", 150),
    ],
    ruleResults: withFail(
      passRules("1.1"),
      "MNP-ELIG-005",
      "PORTING_INTERVAL_TOO_SHORT",
      "WAIT_PORTING_INTERVAL",
      "REG-MNP-CLAUSE-05",
      "1.1",
    ),
    blockingReasonDetails: [
      blocking(
        "PORTING_INTERVAL_TOO_SHORT",
        "MNP-ELIG-005",
        "1.1",
        "REG-MNP-CLAUSE-05",
        "WAIT_PORTING_INTERVAL",
        ["Evidence-CASE-06-PORTING"],
        "距上次携转 150 天，当前规则要求不少于 180 天。",
      ),
    ],
    historicalAssessment: {
      assessmentId: "ASSESS-CASE-06-HIST",
      assessmentTime: "2026-05-15T00:00:00Z",
      decision: "ELIGIBLE",
      ruleId: "MNP-ELIG-005",
      ruleVersion: "1.0",
      requiredDays: 120,
      observedDays: 150,
      note: "历史规则版本要求 120 天，当时结论为可携转。",
    },
    currentAssessmentNote: "当前规则版本要求 180 天，结论为不可携转。",
    process: {
      currentStep: "ELIGIBILITY_CHECK",
      nextStep: "AUTHORIZATION_CODE_REQUEST",
      canAdvance: false,
      processBlockingReasons: [
        { code: "ELIGIBILITY_NOT_PASSED", message: "资格评估未通过，不能进入授权码或提交阶段。" },
      ],
      eligibilityDecision: "BLOCKED",
    },
  }),
  makeCase({
    id: "CASE-07",
    title: "资格通过但授权码过期",
    scenario: "资格通过但授权码过期",
    decision: "ELIGIBLE",
    assessmentTime: "2026-07-01T00:00:00Z",
    blockingReasons: [],
    executionCount: 1,
    published: true,
    publicationStatus: pub(true),
    maskedNumber: "138****0007",
    daysSinceLastPort: 400,
    subscriberId: "SUB-07",
    accountId: "ACC-07",
    evidence: [
      defaultIdentity("07"),
      defaultNumber("07"),
      defaultBilling("07", 0),
      defaultContract("07", "EXPIRED", "2025-01-01T00:00:00Z"),
      defaultPorting("07", 400),
    ],
    ruleResults: passRules("1.1"),
    blockingReasonDetails: [],
    process: {
      currentStep: "AUTHORIZATION_CODE_REQUEST",
      nextStep: "PORT_IN_SUBMISSION",
      canAdvance: false,
      processBlockingReasons: [
        { code: "AUTHORIZATION_CODE_EXPIRED", message: "授权码已过期。" },
      ],
      authorizationCode: {
        status: "EXPIRED",
        issuedAt: "2026-06-01T00:00:00Z",
        validUntil: "2026-06-15T00:00:00Z",
        maskedValue: "****07",
      },
      eligibilityDecision: "ELIGIBLE",
    },
  }),
  makeCase({
    id: "CASE-08",
    title: "解除协议已签未生效",
    scenario: "解除协议已签未生效",
    decision: "BLOCKED",
    assessmentTime: "2026-07-01T00:00:00Z",
    blockingReasons: ["ACTIVE_CONTRACT_RESTRICTION"],
    executionCount: 1,
    published: false,
    publicationStatus: pub(false),
    maskedNumber: "138****0008",
    daysSinceLastPort: 400,
    subscriberId: "SUB-08",
    accountId: "ACC-08",
    evidence: [
      defaultIdentity("08"),
      defaultNumber("08"),
      defaultBilling("08", 0),
      defaultContract("08", "ACTIVE", "2027-06-01T00:00:00Z"),
      defaultPorting("08", 400),
    ],
    ruleResults: withFail(
      passRules("1.1"),
      "MNP-ELIG-004",
      "ACTIVE_CONTRACT_RESTRICTION",
      "WAIT_OR_TERMINATE_CONTRACT",
      "REG-MNP-CLAUSE-04",
    ),
    blockingReasonDetails: [
      blocking(
        "ACTIVE_CONTRACT_RESTRICTION",
        "MNP-ELIG-004",
        "1.0",
        "REG-MNP-CLAUSE-04",
        "WAIT_OR_TERMINATE_CONTRACT",
        ["Evidence-CASE-08-CONTRACT"],
        "合约仍有效；解除协议已签署但尚未生效。",
      ),
    ],
    process: {
      currentStep: "ELIGIBILITY_CHECK",
      nextStep: "AUTHORIZATION_CODE_REQUEST",
      canAdvance: false,
      processBlockingReasons: [
        { code: "ELIGIBILITY_NOT_PASSED", message: "资格评估未通过，不能进入授权码或提交阶段。" },
        { code: "TERMINATION_NOT_EFFECTIVE", message: "解除协议已签署但尚未生效。" },
      ],
      terminationAgreement: {
        signedAt: "2026-06-20T00:00:00Z",
        effectiveAt: "2026-08-01T00:00:00Z",
        status: "SIGNED_PENDING_EFFECTIVE",
      },
      eligibilityDecision: "BLOCKED",
    },
  }),
  makeCase({
    id: "CASE-09",
    title: "实名信息不一致",
    scenario: "实名信息不一致",
    decision: "BLOCKED",
    assessmentTime: "2026-07-01T00:00:00Z",
    blockingReasons: ["REAL_NAME_MISMATCH"],
    executionCount: 1,
    published: true,
    publicationStatus: pub(true),
    maskedNumber: "138****0009",
    daysSinceLastPort: 400,
    subscriberId: "SUB-09",
    accountId: "ACC-09",
    evidence: [
      defaultIdentity("09", false),
      defaultNumber("09"),
      defaultBilling("09", 0),
      defaultContract("09", "EXPIRED", "2025-01-01T00:00:00Z"),
      defaultPorting("09", 400),
    ],
    ruleResults: withFail(
      passRules("1.1"),
      "MNP-ELIG-001",
      "REAL_NAME_MISMATCH",
      "VERIFY_IDENTITY",
      "REG-MNP-CLAUSE-01",
    ),
    blockingReasonDetails: [
      blocking(
        "REAL_NAME_MISMATCH",
        "MNP-ELIG-001",
        "1.0",
        "REG-MNP-CLAUSE-01",
        "VERIFY_IDENTITY",
        ["Evidence-CASE-09-IDENTITY"],
        "实名信息不一致，因此规则未通过。",
      ),
    ],
    process: {
      currentStep: "ELIGIBILITY_CHECK",
      nextStep: "AUTHORIZATION_CODE_REQUEST",
      canAdvance: false,
      processBlockingReasons: [
        { code: "ELIGIBILITY_NOT_PASSED", message: "资格评估未通过，不能进入授权码或提交阶段。" },
      ],
      eligibilityDecision: "BLOCKED",
    },
  }),
];

export function toCaseSummary(c: CaseDetail): CaseSummary {
  return {
    id: c.id,
    title: c.title,
    scenario: c.scenario,
    decision: c.decision,
    assessmentTime: c.assessmentTime,
    blockingReasons: c.blockingReasons,
    executionCount: c.executionCount,
    published: c.published,
    publicationStatus: c.publicationStatus,
    maskedNumber: c.maskedNumber,
    daysSinceLastPort: c.daysSinceLastPort,
  };
}

export const mockCaseSummaries: CaseSummary[] = mockCases.map(toCaseSummary);

export function getMockCaseById(caseId: string): CaseDetail | undefined {
  return mockCases.find((c) => c.id === caseId);
}
