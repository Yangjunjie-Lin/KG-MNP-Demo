import type { EligibilityRule } from "../types/rules";
import { ruleLabels } from "../i18n/zh-CN";

export const mockRules: EligibilityRule[] = [
  {
    ruleId: "MNP-ELIG-001",
    version: "1.0",
    name: ruleLabels["MNP-ELIG-001"],
    effectiveFrom: "2024-01-01T00:00:00Z",
    effectiveTo: null,
    reasonCode: "REAL_NAME_MISMATCH",
    actionCode: "VERIFY_IDENTITY",
    regulatoryClause: "REG-MNP-CLAUSE-01",
    checkDescription: "实名一致性标志必须为真",
    inputEvidenceTypes: ["IDENTITY_MATCH"],
    inputs: [
      {
        evidenceType: "IDENTITY_MATCH",
        required: true,
        fields: [
          "identityMatchFlag",
          "evidenceStatus",
          "evidenceGeneratedAt",
          "evidenceValidUntil",
        ],
      },
    ],
    decisionWhenPass: "ELIGIBLE",
    decisionWhenFail: "BLOCKED",
    missingEvidenceAction: "MANUAL_REVIEW",
  },
  {
    ruleId: "MNP-ELIG-002",
    version: "1.0",
    name: ruleLabels["MNP-ELIG-002"],
    effectiveFrom: "2024-01-01T00:00:00Z",
    effectiveTo: null,
    reasonCode: "NUMBER_STATUS_INVALID",
    actionCode: "RESTORE_NUMBER_STATUS",
    regulatoryClause: "REG-MNP-CLAUSE-02",
    checkDescription: "号码状态须为正常",
    inputEvidenceTypes: ["NUMBER_STATUS"],
    inputs: [
      {
        evidenceType: "NUMBER_STATUS",
        required: true,
        fields: [
          "numberStatusCode",
          "evidenceStatus",
          "evidenceGeneratedAt",
          "evidenceValidUntil",
        ],
      },
    ],
    decisionWhenPass: "ELIGIBLE",
    decisionWhenFail: "BLOCKED",
    missingEvidenceAction: "MANUAL_REVIEW",
  },
  {
    ruleId: "MNP-ELIG-003",
    version: "1.0",
    name: ruleLabels["MNP-ELIG-003"],
    effectiveFrom: "2024-01-01T00:00:00Z",
    effectiveTo: null,
    reasonCode: "OUTSTANDING_BALANCE",
    actionCode: "SETTLE_OUTSTANDING_FEES",
    regulatoryClause: "REG-MNP-CLAUSE-03",
    checkDescription: "未结费用须为零，或存在有效缴费安排",
    inputEvidenceTypes: ["BILLING_BALANCE"],
    inputs: [
      {
        evidenceType: "BILLING_BALANCE",
        required: true,
        fields: [
          "observedAmount",
          "currencyCode",
          "hasPaymentArrangement",
          "evidenceStatus",
          "evidenceGeneratedAt",
          "evidenceValidUntil",
        ],
      },
    ],
    decisionWhenPass: "ELIGIBLE",
    decisionWhenFail: "BLOCKED",
    missingEvidenceAction: "MANUAL_REVIEW",
  },
  {
    ruleId: "MNP-ELIG-004",
    version: "1.0",
    name: ruleLabels["MNP-ELIG-004"],
    effectiveFrom: "2024-01-01T00:00:00Z",
    effectiveTo: null,
    reasonCode: "ACTIVE_CONTRACT_RESTRICTION",
    actionCode: "WAIT_OR_TERMINATE_CONTRACT",
    regulatoryClause: "REG-MNP-CLAUSE-04",
    checkDescription: "合约在评估时点不得构成有效限制",
    inputEvidenceTypes: ["CONTRACT_STATUS"],
    inputs: [
      {
        evidenceType: "CONTRACT_STATUS",
        required: true,
        fields: [
          "contractStatusCode",
          "contractEndTime",
          "evidenceStatus",
          "evidenceGeneratedAt",
          "evidenceValidUntil",
        ],
      },
    ],
    decisionWhenPass: "ELIGIBLE",
    decisionWhenFail: "BLOCKED",
    missingEvidenceAction: "MANUAL_REVIEW",
  },
  {
    ruleId: "MNP-ELIG-005",
    version: "1.0",
    name: ruleLabels["MNP-ELIG-005@1.0"],
    effectiveFrom: "2024-01-01T00:00:00Z",
    effectiveTo: "2026-05-31T23:59:59Z",
    reasonCode: "PORTING_INTERVAL_TOO_SHORT",
    actionCode: "WAIT_PORTING_INTERVAL",
    regulatoryClause: "REG-MNP-CLAUSE-05",
    checkDescription: "距上次携转不少于 120 天",
    inputEvidenceTypes: ["PORTING_HISTORY"],
    inputs: [
      {
        evidenceType: "PORTING_HISTORY",
        required: true,
        fields: [
          "daysSinceLastPort",
          "evidenceStatus",
          "evidenceGeneratedAt",
          "evidenceValidUntil",
        ],
      },
    ],
    decisionWhenPass: "ELIGIBLE",
    decisionWhenFail: "BLOCKED",
    missingEvidenceAction: "MANUAL_REVIEW",
    checkMinimum: 120,
  },
  {
    ruleId: "MNP-ELIG-005",
    version: "1.1",
    name: ruleLabels["MNP-ELIG-005@1.1"],
    effectiveFrom: "2026-06-01T00:00:00Z",
    effectiveTo: null,
    reasonCode: "PORTING_INTERVAL_TOO_SHORT",
    actionCode: "WAIT_PORTING_INTERVAL",
    regulatoryClause: "REG-MNP-CLAUSE-05",
    checkDescription: "距上次携转不少于 180 天（收紧后）",
    inputEvidenceTypes: ["PORTING_HISTORY"],
    inputs: [
      {
        evidenceType: "PORTING_HISTORY",
        required: true,
        fields: [
          "daysSinceLastPort",
          "evidenceStatus",
          "evidenceGeneratedAt",
          "evidenceValidUntil",
        ],
      },
    ],
    decisionWhenPass: "ELIGIBLE",
    decisionWhenFail: "BLOCKED",
    missingEvidenceAction: "MANUAL_REVIEW",
    supersedesVersion: "1.0",
    checkMinimum: 180,
  },
];

export function getRuleByIdVersion(
  ruleId: string,
  version?: string,
): EligibilityRule | undefined {
  if (version) {
    return mockRules.find((r) => r.ruleId === ruleId && r.version === version);
  }
  const matches = mockRules.filter((r) => r.ruleId === ruleId);
  return matches[matches.length - 1];
}
