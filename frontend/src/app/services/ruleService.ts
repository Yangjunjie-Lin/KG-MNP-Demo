import { apiGet } from "../../api/client";
import { adaptAffectedAssessments, adaptRules } from "../../api/adapters/ruleAdapter";
import { array, record, text } from "../../api/adapters/guards";

export async function listRules(signal?: AbortSignal) {
  const catalog = record(await apiGet("/api/v1/rules", { signal }));
  const ruleIds = [
    ...new Set(
      array(catalog.items)
        .map((raw) => text(record(raw).rule_id))
        .filter(Boolean),
    ),
  ];
  const details = await Promise.all(
    ruleIds.map((ruleId) =>
      apiGet("/api/v1/rules/{rule_id}/versions", {
        pathParams: { rule_id: ruleId },
        signal,
      }),
    ),
  );
  return adaptRules({
    items: details.flatMap((detail) => array(record(detail).versions)),
  });
}

export async function getRule(ruleId: string, signal?: AbortSignal) {
  return apiGet("/api/v1/rules/{rule_id}", {
    pathParams: { rule_id: ruleId },
    signal,
  });
}

export async function getRuleVersions(ruleId: string, signal?: AbortSignal) {
  return apiGet("/api/v1/rules/{rule_id}/versions", {
    pathParams: { rule_id: ruleId },
    signal,
  });
}

export async function getAffectedAssessments(signal?: AbortSignal) {
  return adaptAffectedAssessments(
    await apiGet("/api/v1/rule-updates/affected-assessments", {
      query: {
        rule_id: "MNP-ELIG-005",
        old_version: "1.0",
        new_version: "1.1",
      },
      signal,
    }),
  );
}
