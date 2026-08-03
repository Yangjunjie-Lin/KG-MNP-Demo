// 后续在这里连接本地 FastAPI
import type { EligibilityRule } from "../types/rules";
import { getRuleByIdVersion, mockRules } from "../data/mockRules";

export async function listRules(): Promise<EligibilityRule[]> {
  return Promise.resolve(mockRules);
}

export async function getRule(
  ruleId: string,
  version?: string,
): Promise<EligibilityRule | null> {
  return Promise.resolve(getRuleByIdVersion(ruleId, version) ?? null);
}
