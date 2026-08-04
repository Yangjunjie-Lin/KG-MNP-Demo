import type { components } from "../generated/schema";
import {
  type AssessmentFormValues,
  type EvidenceFormStatus,
  type ProcessFormValues,
} from "../../app/types/assessmentForm";

export type AssessmentPayloadDto = components["schemas"]["MNPCaseInput"];
type ProcessPayloadDto = NonNullable<AssessmentPayloadDto["process"]>;

const evidenceStatuses = new Set<EvidenceFormStatus>([
  "VALID",
  "EXPIRED",
  "REVOKED",
  "UNKNOWN",
]);

function isRecord(value: unknown): value is Record<string, unknown> {
  return value !== null && typeof value === "object" && !Array.isArray(value);
}

function isNonEmptyString(value: unknown): value is string {
  return typeof value === "string" && value.trim().length > 0;
}

function isDateTime(value: unknown): value is string {
  return isNonEmptyString(value) && !Number.isNaN(new Date(value).getTime());
}

function isEvidenceStatus(value: unknown): value is EvidenceFormStatus {
  return typeof value === "string" && evidenceStatuses.has(value as EvidenceFormStatus);
}

function hasEvidenceBase(value: unknown): value is Record<string, unknown> {
  if (!isRecord(value)) return false;
  return (
    isNonEmptyString(value.source_system) &&
    isDateTime(value.generated_at) &&
    isDateTime(value.valid_until) &&
    isEvidenceStatus(value.status)
  );
}

function isFiniteNumberLike(value: unknown): boolean {
  if (typeof value === "number") return Number.isFinite(value);
  return typeof value === "string" && value.trim() !== "" && Number.isFinite(Number(value));
}

function isOptionalDateTime(value: unknown): boolean {
  return value === undefined || value === null || isDateTime(value);
}

function isOptionalProcess(value: unknown): boolean {
  if (value === undefined || value === null) return true;
  if (!isRecord(value)) return false;
  const auth = value.authorization_code;
  const term = value.termination_agreement;
  if (auth !== undefined && auth !== null) {
    if (!isRecord(auth)) return false;
    if (auth.status !== undefined && !isNonEmptyString(auth.status)) return false;
    if (!isOptionalDateTime(auth.issued_at) || !isOptionalDateTime(auth.valid_until)) return false;
    if (auth.masked_value !== undefined && auth.masked_value !== null && !isNonEmptyString(auth.masked_value)) return false;
  }
  if (term !== undefined && term !== null) {
    if (!isRecord(term)) return false;
    if (!isOptionalDateTime(term.signed_at) || !isOptionalDateTime(term.effective_at)) return false;
    if (term.status !== undefined && term.status !== null && !isNonEmptyString(term.status)) return false;
  }
  return value.current_step === undefined || value.current_step === null || isNonEmptyString(value.current_step);
}

export function isAssessmentPayloadDto(value: unknown): value is AssessmentPayloadDto {
  if (!isRecord(value)) return false;
  const subscriber = value.subscriber;
  const phoneNumber = value.phone_number;
  const account = value.account;
  const evidence = value.evidence;
  if (!isRecord(subscriber) || !isRecord(phoneNumber) || !isRecord(account) || !isRecord(evidence)) {
    return false;
  }

  const identity = evidence.identity;
  const numberStatus = evidence.number_status;
  const billing = evidence.billing;
  const contract = evidence.contract;
  const portingHistory = evidence.porting_history;
  if (
    !hasEvidenceBase(identity) ||
    !hasEvidenceBase(numberStatus) ||
    !hasEvidenceBase(billing) ||
    !hasEvidenceBase(contract) ||
    !hasEvidenceBase(portingHistory)
  ) {
    return false;
  }

  const contractEndTime = contract.contract_end_time;
  return (
    value.schema_version === "1.0" &&
    isNonEmptyString(value.case_id) &&
    isDateTime(value.assessment_time) &&
    isNonEmptyString(subscriber.subscriber_id) &&
    isNonEmptyString(phoneNumber.masked_number) &&
    isNonEmptyString(account.account_id) &&
    typeof identity.matched === "boolean" &&
    isNonEmptyString(numberStatus.status_code) &&
    isFiniteNumberLike(billing.outstanding_amount) &&
    isNonEmptyString(billing.currency) &&
    typeof billing.has_payment_arrangement === "boolean" &&
    isNonEmptyString(contract.contract_status) &&
    (contractEndTime === undefined || contractEndTime === null || isDateTime(contractEndTime)) &&
    typeof portingHistory.days_since_last_port === "number" &&
    Number.isInteger(portingHistory.days_since_last_port) &&
    portingHistory.days_since_last_port >= 0 &&
    isOptionalProcess(value.process)
  );
}

