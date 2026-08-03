import { useEffect, useState } from "react";
import { Play } from "lucide-react";
import { DecisionBadge, StatusBadge } from "../components/StatusBadges";
import { cn } from "../utils/cn";
import {
  blockingReasonLabels,
  caseLabels,
  decisionLabels,
  processStepLabels,
  remediationActionLabels,
  ruleLabels,
  t,
  ui,
} from "../i18n/zh-CN";
import { getCompetencyQuestions, getAssessmentDetail } from "../services/assessmentService";
import { listCases } from "../services/caseService";
import type { CompetencyQuestion } from "../data/mockCompetencyQuestions";
import type { AssessmentDetail, CaseSummary } from "../types/assessment";

function cqOrdinal(id: string): string {
  const n = Number(id.replace("CQ-", ""));
  const map = ["", "一", "二", "三", "四", "五", "六", "七", "八", "九", "十", "十一", "十二", "十三", "十四", "十五"];
  return map[n] ? `问题${map[n]}` : id;
}

function ResultPanel({
  cq,
  caseId,
  detail,
}: {
  cq: CompetencyQuestion;
  caseId: string;
  detail: AssessmentDetail | null;
}) {
  const caseLabel = t(caseLabels, caseId, caseId);
  if (!detail) {
    return <div className="text-xs text-slate-400 py-4 text-center">{ui.empty}</div>;
  }

  if (cq.id === "CQ-01") {
    return (
      <div className="text-xs space-y-2">
        <div className="bg-white border border-slate-200 rounded-lg p-3">
          <div className="text-slate-400 text-[10px] mb-2">查询结果</div>
          <div className="grid grid-cols-2 gap-2">
            <div>
              <span className="text-slate-400">案例</span>
              <br />
              <span className="text-blue-700">{caseLabel}</span>
            </div>
            <div>
              <span className="text-slate-400">资格结论</span>
              <br />
              <DecisionBadge decision={detail.decision} />
            </div>
            <div>
              <span className="text-slate-400">评估时间</span>
              <br />
              <span className="text-slate-600">
                {detail.assessmentTime.replace("T", " ").replace("Z", "").slice(0, 16)}
              </span>
            </div>
            <div>
              <span className="text-slate-400">执行编号</span>
              <br />
              <span className="text-slate-600">执行-{caseLabel}</span>
            </div>
          </div>
        </div>
        <div className="text-slate-600 bg-slate-50 rounded p-2">
          {caseLabel} 当前结论为「{t(decisionLabels, detail.decision)}」。
        </div>
      </div>
    );
  }

  if (cq.id === "CQ-02" || cq.id === "CQ-14") {
    return (
      <div className="text-xs space-y-2">
        {detail.blockingReasonDetails.length === 0 ? (
          <div className="text-emerald-600 bg-emerald-50 rounded p-3">无阻塞原因</div>
        ) : (
          detail.blockingReasonDetails.map((br) => (
            <div key={br.reasonCode} className="bg-white border border-slate-200 rounded-lg p-3">
              <div className="font-medium text-red-700 mb-1">
                {t(blockingReasonLabels, br.reasonCode)}
              </div>
              <div className="text-slate-600">{br.description}</div>
              {cq.id === "CQ-14" && (
                <div className="mt-1 text-emerald-700">
                  处理动作：{t(remediationActionLabels, br.actionCode)}
                </div>
              )}
            </div>
          ))
        )}
      </div>
    );
  }

  if (cq.id === "CQ-05") {
    return (
      <div className="overflow-x-auto">
        <table className="w-full bg-white border border-slate-200 rounded-lg overflow-hidden text-xs min-w-[480px]">
          <thead className="bg-slate-50">
            <tr>
              {["规则名称", "版本", "执行结果", "触发原因"].map((h) => (
                <th key={h} className="px-3 py-2 text-left text-[10px] font-semibold text-slate-500">
                  {h}
                </th>
              ))}
            </tr>
          </thead>
          <tbody>
            {detail.ruleResults.map((r) => (
              <tr key={`${r.ruleId}-${r.version}`} className="border-t border-slate-100">
                <td className="px-3 py-2 text-violet-700">{t(ruleLabels, r.ruleId)}</td>
                <td className="px-3 py-2 text-slate-500">{r.version}</td>
                <td className="px-3 py-2">
                  <StatusBadge status={r.status} />
                </td>
                <td className="px-3 py-2 text-slate-400">
                  {r.reasonCode ? t(blockingReasonLabels, r.reasonCode) : "—"}
                </td>
              </tr>
            ))}
          </tbody>
        </table>
      </div>
    );
  }

  if (cq.id === "CQ-08" || cq.id === "CQ-09" || cq.id === "CQ-10") {
    const process = detail.process;
    return (
      <div className="text-xs space-y-2 bg-white border border-slate-200 rounded-lg p-3">
        <div>
          当前步骤：
          {t(processStepLabels, process?.currentStep ?? "", String(process?.currentStep ?? "—"))}
        </div>
        <div>
          能否继续：
          {process?.canAdvance ? ui.canAdvance : ui.cannotAdvance}
        </div>
        {process?.processBlockingReasons?.map((p) => (
          <div key={p.code} className="text-red-600">
            {t(blockingReasonLabels, p.code, p.message)}
          </div>
        ))}
        {process?.authorizationCode && (
          <div>
            授权码状态：
            <StatusBadge status={process.authorizationCode.status} />
          </div>
        )}
      </div>
    );
  }

  if (cq.id === "CQ-15") {
    return (
      <div className="text-xs bg-white border border-slate-200 rounded-lg p-3 space-y-2">
        <div>
          受影响案例：{t(caseLabels, "CASE-06")}
        </div>
        <div className="flex items-center gap-2">
          <DecisionBadge decision="ELIGIBLE" />
          <span className="text-slate-400">→</span>
          <DecisionBadge decision="BLOCKED" />
        </div>
        <div className="text-slate-600">
          规则五由版本 1.0（120 天）更新为版本 1.1（180 天）后，历史评估需重新评估。
        </div>
      </div>
    );
  }

  return (
    <div className="bg-white border border-slate-200 rounded-lg p-3 text-xs">
      <div className="text-center py-2 text-slate-600">
        已对 {caseLabel} 执行「{cqOrdinal(cq.id)}：{cq.titleZh}」
        <br />
        <span className="text-emerald-600">查询成功</span>
      </div>
    </div>
  );
}

