export type PageId =
  | "overview"
  | "new-assessment"
  | "case-history"
  | "ontology"
  | "competency"
  | "rules"
  | "whatif"
  | "system-status"
  | "result";

export type Decision = "ELIGIBLE" | "BLOCKED" | "MANUAL_REVIEW" | "CONDITIONAL" | "UNKNOWN";
export type StepStatus =
  | "PASSED"
  | "FAILED"
  | "DONE"
  | "SKIPPED"
  | "PENDING"
  | "PASS"
  | "FAIL"
  | "SKIP";
export type EvidenceStatus =
  | "VALID"
  | "EXPIRED"
  | "REVOKED"
  | "UNKNOWN"
  | "MISSING"
  | "CONFLICT";
export type PublicationStatus = "PUBLISHABLE" | "NOT_PUBLISHABLE";
export type RuleExecStatus = "PASS" | "FAIL" | "SKIP";