export function parseAssessmentPayload(value: unknown): AssessmentPayloadDto {
  if (!isAssessmentPayloadDto(value)) {
    throw new Error("INVALID_ASSESSMENT_PAYLOAD");
  }
  return value;
}

function pad(value: number): string {
  return String(value).padStart(2, "0");
}

export function isoToLocalDateTime(value: string | null | undefined): string {
  if (!value) return "";
  const date = new Date(value);
  if (Number.isNaN(date.getTime())) return "";
  return [
    `${date.getFullYear()}-${pad(date.getMonth() + 1)}-${pad(date.getDate())}`,
    `${pad(date.getHours())}:${pad(date.getMinutes())}:${pad(date.getSeconds())}`,
  ].join("T");
}

export function localDateTimeToIso(value: string): string {
  const date = new Date(value);
  if (Number.isNaN(date.getTime())) {
    throw new Error("INVALID_LOCAL_DATE_TIME");
  }
  return date.toISOString();
}

export function adaptExamplePayloadToAssessmentForm(input: unknown): AssessmentFormValues {
  const payload = parseAssessmentPayload(input);
  const process = payload.process;
  const auth = process?.authorization_code;
  const termination = process?.termination_agreement;
  return {
    schemaVersion: "1.0",
    caseId: payload.case_id,
    assessmentTime: isoToLocalDateTime(payload.assessment_time),
    subscriber: { subscriberId: payload.subscriber.subscriber_id },
    phoneNumber: { maskedNumber: payload.phone_number.masked_number },
    account: { accountId: payload.account.account_id },
    evidence: {
      identity: {
        matched: payload.evidence.identity.matched ? "true" : "false",
        sourceSystem: payload.evidence.identity.source_system,
        generatedAt: isoToLocalDateTime(payload.evidence.identity.generated_at),
        validUntil: isoToLocalDateTime(payload.evidence.identity.valid_until),
        status: payload.evidence.identity.status,
      },
      numberStatus: {
        statusCode: payload.evidence.number_status.status_code,
        sourceSystem: payload.evidence.number_status.source_system,
        generatedAt: isoToLocalDateTime(payload.evidence.number_status.generated_at),
        validUntil: isoToLocalDateTime(payload.evidence.number_status.valid_until),
        status: payload.evidence.number_status.status,
      },
      billing: {
        outstandingAmount: String(payload.evidence.billing.outstanding_amount),
        currency: payload.evidence.billing.currency,
        hasPaymentArrangement: payload.evidence.billing.has_payment_arrangement ? "true" : "false",
        sourceSystem: payload.evidence.billing.source_system,
        generatedAt: isoToLocalDateTime(payload.evidence.billing.generated_at),
        validUntil: isoToLocalDateTime(payload.evidence.billing.valid_until),
        status: payload.evidence.billing.status,
      },
      contract: {
        contractStatus: payload.evidence.contract.contract_status,
        contractEndTime: isoToLocalDateTime(payload.evidence.contract.contract_end_time),
        sourceSystem: payload.evidence.contract.source_system,
        generatedAt: isoToLocalDateTime(payload.evidence.contract.generated_at),
        validUntil: isoToLocalDateTime(payload.evidence.contract.valid_until),
        status: payload.evidence.contract.status,
      },
      portingHistory: {
        daysSinceLastPort: String(payload.evidence.porting_history.days_since_last_port),
        sourceSystem: payload.evidence.porting_history.source_system,
        generatedAt: isoToLocalDateTime(payload.evidence.porting_history.generated_at),
        validUntil: isoToLocalDateTime(payload.evidence.porting_history.valid_until),
        status: payload.evidence.porting_history.status,
      },
    },
    ...(process
      ? {
          process: {
            currentStep: process.current_step ?? "",
            authorizationCode: {
              status: auth?.status ?? "",
              issuedAt: isoToLocalDateTime(auth?.issued_at),
              validUntil: isoToLocalDateTime(auth?.valid_until),
              maskedValue: auth?.masked_value ?? "",
            },
            terminationAgreement: {
              signedAt: isoToLocalDateTime(termination?.signed_at),
              effectiveAt: isoToLocalDateTime(termination?.effective_at),
              status: termination?.status ?? "",
            },
          } satisfies ProcessFormValues,
        }
      : {}),
  };
}

function requiredNumber(value: string): number {
  const parsed = Number(value);
  if (!Number.isFinite(parsed)) throw new Error("INVALID_NUMBER");
  return parsed;
}

function requiredNonNegativeInteger(value: string): number {
  const parsed = requiredNumber(value);
  if (!Number.isInteger(parsed) || parsed < 0) throw new Error("INVALID_NON_NEGATIVE_INTEGER");
  return parsed;
}

function optionalText(value: string | null | undefined): string | undefined {
  const trimmed = value?.trim() ?? "";
  return trimmed ? trimmed : undefined;
}

