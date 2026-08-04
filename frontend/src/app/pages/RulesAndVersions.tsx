import { useMemo, useState } from "react";
import { RefreshCw } from "lucide-react";
import { ApiErrorState, EmptyState, PageSkeleton } from "../components/dataStates";
import { SectionHeader } from "../components/SectionHeader";
import { RuleLifecycleBadge } from "../components/StatusBadges";
import {
  blockingReasonLabels,
  caseLabels,
  evidenceTypeLabels,
  remediationActionLabels,
  regulatoryClauseLabels,
  ruleLabels,
  translateOrUnknown,
  ui,
} from "../i18n/zh-CN";
import { useAffectedAssessments, useRules } from "../query/hooks/useAppQueries";
import type { EligibilityRule } from "../types/rules";
import { cn } from "../utils/cn";

const UPDATED_RULE_ID = "MNP-ELIG-005";

function formatDate(iso: string | null): string {
  if (!iso) return "暂无信息";
  const date = new Date(iso);
  return Number.isNaN(date.getTime()) ? "暂无信息" : date.toLocaleDateString("zh-CN");
}

function ruleKey(rule: EligibilityRule): string {
  return `${rule.ruleId}@${rule.version}`;
}

function ruleName(rule: EligibilityRule): string {
  return translateOrUnknown(ruleLabels, rule.ruleId, ui.unknownRule);
}

