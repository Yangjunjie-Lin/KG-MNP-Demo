import { useEffect, useMemo, useState } from "react";
import { Eye, Search } from "lucide-react";
import { DecisionBadge } from "../components/StatusBadges";
import { cn } from "../utils/cn";
import {
  blockingReasonLabels,
  caseLabels,
  decisionLabels,
  publicationStatusLabels,
  t,
  ui,
} from "../i18n/zh-CN";
import { listCases } from "../services/caseService";
import type { CaseSummary } from "../types/assessment";
import type { Decision } from "../types/common";

function formatTime(iso: string): string {
  return iso.replace("T", " ").replace("Z", "").slice(0, 16);
}

export function CaseHistory({
  onCaseClick,
}: {
  onCaseClick: (caseId: string) => void;
}) {
  const [cases, setCases] = useState<CaseSummary[]>([]);
  const [search, setSearch] = useState("");
  const [filterDecision, setFilterDecision] = useState<string>("ALL");
  const [filterPublish, setFilterPublish] = useState<string>("ALL");

  useEffect(() => {
    void listCases().then(setCases);
  }, []);

  const filtered = useMemo(
    () =>
      cases.filter((c) => {
        const label = t(caseLabels, c.id, c.id);
        const matchSearch =
          !search ||
          label.includes(search) ||
          c.title.includes(search) ||
          c.scenario.includes(search);
        const matchDecision =
          filterDecision === "ALL" || c.decision === filterDecision;
        const matchPublish =
          filterPublish === "ALL" || c.publicationStatus === filterPublish;
        return matchSearch && matchDecision && matchPublish;
      }),
    [cases, search, filterDecision, filterPublish],
  );

  return (
    <div className="p-6 space-y-4 min-w-0 overflow-x-hidden">
      <div className="flex flex-wrap items-center gap-3">
        <div className="flex items-center gap-1.5 bg-white border border-slate-200 rounded-md px-3 py-1.5 flex-1 min-w-[180px] max-w-xs">
          <Search size={13} className="text-slate-400 flex-shrink-0" />
          <input
            value={search}
            onChange={(e) => setSearch(e.target.value)}
            placeholder="搜索案例…"
            className="text-xs bg-transparent outline-none text-slate-700 placeholder-slate-400 w-full min-w-0"
          />
        </div>
        <select
          value={filterDecision}
          onChange={(e) => setFilterDecision(e.target.value)}
          className="text-xs border border-slate-200 rounded px-2 py-1.5 bg-white text-slate-700 outline-none"
        >
          <option value="ALL">所有结论</option>
          {(Object.keys(decisionLabels) as Decision[]).map((d) => (
            <option key={d} value={d}>
              {decisionLabels[d]}
            </option>
          ))}
        </select>
        <select
          value={filterPublish}
          onChange={(e) => setFilterPublish(e.target.value)}
          className="text-xs border border-slate-200 rounded px-2 py-1.5 bg-white text-slate-700 outline-none"
        >
          <option value="ALL">全部发布状态</option>
          <option value="PUBLISHABLE">{publicationStatusLabels.PUBLISHABLE}</option>
          <option value="NOT_PUBLISHABLE">
            {publicationStatusLabels.NOT_PUBLISHABLE}
          </option>
        </select>
        <div className="ml-auto text-xs text-slate-400">
          {filtered.length} / {cases.length} 案件
        </div>
      </div>

      <div className="bg-white border border-slate-200 rounded-lg overflow-x-auto">
        <table className="w-full text-xs min-w-[720px]">
          <thead>
            <tr className="border-b border-slate-200 bg-slate-50">
              {[
                ui.caseName,
                ui.latestDecision,
                ui.assessmentTime,
                ui.publicationStatus,
                ui.blockingReason,
                ui.executionCount,
                ui.actions,
              ].map((h) => (
                <th
                  key={h}
                  className="px-4 py-3 text-left font-semibold text-slate-500 tracking-wide text-[10px]"
                >
                  {h}
                </th>
              ))}
            </tr>
          </thead>
          <tbody>
            {filtered.map((c, i) => (
              <tr
                key={c.id}
                className={cn(
                  "border-b border-slate-100 hover:bg-slate-50 cursor-pointer",
                  i % 2 === 0 ? "" : "bg-slate-50/50",
                )}
                onClick={() => onCaseClick(c.id)}
              >
                <td className="px-4 py-3">
                  <div className="text-slate-800 font-medium">
                    {t(caseLabels, c.id, c.id)}
                  </div>
                  <div className="text-[10px] text-slate-400 mt-0.5">{c.title}</div>
                </td>
                <td className="px-4 py-3">
                  <DecisionBadge decision={c.decision} />
                </td>
                <td className="px-4 py-3 text-slate-500">
                  {formatTime(c.assessmentTime)}
                </td>
                <td className="px-4 py-3">
                  <span
                    className={cn(
                      "text-[10px] font-medium px-1.5 py-0.5 rounded",
                      c.publicationStatus === "PUBLISHABLE"
                        ? "text-emerald-700 bg-emerald-50"
                        : "text-amber-600 bg-amber-50",
                    )}
                  >
                    {t(publicationStatusLabels, c.publicationStatus)}
                  </span>
                </td>
                <td className="px-4 py-3">
                  <div className="flex flex-wrap gap-1">
                    {c.blockingReasons.length === 0 ? (
                      <span className="text-slate-300 text-[10px]">—</span>
                    ) : (
                      c.blockingReasons.map((r) => (
                        <span
                          key={r}
                          className="text-[10px] bg-red-50 text-red-600 px-1 py-0.5 rounded"
                        >
                          {t(blockingReasonLabels, r, r)}
                        </span>
                      ))
                    )}
                  </div>
                </td>
                <td className="px-4 py-3 text-slate-500 text-center">
                  {c.executionCount}
                </td>
                <td className="px-4 py-3">
                  <button
                    type="button"
                    className="flex items-center gap-1 text-blue-600 hover:text-blue-700 text-[10px] font-medium"
                  >
                    <Eye size={11} /> 查看
                  </button>
                </td>
              </tr>
            ))}
          </tbody>
        </table>
      </div>
    </div>
  );
}