function optionalDateTime(value: string | null | undefined): string | undefined {
  const supplied = optionalText(value);
  return supplied ? localDateTimeToIso(supplied) : undefined;
}

function optionalProcess(values: ProcessFormValues | undefined): ProcessPayloadDto | undefined {
  if (!values) return undefined;
  const process: ProcessPayloadDto = {};
  const currentStep = optionalText(values.currentStep);
  if (currentStep) process.current_step = currentStep;

  const auth = values.authorizationCode ?? {
    status: "",
    issuedAt: "",
    validUntil: "",
    maskedValue: "",
  };
  const authorizationCode: NonNullable<ProcessPayloadDto["authorization_code"]> = {};
  if (auth.status) authorizationCode.status = auth.status;
  const issuedAt = optionalDateTime(auth.issuedAt);
  const validUntil = optionalDateTime(auth.validUntil);
  const maskedValue = optionalText(auth.maskedValue);
  if (issuedAt) authorizationCode.issued_at = issuedAt;
  if (validUntil) authorizationCode.valid_until = validUntil;
  if (maskedValue) authorizationCode.masked_value = maskedValue;
  if (Object.keys(authorizationCode).length) process.authorization_code = authorizationCode;

  const term = values.terminationAgreement ?? { signedAt: "", effectiveAt: "", status: "" };
  const terminationAgreement: NonNullable<ProcessPayloadDto["termination_agreement"]> = {};
  const signedAt = optionalDateTime(term.signedAt);
  const effectiveAt = optionalDateTime(term.effectiveAt);
  const status = optionalText(term.status);
  if (signedAt) terminationAgreement.signed_at = signedAt;
  if (effectiveAt) terminationAgreement.effective_at = effectiveAt;
  if (status) terminationAgreement.status = status;
  if (Object.keys(terminationAgreement).length) process.termination_agreement = terminationAgreement;

  return Object.keys(process).length ? process : undefined;
}

export function adaptAssessmentFormToPayload(values: AssessmentFormValues): AssessmentPayloadDto {
  const payload: AssessmentPayloadDto = {
    schema_version: values.schemaVersion,
    case_id: values.caseId,
    assessment_time: localDateTimeToIso(values.assessmentTime),
    subscriber: { subscriber_id: values.subscriber.subscriberId },
    phone_number: { masked_number: values.phoneNumber.maskedNumber },
    account: { account_id: values.account.accountId },
    evidence: {
      identity: {
        matched: values.evidence.identity.matched === "true",
        source_system: values.evidence.identity.sourceSystem,
        generated_at: localDateTimeToIso(values.evidence.identity.generatedAt),
        valid_until: localDateTimeToIso(values.evidence.identity.validUntil),
        status: values.evidence.identity.status,
      },
      number_status: {
        status_code: values.evidence.numberStatus.statusCode,
        source_system: values.evidence.numberStatus.sourceSystem,
        generated_at: localDateTimeToIso(values.evidence.numberStatus.generatedAt),
        valid_until: localDateTimeToIso(values.evidence.numberStatus.validUntil),
        status: values.evidence.numberStatus.status,
      },
      billing: {
        outstanding_amount: requiredNumber(values.evidence.billing.outstandingAmount),
        currency: values.evidence.billing.currency,
        has_payment_arrangement: values.evidence.billing.hasPaymentArrangement === "true",
        source_system: values.evidence.billing.sourceSystem,
        generated_at: localDateTimeToIso(values.evidence.billing.generatedAt),
        valid_until: localDateTimeToIso(values.evidence.billing.validUntil),
        status: values.evidence.billing.status,
      },
      contract: {
        contract_status: values.evidence.contract.contractStatus,
        contract_end_time: values.evidence.contract.contractEndTime
          ? localDateTimeToIso(values.evidence.contract.contractEndTime)
          : null,
        source_system: values.evidence.contract.sourceSystem,
        generated_at: localDateTimeToIso(values.evidence.contract.generatedAt),
        valid_until: localDateTimeToIso(values.evidence.contract.validUntil),
        status: values.evidence.contract.status,
      },
      porting_history: {
        days_since_last_port: requiredNonNegativeInteger(
          values.evidence.portingHistory.daysSinceLastPort,
        ),
        source_system: values.evidence.portingHistory.sourceSystem,
        generated_at: localDateTimeToIso(values.evidence.portingHistory.generatedAt),
        valid_until: localDateTimeToIso(values.evidence.portingHistory.validUntil),
        status: values.evidence.portingHistory.status,
      },
    },
  };
  const process = optionalProcess(values.process);
  if (process) payload.process = process;
  return payload;
}

export function formatTechnicalAssessmentPayload(input: unknown): string {
  return JSON.stringify(parseAssessmentPayload(input), null, 2);
}

export function parseTechnicalAssessmentPayload(source: string): AssessmentPayloadDto {
  return parseAssessmentPayload(JSON.parse(source) as unknown);
}