export function RulesAndVersions() {
  const rulesQuery = useRules();
  const affectedQuery = useAffectedAssessments();
  const [selectedKey, setSelectedKey] = useState<string | null>(null);

  const rules = rulesQuery.data ?? [];
  const preferred =
    rules.find((rule) => rule.ruleId === UPDATED_RULE_ID && !rule.effectiveTo) ??
    rules[0] ??
    null;
  const selected =
    rules.find((rule) => ruleKey(rule) === selectedKey) ?? preferred;
  const selectedVersions = useMemo(
    () =>
      selected
        ? rules
            .filter((rule) => rule.ruleId === selected.ruleId)
            .sort((left, right) => left.version.localeCompare(right.version))
        : [],
    [rules, selected],
  );

  if (rulesQuery.isLoading) return <PageSkeleton />;
  if (rulesQuery.isError) {
    return <ApiErrorState error={rulesQuery.error} onRetry={() => void rulesQuery.refetch()} />;
  }
  if (!rules.length || !selected) return <EmptyState message="暂无规则版本数据" />;

  const affected = affectedQuery.data ?? [];
  const isUpdatedRule = selected.ruleId === UPDATED_RULE_ID;

  return (
    <div className="flex h-full min-w-0 overflow-x-hidden">
      <aside className="w-64 flex-shrink-0 overflow-y-auto border-r border-slate-200 bg-white">
        <div className="border-b border-slate-100 p-3">
          <div className="text-[10px] font-semibold tracking-wider text-slate-400">规则列表</div>
        </div>
        {rules.map((rule) => (
          <button
            key={ruleKey(rule)}
            type="button"
            onClick={() => setSelectedKey(ruleKey(rule))}
            className={cn(
              "w-full border-b border-slate-50 p-3 text-left transition-colors",
              ruleKey(selected) === ruleKey(rule)
                ? "border-l-2 border-l-violet-500 bg-violet-50"
                : "hover:bg-slate-50",
            )}
          >
            <div className="mb-1 flex flex-wrap items-center gap-2">
              <span className="text-[10px] text-violet-700">{ruleName(rule)}</span>
              <span className="text-[10px] text-slate-400">版本 {rule.version}</span>
              {rule.effectiveTo && <span className="text-[9px] text-slate-400">历史版本</span>}
            </div>
            <div className="text-xs text-slate-700">{rule.checkDescription}</div>
          </button>
        ))}
      </aside>

      <main className="min-w-0 flex-1 space-y-4 overflow-y-auto p-6">
        {(rulesQuery.isFetching || affectedQuery.isFetching) && (
          <div role="status" className="flex items-center justify-end gap-1.5 text-xs text-slate-400">
            <RefreshCw size={12} className="animate-spin" />正在刷新规则数据…
          </div>
        )}

        <section className="rounded-lg border border-slate-200 bg-white p-5">
          <div className="mb-4 flex flex-col justify-between gap-3 sm:flex-row sm:items-start">
            <div className="min-w-0">
              <div className="mb-1 flex flex-wrap items-center gap-3">
                <span className="text-lg font-bold text-violet-700">
                  {translateOrUnknown(
                    ruleLabels,
                    `${selected.ruleId}@${selected.version}`,
                    ruleName(selected),
                  )}
                </span>
                <RuleLifecycleBadge historical={!!selected.effectiveTo} />
              </div>
            </div>
            <dl className="flex-shrink-0 space-y-1 text-left text-xs sm:text-right">
              <div><dt className="inline text-slate-400">版本：</dt><dd className="inline text-slate-700">{selected.version}</dd></div>
              <div><dt className="inline text-slate-400">生效：</dt><dd className="inline text-slate-700">{formatDate(selected.effectiveFrom)}</dd></div>
              <div><dt className="inline text-slate-400">失效：</dt><dd className="inline text-slate-700">{selected.effectiveTo ? formatDate(selected.effectiveTo) : "长期有效"}</dd></div>
            </dl>
          </div>
          <div className="border-t border-slate-100 pt-3 text-xs leading-relaxed text-slate-600">
            {selected.checkDescription}
          </div>
        </section>

        <section className="grid grid-cols-1 gap-3 sm:grid-cols-2">
          {[
            {
              label: "输入证据",
              value: selected.inputEvidenceTypes.length
                ? selected.inputEvidenceTypes
                    .map((value) => translateOrUnknown(evidenceTypeLabels, value, ui.unknownEvidence))
                    .join("、")
                : "暂无信息",
              color: "text-cyan-700",
            },
            { label: "判断说明", value: selected.checkDescription, color: "text-violet-700" },
            {
              label: "失败原因",
              value: translateOrUnknown(blockingReasonLabels, selected.reasonCode, ui.unknownStatus),
              color: "text-red-700",
            },
            {
              label: "处理动作",
              value: translateOrUnknown(remediationActionLabels, selected.actionCode, ui.unknownAction),
              color: "text-emerald-700",
            },
            {
              label: "监管条款",
              value: translateOrUnknown(regulatoryClauseLabels, selected.regulatoryClause, ui.unknownClause),
              color: "text-indigo-800",
            },
            {
              label: "最少间隔天数",
              value: selected.checkMinimum == null ? "不适用" : `${selected.checkMinimum} 天`,
              color: "text-slate-700",
            },
          ].map((field) => (
            <div key={field.label} className="rounded-lg border border-slate-200 bg-white p-3">
              <div className="mb-1.5 text-[10px] tracking-wide text-slate-400">{field.label}</div>
              <div className={cn("text-xs", field.color)}>{field.value}</div>
            </div>
          ))}
        </section>

        <section className="rounded-lg border border-slate-200 bg-white p-5">
          <SectionHeader title="规则版本时间线" sub={ruleName(selected)} />
          <div className="space-y-3">
            {selectedVersions.map((version) => {
              const historical = !!version.effectiveTo;
              return (
                <div
                  key={ruleKey(version)}
                  className={cn(
                    "rounded-lg border p-4",
                    historical
                      ? "border-slate-200 bg-slate-50"
                      : "border-violet-200 bg-violet-50",
                  )}
                >
                  <div className="mb-2 flex flex-wrap items-center gap-3">
                    <span className={cn("text-sm font-bold", historical ? "text-slate-600" : "text-violet-700")}>
                      版本 {version.version}
                    </span>
                    <span className="text-xs text-slate-400">
                      {historical
                        ? `${formatDate(version.effectiveFrom)} 至 ${formatDate(version.effectiveTo)}`
                        : `${formatDate(version.effectiveFrom)} 起`}
                    </span>
                    <RuleLifecycleBadge historical={historical} />
                  </div>
                  <div className="text-xs text-slate-600">
                    最少间隔：{version.checkMinimum == null ? "不适用" : `${version.checkMinimum} 天`}
                  </div>
                </div>
              );
            })}
          </div>

          {isUpdatedRule && (
            <div className="mt-5 border-t border-slate-100 pt-4">
              <div className="mb-2 text-[10px] font-semibold tracking-wide text-slate-400">
                受影响的历史评估
              </div>
              {affectedQuery.isLoading ? (
                <div role="status" className="rounded border border-slate-200 p-5 text-center text-xs text-slate-500">
                  正在加载受影响评估…
                </div>
              ) : affectedQuery.isError ? (
                <ApiErrorState
                  error={affectedQuery.error}
                  onRetry={() => void affectedQuery.refetch()}
                />
              ) : affected.length === 0 ? (
                <div className="rounded border border-dashed border-slate-300 p-5 text-center text-xs text-slate-500">
                  暂无受影响的历史评估，请先运行示例数据初始化。
                </div>
              ) : (
                <div className="space-y-2">
                  {affected.map((item) => (
                    <div
                      key={item.executionId}
                      className="flex flex-wrap items-center gap-x-4 gap-y-1 rounded border border-slate-100 px-3 py-2 text-xs"
                    >
                      <span className="font-medium text-slate-700">
                        {translateOrUnknown(caseLabels, item.caseId, ui.unknownCase)}
                      </span>
                      <span className="text-slate-500">评估时间：{formatDate(item.assessmentTime)}</span>
                      <span className="text-slate-500">
                        规则版本：{item.oldVersion || "暂无信息"} → {item.newVersion || "暂无信息"}
                      </span>
                      <span className="ml-auto text-amber-700">
                        {item.requiresReassessment ? "需要重新评估" : "无需重新评估"}
                      </span>
                    </div>
                  ))}
                </div>
              )}
            </div>
          )}
        </section>
      </main>
    </div>
  );
}