export function CompetencyQuestions() {
  const [questions, setQuestions] = useState<CompetencyQuestion[]>([]);
  const [cases, setCases] = useState<CaseSummary[]>([]);
  const [selectedCQ, setSelectedCQ] = useState<CompetencyQuestion | null>(null);
  const [selectedCase, setSelectedCase] = useState("CASE-03");
  const [detail, setDetail] = useState<AssessmentDetail | null>(null);
  const [executed, setExecuted] = useState(false);

  useEffect(() => {
    void (async () => {
      const [cqs, caseList] = await Promise.all([
        getCompetencyQuestions(),
        listCases(),
      ]);
      setQuestions(cqs);
      setCases(caseList);
      setSelectedCQ(cqs[0] ?? null);
      if (cqs[0]?.exampleCase) setSelectedCase(cqs[0].exampleCase);
    })();
  }, []);

  useEffect(() => {
    void getAssessmentDetail(selectedCase).then(setDetail);
  }, [selectedCase]);

  return (
    <div className="flex h-full min-w-0 overflow-x-hidden">
      <div className="w-64 border-r border-slate-200 bg-white flex-shrink-0 overflow-y-auto">
        <div className="p-3 border-b border-slate-100">
          <div className="text-[10px] text-slate-400 font-semibold tracking-wider">
            能力问题（问题一至问题十五）
          </div>
        </div>
        {questions.map((cq) => (
          <button
            key={cq.id}
            type="button"
            onClick={() => {
              setSelectedCQ(cq);
              setExecuted(false);
              if (cq.exampleCase) setSelectedCase(cq.exampleCase);
            }}
            className={cn(
              "w-full text-left p-3 border-b border-slate-50 transition-colors",
              selectedCQ?.id === cq.id
                ? "bg-blue-50 border-l-2 border-l-blue-500"
                : "hover:bg-slate-50",
            )}
          >
            <div className="flex items-center gap-2 mb-1">
              <span className="text-[10px] text-blue-600 bg-blue-50 px-1.5 py-0.5 rounded">
                {cqOrdinal(cq.id)}
              </span>
              <span className="text-[9px] text-slate-400">{cq.exampleCaseLabel}</span>
            </div>
            <div className="text-xs text-slate-700 leading-relaxed">{cq.titleZh}</div>
          </button>
        ))}
      </div>

      <div className="flex-1 overflow-y-auto p-6 space-y-4 min-w-0">
        {selectedCQ && (
          <>
            <div className="bg-white border border-slate-200 rounded-lg p-4">
              <div className="flex items-center gap-2 mb-1 flex-wrap">
                <span className="text-sm text-blue-700">{cqOrdinal(selectedCQ.id)}</span>
                <span className="text-slate-300">—</span>
                <span className="text-sm font-medium text-slate-700">{selectedCQ.questionZh}</span>
              </div>
              <div className="text-xs text-slate-500 mb-3">用途：{selectedCQ.usage}</div>
              <div className="grid grid-cols-1 sm:grid-cols-3 gap-3 text-xs">
                <div>
                  <div className="text-[10px] text-slate-400 mb-1">需要输入</div>
                  {selectedCQ.requiredInputs.length > 0 ? (
                    selectedCQ.requiredInputs.map((i) => (
                      <span key={i} className="text-slate-600 block">
                        {i === "case_id" ? "案例编号" : i}
                      </span>
                    ))
                  ) : (
                    <span className="text-slate-400">无需输入</span>
                  )}
                </div>
                <div>
                  <div className="text-[10px] text-slate-400 mb-1">预期返回</div>
                  <div className="text-slate-600">{selectedCQ.expected}</div>
                </div>
                <div>
                  <div className="text-[10px] text-slate-400 mb-1">示例案例</div>
                  <span className="text-blue-600">{selectedCQ.exampleCaseLabel}</span>
                </div>
              </div>
            </div>

            <div className="bg-white border border-slate-200 rounded-lg p-4">
              <div className="flex flex-wrap items-center gap-3 mb-4">
                <select
                  value={selectedCase}
                  onChange={(e) => {
                    setSelectedCase(e.target.value);
                    setExecuted(false);
                  }}
                  className="text-xs border border-slate-200 rounded px-2 py-1.5 bg-white text-slate-700 outline-none"
                >
                  {cases.map((c) => (
                    <option key={c.id} value={c.id}>
                      {t(caseLabels, c.id)} — {c.title}
                    </option>
                  ))}
                </select>
                <button
                  type="button"
                  onClick={() => setExecuted(true)}
                  className="flex items-center gap-1.5 bg-blue-600 hover:bg-blue-700 text-white text-xs px-3 py-1.5 rounded-md font-medium transition-colors"
                >
                  <Play size={11} /> 执行查询
                </button>
              </div>
              {executed ? (
                <div>
                  <div className="text-[10px] text-slate-400 tracking-wide mb-2">查询结果</div>
                  <ResultPanel cq={selectedCQ} caseId={selectedCase} detail={detail} />
                </div>
              ) : (
                <div className="text-center text-slate-300 text-xs py-6">
                  <Play size={20} className="mx-auto mb-1.5 opacity-40" />
                  选择案例后点击执行
                </div>
              )}
            </div>
          </>
        )}
      </div>
    </div>
  );
}
