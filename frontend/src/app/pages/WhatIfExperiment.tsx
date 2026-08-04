import { ArrowRight, FlaskConical, Play } from "lucide-react";
import { useEffect, useMemo, useState } from "react";
import { ApiErrorState, EmptyState, MutationStatus, PageSkeleton } from "../components/dataStates";
import { DecisionBadge, StatusBadge } from "../components/StatusBadges";
import {
  blockingReasonLabels,
  caseLabels,
  contractStatusLabels,
  ruleLabels,
  translateOrUnknown,
  ui,
} from "../i18n/zh-CN";
import { useAssessment, useCases, useWhatIf } from "../query/hooks/useAppQueries";

type ChangedField = "contract" | "billing" | "history";

export function WhatIfExperiment() {
  const cases = useCases();
  const mutation = useWhatIf();
  const [executionId, setExecutionId] = useState("");
  const [contractStatus, setContractStatus] = useState("ACTIVE");
  const [balance, setBalance] = useState("0");
  const [days, setDays] = useState("0");
  const [changedFields, setChangedFields] = useState<Set<ChangedField>>(new Set());
  const runnable = useMemo(
    () => (cases.data ?? []).filter((item) => item.latestExecutionId),
    [cases.data],
  );
  const selectedExecution = executionId
    || runnable.find((item) => item.id === "CASE-03")?.latestExecutionId
    || runnable[0]?.latestExecutionId
    || "";
  const baseline = useAssessment(selectedExecution);

  useEffect(() => {
    if (!baseline.data) return;
    setContractStatus(baseline.data.whatIfBaseline.contractStatus);
    setBalance(String(baseline.data.whatIfBaseline.outstandingAmount));
    setDays(String(baseline.data.whatIfBaseline.daysSinceLastPort));
    setChangedFields(new Set());
  }, [baseline.data]);

  const markChanged = (field: ChangedField) => {
    setChangedFields((current) => new Set(current).add(field));
    mutation.reset();
  };

  const run = () => {
    mutation.mutate({
      executionId: selectedExecution,
      changes: {
        contractStatus: changedFields.has("contract") ? contractStatus : undefined,
        outstandingAmount: changedFields.has("billing") ? Number(balance) : undefined,
        daysSinceLastPort: changedFields.has("history") ? Number(days) : undefined,
      },
    });
  };

  if (cases.isLoading) return <PageSkeleton />;
  if (cases.isError) {
    return <ApiErrorState error={cases.error} onRetry={() => void cases.refetch()} />;
  }
  if (!runnable.length) {
    return <EmptyState message="暂无可用于推演的真实评估，请先运行示例案例。" />;
  }
  if (baseline.isLoading) return <PageSkeleton />;
  if (baseline.isError) {
    return <ApiErrorState error={baseline.error} onRetry={() => void baseline.refetch()} />;
  }
  const selectedCase = runnable.find((item) => item.latestExecutionId === selectedExecution);

  return (
    <div className="space-y-5 overflow-y-auto p-6">
      <div className="flex flex-wrap items-center gap-3">
        <FlaskConical className="text-blue-600" size={20} />
        <div>
          <h1 className="font-semibold text-slate-800">情景推演</h1>
          <p className="text-xs text-slate-500">基准为已持久化执行；结论和全部差异由后端计算。</p>
        </div>
        {(cases.isFetching || baseline.isFetching) && (
          <span role="status" className="ml-auto text-xs text-slate-400">正在刷新真实评估…</span>
        )}
      </div>

      <section className="rounded-lg border border-slate-200 bg-white p-5">
        <label className="mb-1 block text-xs font-medium text-slate-500">基准评估</label>
        <select
          aria-label="基准评估"
          value={selectedExecution}
          onChange={(event) => {
            setExecutionId(event.target.value);
            setChangedFields(new Set());
            mutation.reset();
          }}
          className="w-full max-w-sm rounded border border-slate-200 px-3 py-2 text-sm"
        >
          {runnable.map((item) => (
            <option key={item.latestExecutionId ?? item.id} value={item.latestExecutionId ?? ""}>
              {translateOrUnknown(caseLabels, item.id, ui.unknownCase)} · {item.assessmentTime.slice(0, 10)}
            </option>
          ))}
        </select>
      </section>

      <div className="grid gap-4 md:grid-cols-2">
        <section className="rounded-lg border border-slate-200 bg-white p-5">
          <h2 className="mb-3 text-xs font-semibold text-slate-500">基准方案</h2>
          {baseline.data && <DecisionBadge decision={baseline.data.decision} />}
          {selectedCase && (
            <div className="mt-4 text-xs text-slate-500">
              {translateOrUnknown(caseLabels, selectedCase.id, ui.unknownCase)}
            </div>
          )}
        </section>
        <section className="rounded-lg border border-blue-200 bg-blue-50 p-5">
          <h2 className="mb-3 text-xs font-semibold text-blue-700">推演修改</h2>
          <div className="grid gap-3">
            <label className="text-xs text-slate-600">
              合约状态
              <select
                value={contractStatus}
                onChange={(event) => {
                  setContractStatus(event.target.value);
                  markChanged("contract");
                }}
                className="mt-1 w-full rounded border px-2 py-1.5"
              >
                <option value="ACTIVE">{contractStatusLabels.ACTIVE}</option>
                <option value="EXPIRED">{contractStatusLabels.EXPIRED}</option>
                <option value="TERMINATED">{contractStatusLabels.TERMINATED}</option>
              </select>
            </label>
            <label className="text-xs text-slate-600">
              未结费用
              <input
                aria-label="未结费用"
                type="number"
                min="0"
                value={balance}
                onChange={(event) => {
                  setBalance(event.target.value);
                  markChanged("billing");
                }}
                className="mt-1 w-full rounded border px-2 py-1.5"
              />
            </label>
            <label className="text-xs text-slate-600">
              距上次携转天数
              <input
                aria-label="距上次携转天数"
                type="number"
                min="0"
                value={days}
                onChange={(event) => {
                  setDays(event.target.value);
                  markChanged("history");
                }}
                className="mt-1 w-full rounded border px-2 py-1.5"
              />
            </label>
          </div>
        </section>
      </div>

      <button
        type="button"
        disabled={mutation.isPending || changedFields.size === 0}
        onClick={run}
        className="inline-flex items-center gap-2 rounded bg-blue-600 px-4 py-2 text-sm font-medium text-white disabled:opacity-50"
      >
        <Play size={14} />运行后端推演
      </button>
      <MutationStatus pending={mutation.isPending} error={mutation.error} />

      {mutation.data && (
        <section className="space-y-4" data-testid="what-if-result">
          <div className="flex flex-wrap items-center gap-3 rounded-lg border border-slate-200 bg-white p-5">
            <DecisionBadge decision={mutation.data.baselineDecision} />
            <ArrowRight size={16} className="text-slate-400" />
            <DecisionBadge decision={mutation.data.scenarioDecision} />
            <span className="text-xs text-slate-500">
              {mutation.data.decisionChanged ? "结论已改变" : "结论未改变"}
            </span>
          </div>

          <div className="rounded-lg border border-slate-200 bg-white p-5">
            <h2 className="mb-3 text-sm font-semibold text-slate-700">规则变化</h2>
            {mutation.data.ruleChanges.length === 0 ? (
              <div className="text-xs text-slate-500">规则执行结果无变化</div>
            ) : (
              <div className="space-y-2">
                {mutation.data.ruleChanges.map((item, index) => (
                  <div key={`${item.ruleId}-${index}`} className="flex flex-wrap items-center gap-3 border-b py-2 text-xs">
                    <span className="min-w-40 text-violet-700">
                      {translateOrUnknown(ruleLabels, item.ruleId, ui.unknownRule)}
                    </span>
                    <StatusBadge status={item.statusBefore} />
                    <ArrowRight size={12} />
                    <StatusBadge status={item.statusAfter} />
                    <span className="text-slate-500">{item.changed ? "发生变化" : "无变化"}</span>
                  </div>
                ))}
              </div>
            )}
          </div>

          <div className="grid gap-4 md:grid-cols-3">
            <div className="rounded-lg border border-slate-200 bg-white p-4 text-xs text-slate-600">
              <h2 className="mb-2 font-semibold text-slate-700">阻塞原因变化</h2>
              <div>新增：{mutation.data.reasonChanges.added.length
                ? mutation.data.reasonChanges.added.map((reason) => translateOrUnknown(blockingReasonLabels, reason, ui.unknownReason)).join("、")
                : "无"}</div>
              <div className="mt-1">移除：{mutation.data.reasonChanges.removed.length
                ? mutation.data.reasonChanges.removed.map((reason) => translateOrUnknown(blockingReasonLabels, reason, ui.unknownReason)).join("、")
                : "无"}</div>
            </div>
            <div className="rounded-lg border border-slate-200 bg-white p-4 text-xs text-slate-600">
              <h2 className="mb-2 font-semibold text-slate-700">证据变化</h2>
              <div>新增 {mutation.data.evidenceChanges.addedCount} 项，移除 {mutation.data.evidenceChanges.removedCount} 项，修改 {mutation.data.evidenceChanges.modifiedCount} 项</div>
            </div>
            <div className="rounded-lg border border-slate-200 bg-white p-4 text-xs text-slate-600">
              <h2 className="mb-2 font-semibold text-slate-700">追溯变化</h2>
              <div>节点：{mutation.data.traceChanges.baselineNodeCount} → {mutation.data.traceChanges.scenarioNodeCount}</div>
              <div className="mt-1">关系：{mutation.data.traceChanges.baselineEdgeCount} → {mutation.data.traceChanges.scenarioEdgeCount}</div>
            </div>
          </div>
        </section>
      )}
    </div>
  );
}
