const fieldLabels: Record<string, string> = {
  "payload.schema_version": "数据规范版本",
  "payload.case_id": "案例编号",
  "payload.assessment_time": "评估时间",
  "payload.subscriber.subscriber_id": "订户编号",
  "payload.phone_number.masked_number": "脱敏手机号码",
  "payload.account.account_id": "账户编号",
  "payload.evidence.identity.matched": "实名信息是否一致",
  "payload.evidence.identity.source_system": "实名证据来源",
  "payload.evidence.identity.generated_at": "实名证据生成时间",
  "payload.evidence.identity.valid_until": "实名证据有效期",
  "payload.evidence.identity.status": "实名证据状态",
  "payload.evidence.number_status.status_code": "号码状态",
  "payload.evidence.number_status.source_system": "号码状态来源",
  "payload.evidence.number_status.generated_at": "号码证据生成时间",
  "payload.evidence.number_status.valid_until": "号码证据有效期",
  "payload.evidence.number_status.status": "号码证据状态",
  "payload.evidence.billing.outstanding_amount": "未结费用",
  "payload.evidence.billing.currency": "货币",
  "payload.evidence.billing.has_payment_arrangement": "是否有付款安排",
  "payload.evidence.billing.source_system": "计费证据来源",
  "payload.evidence.billing.generated_at": "计费证据生成时间",
  "payload.evidence.billing.valid_until": "计费证据有效期",
  "payload.evidence.billing.status": "计费证据状态",
  "payload.evidence.contract.contract_status": "合约状态",
  "payload.evidence.contract.contract_end_time": "合约结束时间",
  "payload.evidence.contract.source_system": "合约证据来源",
  "payload.evidence.contract.generated_at": "合约证据生成时间",
  "payload.evidence.contract.valid_until": "合约证据有效期",
  "payload.evidence.contract.status": "合约证据状态",
  "payload.evidence.porting_history.days_since_last_port": "距上次携转天数",
  "payload.evidence.porting_history.source_system": "携转历史来源",
  "payload.evidence.porting_history.generated_at": "携转历史生成时间",
  "payload.evidence.porting_history.valid_until": "携转历史有效期",
  "payload.evidence.porting_history.status": "携转历史证据状态",
  "payload.process.current_step": "当前流程步骤",
  "payload.process.authorization_code.status": "授权码状态",
  "payload.process.authorization_code.issued_at": "授权码签发时间",
  "payload.process.authorization_code.valid_until": "授权码有效期",
  "payload.process.authorization_code.masked_value": "脱敏授权码",
  "payload.process.termination_agreement.signed_at": "解除协议签署时间",
  "payload.process.termination_agreement.effective_at": "解除协议生效时间",
  "payload.process.termination_agreement.status": "解除协议状态",
};

function normalizeFieldPath(path: string): string {
  return path
    .replace(/^body\./, "")
    .replace(/^request\./, "")
    .replace(/^evidence\./, "payload.evidence.");
}

export function fieldLabel(path: string): string {
  return fieldLabels[normalizeFieldPath(path)] ?? "未识别字段";
}

export function translateValidationDetail(detail: unknown): string {
  if (typeof detail === "string") {
    const [rawPath] = detail.split(":", 1);
    return fieldLabel(rawPath.trim());
  }
  if (detail && typeof detail === "object") {
    const value = detail as Record<string, unknown>;
    const loc = Array.isArray(value.loc) ? value.loc.join(".") : String(value.path ?? "");
    return fieldLabel(loc);
  }
  return "未识别字段";
}
