import type { ReactNode } from "react";
import { CheckCircle2, XCircle, AlertTriangle, Info } from "lucide-react";
import { cn } from "../utils/cn";
import {
  decisionLabels,
  evidenceStatusLabels,
  moduleLabels,
  stepStatusLabels,
  authCodeStatusLabels,
  contractStatusLabels,
  numberStatusLabels,
  publicationStatusLabels,
  serviceStatusLabels,
  ruleLifecycleLabels,
  translateOrUnknown,
  ui,
} from "../i18n/zh-CN";
import type { Decision } from "../types/common";

const decisionStyles: Record<Decision, { bg: string; icon: ReactNode }> = {
  ELIGIBLE: {
    bg: "bg-emerald-50 text-emerald-700 ring-1 ring-emerald-200",
    icon: <CheckCircle2 size={12} />,
  },
  BLOCKED: {
    bg: "bg-red-50 text-red-700 ring-1 ring-red-200",
    icon: <XCircle size={12} />,
  },
  MANUAL_REVIEW: {
    bg: "bg-amber-50 text-amber-700 ring-1 ring-amber-200",
    icon: <AlertTriangle size={12} />,
  },
  CONDITIONAL: {
    bg: "bg-blue-50 text-blue-700 ring-1 ring-blue-200",
    icon: <Info size={12} />,
  },
};

export function DecisionBadge({ decision }: { decision: Decision }) {
  const style = decisionStyles[decision] ?? decisionStyles.MANUAL_REVIEW;
  const label = translateOrUnknown(decisionLabels, decision, ui.unknownStatus);
  return (
    <span
      className={cn(
        "inline-flex items-center gap-1 px-2 py-0.5 rounded text-xs font-medium",
        style.bg,
      )}
    >
      {style.icon}
      {label}
    </span>
  );
}

const statusColorMap: Record<string, string> = {
  PASS: "bg-emerald-50 text-emerald-700 ring-1 ring-emerald-200",
  PASSED: "bg-emerald-50 text-emerald-700 ring-1 ring-emerald-200",
  FAIL: "bg-red-50 text-red-700 ring-1 ring-red-200",
  FAILED: "bg-red-50 text-red-700 ring-1 ring-red-200",
  SKIP: "bg-slate-50 text-slate-500 ring-1 ring-slate-200",
  SKIPPED: "bg-slate-50 text-slate-400 ring-1 ring-slate-200",
  VALID: "bg-cyan-50 text-cyan-700 ring-1 ring-cyan-200",
  EXPIRED: "bg-red-50 text-red-600 ring-1 ring-red-200",
  MISSING: "bg-slate-50 text-slate-500 ring-1 ring-slate-200",
  CONFLICT: "bg-orange-50 text-orange-700 ring-1 ring-orange-200",
  DONE: "bg-blue-50 text-blue-700 ring-1 ring-blue-200",
  PENDING: "bg-amber-50 text-amber-600 ring-1 ring-amber-200",
  ACTIVE: "bg-emerald-50 text-emerald-700 ring-1 ring-emerald-200",
  NORMAL: "bg-emerald-50 text-emerald-700 ring-1 ring-emerald-200",
  ONLINE: "bg-emerald-50 text-emerald-700 ring-1 ring-emerald-200",
  DEGRADED: "bg-amber-50 text-amber-700 ring-1 ring-amber-200",
  PUBLISHABLE: "bg-emerald-50 text-emerald-700 ring-1 ring-emerald-200",
  NOT_PUBLISHABLE: "bg-slate-50 text-slate-600 ring-1 ring-slate-200",
  REVOKED: "bg-red-50 text-red-600 ring-1 ring-red-200",
  UNKNOWN: "bg-slate-50 text-slate-500 ring-1 ring-slate-200",
  NOT_EVALUATED: "bg-slate-50 text-slate-500 ring-1 ring-slate-200",
  CLOSED: "bg-slate-50 text-slate-600 ring-1 ring-slate-200",
  SUSPENDED: "bg-amber-50 text-amber-700 ring-1 ring-amber-200",
  CANCELLED: "bg-slate-50 text-slate-600 ring-1 ring-slate-200",
  ISSUED: "bg-emerald-50 text-emerald-700 ring-1 ring-emerald-200",
  SIGNED_PENDING_EFFECTIVE: "bg-amber-50 text-amber-700 ring-1 ring-amber-200",
};

function resolveStatusLabel(status: string): string {
  const maps = [
    stepStatusLabels,
    evidenceStatusLabels,
    publicationStatusLabels,
    authCodeStatusLabels,
    contractStatusLabels,
    numberStatusLabels,
    serviceStatusLabels,
    ruleLifecycleLabels,
  ];
  for (const map of maps) {
    if (map[status]) return map[status];
  }
  return translateOrUnknown({}, status, ui.unknownStatus);
}

export function StatusBadge({ status }: { status: string }) {
  const label = resolveStatusLabel(status);
  return (
    <span
      className={cn(
        "inline-flex items-center gap-1 px-2 py-0.5 rounded text-xs font-medium",
        statusColorMap[status] || "bg-slate-50 text-slate-500 ring-1 ring-slate-200",
      )}
    >
      {label}
    </span>
  );
}

/** 规则生命周期专用：当前有效 / 历史版本 */
export function RuleLifecycleBadge({ historical }: { historical: boolean }) {
  const label = historical ? ruleLifecycleLabels.HISTORICAL : ruleLifecycleLabels.CURRENT;
  return (
    <span
      className={cn(
        "inline-flex items-center gap-1 px-2 py-0.5 rounded text-xs font-medium",
        historical
          ? "bg-slate-50 text-slate-500 ring-1 ring-slate-200"
          : "bg-emerald-50 text-emerald-700 ring-1 ring-emerald-200",
      )}
    >
      {label}
    </span>
  );
}

const moduleColorMap: Record<string, string> = {
  Core: "bg-blue-50 text-blue-700",
  Identity: "bg-violet-50 text-violet-700",
  AccountBilling: "bg-cyan-50 text-cyan-700",
  Contract: "bg-indigo-50 text-indigo-700",
  MNPProcess: "bg-teal-50 text-teal-700",
  Eligibility: "bg-emerald-50 text-emerald-700",
  Evidence: "bg-cyan-50 text-cyan-700",
  Rules: "bg-violet-50 text-violet-700",
  Regulatory: "bg-indigo-50 text-indigo-800",
};

export function ModuleTag({ module }: { module: string }) {
  const label = translateOrUnknown(moduleLabels, module, ui.unknownModule);
  return (
    <span
      className={cn(
        "inline-flex items-center px-1.5 py-0.5 rounded text-xs font-medium",
        moduleColorMap[module] || "bg-slate-100 text-slate-600",
      )}
    >
      {label}
    </span>
  );
}
