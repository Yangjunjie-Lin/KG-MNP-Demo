import { XCircle } from "lucide-react";
import {
  blockingReasonLabels,
  evidenceTypeLabels,
  remediationActionLabels,
  regulatoryClauseLabels,
  ruleLabels,
  t,
  ui,
} from "../i18n/zh-CN";

function evidenceDisplayLabel(raw: string): string {
  const upper = raw.toUpperCase();
  if (upper.includes("IDENTITY")) return evidenceTypeLabels.IDENTITY_MATCH;
  if (upper.includes("NUMBER")) return evidenceTypeLabels.NUMBER_STATUS;
  if (upper.includes("BILLING")) return evidenceTypeLabels.BILLING_BALANCE;
  if (upper.includes("CONTRACT")) return evidenceTypeLabels.CONTRACT_STATUS;
  if (upper.includes("PORTING")) return evidenceTypeLabels.PORTING_HISTORY;
  return t(evidenceTypeLabels, raw, raw);
}

export function BlockingReasonCard({
  code,
  description,
  evidence,
  ruleId,
  ruleVersion,
  clause,
  action,
}: {
  code: string;
  description: string;
  evidence: string[];
  ruleId: string;
  ruleVersion: string;
  clause: string;
  action: string;
}) {
  const reasonLabel = t(blockingReasonLabels, code, code);
  const ruleLabel = t(ruleLabels, ruleId, ruleId);
  const actionLabel = t(remediationActionLabels, action, action);
  const clauseLabel = t(regulatoryClauseLabels, clause, clause);

  return (
    <div className="bg-white border border-red-200 rounded-lg overflow-hidden">
      <div className="bg-red-50 px-4 py-3 border-b border-red-100 flex items-center gap-2">
        <XCircle size={15} className="text-red-600 flex-shrink-0" />
        <span className="text-sm font-semibold text-red-700">{reasonLabel}</span>
      </div>
      <div className="p-4 grid grid-cols-1 sm:grid-cols-2 gap-4 text-xs">
        <div>
          <div className="text-slate-400 font-medium mb-1 text-[10px]">{ui.blockingReason}</div>
          <div className="text-slate-700 leading-relaxed">{description}</div>
        </div>
        <div>
          <div className="text-slate-400 font-medium mb-1 text-[10px]">{ui.supportingEvidence}</div>
          <div className="flex flex-wrap gap-1">
            {evidence.map((e) => (
              <span
                key={e}
                className="text-cyan-700 bg-cyan-50 px-1.5 py-0.5 rounded border border-cyan-100"
              >
                {evidenceDisplayLabel(e)}
              </span>
            ))}
          </div>
        </div>
        <div>
          <div className="text-slate-400 font-medium mb-1 text-[10px]">{ui.triggeredRule}</div>
          <div className="flex flex-wrap items-center gap-2">
            <span className="text-violet-700 bg-violet-50 px-1.5 py-0.5 rounded border border-violet-100">
              {ruleLabel}
            </span>
            <span className="text-slate-500 bg-slate-50 px-1.5 py-0.5 rounded">
              版本 {ruleVersion}
            </span>
          </div>
        </div>
        <div>
          <div className="text-slate-400 font-medium mb-1 text-[10px]">{ui.remediationAction}</div>
          <div className="text-emerald-700 leading-relaxed">{actionLabel}</div>
        </div>
        <div className="sm:col-span-2">
          <div className="text-slate-400 font-medium mb-1 text-[10px]">{ui.regulatoryClause}</div>
          <div className="text-indigo-800 bg-indigo-50 rounded p-2 border border-indigo-100 leading-relaxed">
            {clauseLabel}
          </div>
        </div>
      </div>
    </div>
  );
}
