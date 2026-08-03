import { useEffect, useState } from "react";
import { ArrowRight, FlaskConical, Play } from "lucide-react";
import { DecisionBadge, StatusBadge } from "../components/StatusBadges";
import { cn } from "../utils/cn";
import {
  caseLabels,
  contractStatusLabels,
  ruleLabels,
  translateOrUnknown,
  ui,
} from "../i18n/zh-CN";
import { getAssessmentDetail } from "../services/assessmentService";
import { listRules } from "../services/ruleService";
import type { Decision } from "../types/common";
import type { EligibilityRule } from "../types/rules";

export function WhatIfExperiment() {
  const [contractStatus, setContractStatus] = useState<"ACTIVE" | "EXPIRED">("ACTIVE");
  const [balance, setBalance] = useState("0.00");
  const [daysSincePort, setDaysSincePort] = useState("400");
  const [ran, setRan] = useState(false);
  const [baselineDecision, setBaselineDecision] = useState<Decision>("BLOCKED");
  const [rules, setRules] = useState<EligibilityRule[]>([]);

  useEffect(() => {
    void (async () => {
      const [detail, ruleList] = await Promise.all([
        getAssessmentDetail("CASE-03"),
        listRules(),
      ]);
      if (detail) setBaselineDecision(detail.decision);
      setRules(ruleList.filter((r) => !(r.ruleId === "MNP-ELIG-005" && r.version === "1.0")));
    })();
  }, []);

  const scenarioDecision: Decision =
    contractStatus === "EXPIRED" && parseFloat(balance || "0") === 0
      ? "ELIGIBLE"
      : "BLOCKED";
  const changed = scenarioDecision !== baselineDecision;

  return (
    <div className="flex flex-col h-full overflow-y-auto overflow-x-hidden p-6 space-y-5 min-w-0">
      <div className="flex items-center gap-3">
        <FlaskConical size={18} className="text-blue-600" />
        <div>
          <h2 className="text-base font-semibold text-slate-700">{ui.navWhatIf}</h2>
          <div className="text-xs text-slate-500">
            基于{translateOrUnknown(caseLabels, "CASE-03", ui.unknownCase)}，修改条件字段，对比结果变化
          </div>
        </div>
      </div>

      <div className="grid grid-cols-1 md:grid-cols-2 gap-4">
        <div className="bg-white border border-slate-200 rounded-lg p-4">
          <div className="flex items-center gap-2 mb-3">
            <span className="w-2 h-2 rounded-full bg-slate-400" />
            <span className="text-xs font-semibold text-slate-500">
              {ui.baseline} — {translateOrUnknown(caseLabels, "CASE-03", ui.unknownCase)}
            </span>
          </div>
          <DecisionBadge decision={baselineDecision} />
          <div className="mt-3 space-y-1.5 text-xs">
            <div className="flex justify-between gap-2">
              <span className="text-slate-400">合约状态</span>
              <span className="text-slate-700">{contractStatusLabels.ACTIVE}</span>
            </div>
            <div className="flex justify-between gap-2">
              <span className="text-slate-400">未结费用</span>
              <span className="text-slate-700">¥0.00</span>
            </div>
            <div className="flex justify-between gap-2">
              <span className="text-slate-400">距上次携转天数</span>
              <span className="text-slate-700">400</span>
            </div>
            <div className="flex justify-between gap-2">
              <span className="text-slate-400">合约到期时间</span>
              <span className="text-slate-700">2027-06-01</span>
            </div>
          </div>
        </div>

        <div
          className={cn(
            "border rounded-lg p-4",
            changed ? "border-emerald-300 bg-emerald-50" : "bg-white border-slate-200",
          )}
        >
          <div className="flex items-center gap-2 mb-3">
            <span
              className={cn(
                "w-2 h-2 rounded-full",
                changed ? "bg-emerald-500" : "bg-amber-400",
              )}
            />
            <span className="text-xs font-semibold text-slate-500">{ui.scenario}</span>
          </div>
          <DecisionBadge decision={scenarioDecision} />
          <div className="mt-3 space-y-1.5 text-xs">
            <div className="flex justify-between items-center gap-2">
              <span className="text-slate-400">合约状态</span>
              <select
                value={contractStatus}
                onChange={(e) => {
                  setContractStatus(e.target.value as "ACTIVE" | "EXPIRED");
                  setRan(false);
                }}
                className="text-xs border border-slate-300 rounded px-1.5 py-0.5 bg-white text-slate-700 outline-none"
              >
                <option value="ACTIVE">{contractStatusLabels.ACTIVE}</option>
                <option value="EXPIRED">{contractStatusLabels.EXPIRED}</option>
              </select>
            </div>
            <div className="flex justify-between items-center gap-2">
              <span className="text-slate-400">未结费用</span>
              <div className="flex items-center gap-1">
                <span className="text-slate-400">¥</span>
                <input
                  type="number"
                  value={balance}
                  min={0}
                  step={0.01}
                  onChange={(e) => {
                    setBalance(e.target.value);
                    setRan(false);
                  }}
                  className="text-xs border border-slate-300 rounded px-1.5 py-0.5 w-20 bg-white text-slate-700 outline-none"
                />
              </div>
            </div>
            <div className="flex justify-between items-center gap-2">
              <span className="text-slate-400">距上次携转天数</span>
              <input
                type="number"
                value={daysSincePort}
                min={0}
                onChange={(e) => {
                  setDaysSincePort(e.target.value);
                  setRan(false);
                }}
                className="text-xs border border-slate-300 rounded px-1.5 py-0.5 w-20 bg-white text-slate-700 outline-none"
              />
            </div>
          </div>
        </div>
      </div>

      <div className="bg-white border border-slate-200 rounded-lg p-4">
        <div className="text-[10px] text-slate-400 tracking-wide font-semibold mb-3">
          修改字段
        </div>
        <div className="flex flex-wrap items-center gap-4 text-xs">
          <div className="flex items-center gap-2">
            <span className="bg-red-50 text-red-600 px-2 py-1 rounded">
              合约状态：{contractStatusLabels.ACTIVE}
            </span>
            <ArrowRight size={12} className="text-slate-300" />
            <span className="bg-emerald-50 text-emerald-600 px-2 py-1 rounded">
              合约状态：{contractStatusLabels[contractStatus]}
            </span>
          </div>
          {parseFloat(balance || "0") !== 0 && (
            <div className="flex items-center gap-2">
              <span className="bg-red-50 text-red-600 px-2 py-1 rounded">未结费用：¥0.00</span>
              <ArrowRight size={12} className="text-slate-300" />
              <span className="bg-amber-50 text-amber-600 px-2 py-1 rounded">
                未结费用：¥{balance}
              </span>
            </div>
          )}
        </div>
      </div>

      <button
        type="button"
        onClick={() => setRan(true)}
        className="flex items-center gap-2 bg-blue-600 hover:bg-blue-700 text-white text-sm px-4 py-2 rounded-md font-medium transition-colors self-start"
      >
        <Play size={14} /> 运行对比评估
      </button>

      {ran && (
        <div className="space-y-4">
          <div
            className={cn(
              "border rounded-lg p-4",
              changed ? "bg-emerald-50 border-emerald-200" : "bg-slate-50 border-slate-200",
            )}
          >
            <div className="flex flex-wrap items-center gap-4">
              <div className="text-xs text-slate-500 font-semibold">结论变化</div>
              <div className="flex items-center gap-3">
                <DecisionBadge decision={baselineDecision} />
                <ArrowRight size={14} className="text-slate-400" />
                <DecisionBadge decision={scenarioDecision} />
              </div>
              {changed ? (
                <span className="text-xs text-emerald-700 font-medium">结论已改变</span>
              ) : (
                <span className="text-xs text-slate-500">结论未变化</span>
              )}
            </div>
          </div>

          <div className="bg-white border border-slate-200 rounded-lg p-4 overflow-x-auto">
            <div className="text-[10px] text-slate-400 tracking-wide font-semibold mb-3">
              规则变化
            </div>
            <table className="w-full text-xs min-w-[480px]">
              <thead>
                <tr className="border-b border-slate-100">
                  {["规则名称", "基准方案", "推演方案", "变化"].map((h) => (
                    <th
                      key={h}
                      className="pb-2 text-left text-[10px] font-semibold text-slate-400"
                    >
                      {h}
                    </th>
                  ))}
                </tr>
              </thead>
              <tbody>
                {rules.map((r) => {
                  const isContract = r.ruleId === "MNP-ELIG-004";
                  const isBilling = r.ruleId === "MNP-ELIG-003";
                  const baselineStatus =
                    isContract && baselineDecision === "BLOCKED" ? "FAIL" : "PASS";
                  let scenarioStatus = "PASS";
                  if (isContract) {
                    scenarioStatus = contractStatus === "EXPIRED" ? "PASS" : "FAIL";
                  }
                  if (isBilling && parseFloat(balance || "0") > 0) {
                    scenarioStatus = "FAIL";
                  }
                  const ruleChanged = baselineStatus !== scenarioStatus;
                  return (
                    <tr key={`${r.ruleId}-${r.version}`} className="border-b border-slate-50">
                      <td className="py-2 text-violet-700">
                        {translateOrUnknown(ruleLabels, r.ruleId, ui.unknownRule)}
                      </td>
                      <td className="py-2">
                        <StatusBadge status={baselineStatus} />
                      </td>
                      <td className="py-2">
                        <StatusBadge status={scenarioStatus} />
                      </td>
                      <td className="py-2 text-xs">
                        {ruleChanged ? (
                          <span className="text-emerald-600">
                            {baselineStatus === "FAIL" ? "未通过 → 通过" : "通过 → 未通过"}
                          </span>
                        ) : (
                          <span className="text-slate-400">无变化</span>
                        )}
                      </td>
                    </tr>
                  );
                })}
              </tbody>
            </table>
          </div>

          <div className="bg-white border border-slate-200 rounded-lg p-4">
            <div className="text-[10px] text-slate-400 tracking-wide font-semibold mb-3">
              证据变化
            </div>
            <div className="grid grid-cols-1 sm:grid-cols-3 gap-3 text-xs">
              <div>
                <div className="text-emerald-600 font-semibold mb-1.5">新增</div>
                {contractStatus === "EXPIRED" ? (
                  <div className="text-cyan-700 bg-cyan-50 rounded p-1.5 border border-cyan-100">
                    合约到期证明
                  </div>
                ) : (
                  <div className="text-slate-400 italic">无</div>
                )}
              </div>
              <div>
                <div className="text-red-500 font-semibold mb-1.5">移除</div>
                <div className="text-slate-400 italic">无</div>
              </div>
              <div>
                <div className="text-amber-600 font-semibold mb-1.5">修改</div>
                {contractStatus === "EXPIRED" ? (
                  <div className="text-slate-600 bg-amber-50 rounded p-1.5 border border-amber-100">
                    合约状态证据：有效 → 已到期
                  </div>
                ) : (
                  <div className="text-slate-400 italic">无</div>
                )}
              </div>
            </div>
          </div>
        </div>
      )}
    </div>
  );
}
