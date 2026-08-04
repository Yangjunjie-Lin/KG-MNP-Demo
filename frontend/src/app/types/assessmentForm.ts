export interface AssessmentFormValues {
  schemaVersion: "1.0";
  caseId: string;
  assessmentTime: string;
  subscriber: {
    subscriberId: string;
  };
  phoneNumber: {
    maskedNumber: string;
  };
  account: {
    accountId: string;
  };
  evidence: {
    identity: EvidenceFormBase & {
      matched: "true" | "false";
    };
    numberStatus: EvidenceFormBase & {
      statusCode: string;
    };
    billing: EvidenceFormBase & {
      outstandingAmount: string;
      currency: string;
      hasPaymentArrangement: "true" | "false";
    };
    contract: EvidenceFormBase & {
      contractStatus: string;
      contractEndTime: string;
    };
    portingHistory: EvidenceFormBase & {
      daysSinceLastPort: string;
    };
  };
  /** Optional workflow metadata. Omitted entirely when the section is blank. */
  process?: ProcessFormValues;
}

export interface ProcessFormValues {
  currentStep: string;
  authorizationCode: {
    status: "" | "VALID" | "EXPIRED" | "MISSING" | "USED" | "REVOKED";
    issuedAt: string;
    validUntil: string;
    maskedValue: string;
  };
  terminationAgreement: {
    signedAt: string;
    effectiveAt: string;
    status: string;
  };
}

export type EvidenceFormStatus = "VALID" | "EXPIRED" | "REVOKED" | "UNKNOWN";

interface EvidenceFormBase {
  sourceSystem: string;
  generatedAt: string;
  validUntil: string;
  status: EvidenceFormStatus;
}

export const emptyAssessmentFormValues: AssessmentFormValues = {
  schemaVersion: "1.0",
  caseId: "",
  assessmentTime: "",
  subscriber: { subscriberId: "" },
  phoneNumber: { maskedNumber: "" },
  account: { accountId: "" },
  evidence: {
    identity: {
      matched: "true",
      sourceSystem: "CRM",
      generatedAt: "",
      validUntil: "",
      status: "VALID",
    },
    numberStatus: {
      statusCode: "ACTIVE",
      sourceSystem: "HLR",
      generatedAt: "",
      validUntil: "",
      status: "VALID",
    },
    billing: {
      outstandingAmount: "0",
      currency: "CNY",
      hasPaymentArrangement: "false",
      sourceSystem: "BILLING",
      generatedAt: "",
      validUntil: "",
      status: "VALID",
    },
    contract: {
      contractStatus: "ACTIVE",
      contractEndTime: "",
      sourceSystem: "CONTRACT",
      generatedAt: "",
      validUntil: "",
      status: "VALID",
    },
    portingHistory: {
      daysSinceLastPort: "0",
      sourceSystem: "MNP_HISTORY",
      generatedAt: "",
      validUntil: "",
      status: "VALID",
    },
  },
};
