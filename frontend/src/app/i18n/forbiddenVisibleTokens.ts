/** 正式界面渲染文本中禁止出现的技术标识（用于界面测试，不对源代码全文扫描） */
export const forbiddenVisibleTokens = [
  "CASE-",
  "CQ-",
  "MNP-ELIG-",
  "REG-MNP-CLAUSE-",
  "EXEC-",
  "ASSESS-",
  "ELIGIBLE",
  "BLOCKED",
  "MANUAL_REVIEW",
  "CONDITIONAL",
  "PASSED",
  "FAILED",
  "SKIPPED",
  "PENDING",
  "PUBLISHABLE",
  "NOT_PUBLISHABLE",
  '"PASS"',
  " PASS",
  "PASS ",
  "FAIL",
  "VALID",
  "EXPIRED",
  "ONLINE",
  "DEGRADED",
  "JSON Schema",
  "RDF Builder",
  "Input SHACL",
  "OWL-RL",
  "SPARQL Trace",
  "SPARQL",
  "FastAPI",
  "schema_version",
  "case_id",
  "assessment_time",
  "source_system",
  "subscriber_id",
] as const;

/** 更精确的禁止模式：匹配独立英文状态码 / 技术前缀 */
export const forbiddenVisiblePatterns: RegExp[] = [
  /\bCASE-\d+/i,
  /\bCQ-\d+/i,
  /\bMNP-ELIG-\d+/i,
  /\bREG-MNP-CLAUSE-\d+/i,
  /\bEXEC-[A-Z0-9-]+/i,
  /\bASSESS-[A-Z0-9-]+/i,
  /\bELIGIBLE\b/,
  /\bBLOCKED\b/,
  /\bMANUAL_REVIEW\b/,
  /\bCONDITIONAL\b/,
  /\bPASSED\b/,
  /\bFAILED\b/,
  /\bSKIPPED\b/,
  /\bPUBLISHABLE\b/,
  /\bNOT_PUBLISHABLE\b/,
  /\bONLINE\b/,
  /\bDEGRADED\b/,
  /\bJSON Schema\b/,
  /\bRDF Builder\b/,
  /\bInput SHACL\b/,
  /\bOWL-RL\b/,
  /\bSPARQL Trace\b/,
  /\bSPARQL\b/,
  /\bFastAPI\b/,
  /\bschema_version\b/,
  /\bcase_id\b/,
  /\bassessment_time\b/,
  /\bsource_system\b/,
  /\bsubscriber_id\b/,
  /\bMNPCase\b/,
  /\bEligibilityAssessment\b/,
  /\bEvidenceRecord\b/,
  /\bBlockingReason\b/,
  /\bEligibilityRule\b/,
  /\bRuleVersion\b/,
  /\bRegulatoryClause\b/,
  /\bRemediationAction\b/,
];

export function findForbiddenVisibleText(text: string): string[] {
  const found = new Set<string>();
  for (const pattern of forbiddenVisiblePatterns) {
    const match = text.match(pattern);
    if (match) found.add(match[0]);
  }
  // 独立状态短词：避免误伤中文语境中的数字版本
  for (const token of ["PASS", "FAIL", "VALID", "EXPIRED"] as const) {
    const re = new RegExp(`(^|[^A-Za-z_])${token}([^A-Za-z_]|$)`);
    if (re.test(text)) found.add(token);
  }
  return Array.from(found);
}
