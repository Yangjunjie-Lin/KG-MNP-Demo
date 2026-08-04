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

  it("页面源码不直接声明后端 snake_case 字段", () => {
    const source = readFileSync(join(process.cwd(), "src/app/pages/NewAssessment.tsx"), "utf8");
    expect(source).not.toMatch(/\b(?:schema_version|case_id|assessment_time|source_system|generated_at|valid_until|outstanding_amount|contract_status|days_since_last_port)\b/u);
  });
});
