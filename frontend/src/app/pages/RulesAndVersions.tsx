import { useEffect, useMemo, useState } from "react";
import { ArrowRight } from "lucide-react";
import { SectionHeader } from "../components/SectionHeader";
import { DecisionBadge, RuleLifecycleBadge } from "../components/StatusBadges";
import { cn } from "../utils/cn";
import {
  assessmentLabels,
  blockingReasonLabels,
  caseLabels,
  evidenceTypeLabels,
  remediationActionLabels,
  regulatoryClauseLabels,
  ruleLabels,
  translateOrUnknown,
  ui,
} from "../i18n/zh-CN";
import { listRules } from "../services/ruleService";
import type { EligibilityRule } from "../types/rules";

function formatDate(iso: string | null): string {
  if (!iso) return "—";
  return iso.slice(0, 10);
}

export function RulesAndVersions() {
  const [rules, setRules] = useState<EligibilityRule[]>([]);
  const [selected, setSelected] = useState<EligibilityRule | null>(null);

  useEffect(() => {
    void (async () => {
      const list = await listRules();
      setRules(list);
      const prefer =
        list.find((r) => r.ruleId === "MNP-ELIG-005" && r.version === "1.1") ??
        list[0] ??
        null;
      setSelected(prefer);
    })();
  }, []);

  const isMnp005 = selected?.ruleId === "MNP-ELIG-005";
  const versions005 = useMemo(
    () =>
      rules
        .filter((r) => r.ruleId === "MNP-ELIG-005")
        .sort((a, b) => a.version.localeCompare(b.version)),
    [rules],
  );

  return (
    <div className="flex h-full min-w-0 overflow-x-hidden">
      <div className="w-64 border-r border-slate-200 bg-white flex-shrink-0 overflow-y-auto">
        <div className="p-3 border-b border-slate-100">
          <div className="text-[10px] text-slate-400 font-semibold tracking-wider">规则列表</div>
        </div>
        {rules.map((r) => (
          <button
            key={`${r.ruleId}@${r.version}`}
            type="button"
            onClick={() => setSelected(r)}
            className={cn(
              "w-full text-left p-3 border-b border-slate-50 transition-colors",
              selected?.ruleId === r.ruleId && selected?.version === r.version
                ? "bg-violet-50 border-l-2 border-l-violet-500"
                : "hover:bg-slate-50",
            )}
          >
            <div className="flex items-center gap-2 mb-1 flex-wrap">
              <span className="text-[10px] text-violet-700">
                {translateOrUnknown(ruleLabels, r.ruleId, ui.unknownRule)}
              </span>
              <span className="text-[10px] text-slate-400">版本 {r.version}</span>
              {r.effectiveTo && (
                <span className="text-[9px] text-slate-300 italic">历史</span>
              )}
            </div>
            <div className="text-xs text-slate-700">{r.checkDescription}</div>
          </button>
        ))}
      </div>

      <div className="flex-1 overflow-y-auto p-6 space-y-4 min-w-0">
        {selected && (
          <>
            <div className="bg-white border border-slate-200 rounded-lg p-5">
              <div className="flex flex-col sm:flex-row sm:items-start justify-between gap-3 mb-4">
                <div className="min-w-0">
                  <div className="flex flex-wrap items-center gap-3 mb-1">
                    <span className="text-lg text-violet-700 font-bold">
                      {translateOrUnknown(
                        ruleLabels,
                        `${selected.ruleId}@${selected.version}`,
                        ui.unknownRule,
                      )}
                    </span>
                    <RuleLifecycleBadge historical={!!selected.effectiveTo} />
                  </div>
                  <div className="text-base font-semibold text-slate-700">
                    {translateOrUnknown(ruleLabels, selected.ruleId, ui.unknownRule)}
                  </div>
                </div>
                <div className="text-left sm:text-right text-xs space-y-1 flex-shrink-0">
                  <div>
                    <span className="text-slate-400">版本：</span>
                    <span className="text-slate-700">{selected.version}</span>
                  </div>
                  <div>
                    <span className="text-slate-400">生效：</span>
                    <span className="text-slate-700">{formatDate(selected.effectiveFrom)}</span>
                  </div>
                  <div>
                    <span className="text-slate-400">失效：</span>
                    <span className="text-slate-700">
                      {selected.effectiveTo ? formatDate(selected.effectiveTo) : "长期有效"}
                    </span>
                  </div>
                </div>
              </div>
              <div className="text-xs text-slate-600 leading-relaxed border-t border-slate-100 pt-3">
                {selected.checkDescription}
              </div>
            </div>

            <div className="grid grid-cols-1 sm:grid-cols-2 gap-3">
              {[
                {
                  label: "输入证据",
                  value: selected.inputEvidenceTypes
                    .map((e) =>
                      translateOrUnknown(evidenceTypeLabels, e, ui.unknownEvidence),
                    )
                    .join("、"),
                  color: "text-cyan-700",
                },
                {
                  label: "判断说明",
                  value: selected.checkDescription,
                  color: "text-violet-700",
                },
                {
                  label: "失败原因",
                  value: translateOrUnknown(
                    blockingReasonLabels,
                    selected.reasonCode,
                    ui.unknownStatus,
                  ),
                  color: "text-red-700",
                },
                {
                  label: "处理动作",
                  value: translateOrUnknown(
                    remediationActionLabels,
                    selected.actionCode,
                    ui.unknownAction,
                  ),
                  color: "text-emerald-700",
                },
                {
                  label: "监管条款",
                  value: translateOrUnknown(
                    regulatoryClauseLabels,
                    selected.regulatoryClause,
                    ui.unknownClause,
                  ),
                  color: "text-indigo-800",
                },
                {
                  label: "最少间隔天数",
                  value:
                    selected.checkMinimum != null
                      ? `${selected.checkMinimum} 天`
                      : "不适用",
                  color: "text-slate-700",
                },
              ].map((f) => (
                <div key={f.label} className="bg-white border border-slate-200 rounded-lg p-3">
                  <div className="text-[10px] text-slate-400 tracking-wide mb-1.5">{f.label}</div>
                  <div className={cn("text-xs", f.color)}>{f.value}</div>
                </div>
              ))}
            </div>

            {isMnp005 && (
              <div className="bg-white border border-slate-200 rounded-lg p-5">
                <SectionHeader title="规则版本时间线" sub="规则五：携转间隔检查" />
                <div className="space-y-3">
                  {versions005.map((v, idx) => {
                    const isHist = !!v.effectiveTo;
                    return (
                      <div key={v.version}>
                        <div
                          className={cn(
                            "border rounded-lg p-4",
                            isHist
                              ? "border-slate-200 bg-slate-50"
                              : "border-violet-200 bg-violet-50",
                          )}
                        >
                          <div className="flex flex-wrap items-center gap-3 mb-2">
                            <span
                              className={cn(
                                "text-sm font-bold",
                                isHist ? "text-slate-500" : "text-violet-700",
                              )}
                            >
                              版本 {v.version}
                            </span>
                            <span className="text-xs text-slate-400">
                              {isHist
                                ? `${formatDate(v.effectiveFrom)} 至 ${formatDate(v.effectiveTo)}`
                                : `${formatDate(v.effectiveFrom)} 起`}
                            </span>
                            <RuleLifecycleBadge historical={isHist} />
                          </div>
                          <div className="text-xs text-slate-600 mb-2">
                            最少间隔{" "}
                            <span className="text-violet-700 font-medium">
                              {v.checkMinimum ?? (isHist ? 120 : 180)} 天
                            </span>
                          </div>
                          <div className="text-xs text-slate-500 mb-2">
                            监管条款：
                            {translateOrUnknown(
                              regulatoryClauseLabels,
                              v.regulatoryClause,
                              ui.unknownClause,
                            )}
                          </div>
                          <div className="mt-2 flex flex-wrap items-center gap-2">
                            <span className="text-[10px] text-slate-400">
                              {translateOrUnknown(caseLabels, "CASE-06", ui.unknownCase)}{" "}
                              在此版本下的结果：
                            </span>
                            {isHist ? (
                              <span className="text-[10px] font-semibold text-emerald-700 bg-emerald-50 px-1.5 py-0.5 rounded">
                                可携转
                              </span>
                            ) : (
                              <span className="text-[10px] font-semibold text-red-700 bg-red-50 px-1.5 py-0.5 rounded">
                                不可携转
                              </span>
                            )}
                          </div>
                        </div>
                        {idx < versions005.length - 1 && (
                          <div className="flex items-center gap-2 px-4 my-3">
                            <div className="flex-1 h-px bg-slate-200" />
                            <div className="text-[10px] text-amber-700 bg-amber-50 border border-amber-200 px-2 py-0.5 rounded font-medium">
                              版本更新：间隔要求提高 60 天
                            </div>
                            <div className="flex-1 h-px bg-slate-200" />
                          </div>
                        )}
                      </div>
                    );
                  })}
                </div>

                <div className="mt-4 border-t border-slate-100 pt-4">
                  <div className="text-[10px] text-slate-400 tracking-wide font-semibold mb-2">
                    受影响的历史评估
                  </div>
                  <div className="space-y-1">
                    <div className="flex flex-wrap items-center gap-3 bg-white border border-slate-100 rounded px-3 py-2 text-xs">
                      <span className="text-slate-500">
                        {translateOrUnknown(
                          assessmentLabels,
                          "CASE-06-HIST",
                          ui.case06HistoricalAssessment,
                        )}
                      </span>
                      <span className="text-slate-600">
                        {translateOrUnknown(caseLabels, "CASE-06", ui.unknownCase)}
                      </span>
                      <div className="ml-auto flex items-center gap-2">
                        <DecisionBadge decision="ELIGIBLE" />
                        <ArrowRight size={10} className="text-slate-300" />
                        <DecisionBadge decision="BLOCKED" />
                      </div>
                    </div>
                    <div className="text-[10px] text-slate-400 px-1">
                      {ui.historicalVersion}（120 天）→ 可携转；{ui.currentVersion}（180 天）→
                      不可携转。仅展示真实案例六的历史与当前对比。
                    </div>
                  </div>
                </div>
              </div>
            )}
          </>
        )}
      </div>
    </div>
  );
}
