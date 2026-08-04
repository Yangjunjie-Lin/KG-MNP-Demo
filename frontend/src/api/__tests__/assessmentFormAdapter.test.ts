import { readFileSync } from "node:fs";
import { join } from "node:path";
import { describe, expect, it } from "vitest";
import { exampleInputFixture } from "../../mocks/fixtures/api";
import {
  adaptAssessmentFormToPayload,
  adaptExamplePayloadToAssessmentForm,
  formatTechnicalAssessmentPayload,
  isoToLocalDateTime,
  localDateTimeToIso,
  parseTechnicalAssessmentPayload,
} from "../adapters/assessmentFormAdapter";

describe("评估表单适配器", () => {
  it("以 camelCase 表单模型承接示例，并还原 OpenAPI 请求 DTO", () => {
    const form = adaptExamplePayloadToAssessmentForm(exampleInputFixture);

    expect(form.caseId).toBe("CASE-03");
    expect(form.evidence.billing.outstandingAmount).toBe("0");
    expect(form).not.toHaveProperty("case_id");

    const payload = adaptAssessmentFormToPayload(form);
    expect(payload.case_id).toBe("CASE-03");
    expect(payload.assessment_time).toBe(new Date(exampleInputFixture.assessment_time).toISOString());
    expect(payload.evidence.billing.outstanding_amount).toBe(0);
    expect(payload.evidence.billing.has_payment_arrangement).toBe(false);
    expect(payload.evidence.porting_history.days_since_last_port).toBe(250);
  });

  it("在 ISO 时间和浏览器本地 datetime-local 之间按本地时区往返", () => {
    const iso = "2026-07-01T00:00:00.000Z";
    const local = isoToLocalDateTime(iso);

    expect(local).toMatch(/^\d{4}-\d{2}-\d{2}T\d{2}:\d{2}:\d{2}$/u);
    expect(localDateTimeToIso(local)).toBe(iso);
  });

  it("技术 JSON 的解析和必填结构校验均由适配器完成", () => {
    const source = formatTechnicalAssessmentPayload(exampleInputFixture);
    expect(parseTechnicalAssessmentPayload(source).case_id).toBe("CASE-03");
    expect(() => parseTechnicalAssessmentPayload('{"case_id":"CASE-03"}')).toThrow(
      "INVALID_ASSESSMENT_PAYLOAD",
    );
    expect(() => parseTechnicalAssessmentPayload("not-json")).toThrow();
  });

  it("只序列化已填写的流程补充信息，空流程不发送 process", () => {
    const form = adaptExamplePayloadToAssessmentForm(exampleInputFixture);
    expect(adaptAssessmentFormToPayload(form)).not.toHaveProperty("process");

    const withProcess = {
      ...form,
      process: {
        currentStep: "AUTHORIZATION_CODE_REQUEST",
        authorizationCode: {
          status: "EXPIRED" as const,
          issuedAt: "2026-06-01T00:00:00",
          validUntil: "2026-06-15T00:00:00",
          maskedValue: "****07",
        },
        terminationAgreement: { signedAt: "", effectiveAt: "", status: "" },
      },
    };
    expect(adaptAssessmentFormToPayload(withProcess).process).toEqual({
      current_step: "AUTHORIZATION_CODE_REQUEST",
      authorization_code: {
        status: "EXPIRED",
        issued_at: new Date("2026-06-01T00:00:00").toISOString(),
        valid_until: new Date("2026-06-15T00:00:00").toISOString(),
        masked_value: "****07",
      },
    });
  });

  it("回填案例七授权码与案例八解除协议字段", () => {
    const base = exampleInputFixture;
    const case07 = adaptExamplePayloadToAssessmentForm({
      ...base,
      case_id: "CASE-07",
      process: {
        current_step: "AUTHORIZATION_CODE_REQUEST",
        authorization_code: {
          status: "EXPIRED",
          issued_at: "2026-06-01T00:00:00Z",
          valid_until: "2026-06-15T00:00:00Z",
          masked_value: "****07",
        },
      },
    });
    expect(case07.process?.authorizationCode.status).toBe("EXPIRED");

    const case08 = adaptExamplePayloadToAssessmentForm({
      ...base,
      case_id: "CASE-08",
      process: {
        current_step: "ELIGIBILITY_CHECK",
        termination_agreement: {
          signed_at: "2026-06-20T00:00:00Z",
          effective_at: "2026-08-01T00:00:00Z",
          status: "SIGNED_PENDING_EFFECTIVE",
        },
      },
    });
    expect(case08.process?.terminationAgreement.status).toBe("SIGNED_PENDING_EFFECTIVE");
    expect(case08.process?.terminationAgreement.effectiveAt).toContain("2026-08-01");
  });

  it("页面源码不直接声明后端 snake_case 字段", () => {
    const source = readFileSync(join(process.cwd(), "src/app/pages/NewAssessment.tsx"), "utf8");
    expect(source).not.toMatch(/\b(?:schema_version|case_id|assessment_time|source_system|generated_at|valid_until|outstanding_amount|contract_status|days_since_last_port)\b/u);
  });
});
