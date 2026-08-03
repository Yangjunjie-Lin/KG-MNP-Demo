import { useState } from "react";
import {
  AlertTriangle,
  CheckCircle2,
  ChevronLeft,
  ChevronRight,
  Play,
  RefreshCw,
} from "lucide-react";
import { FormField } from "../components/FormField";
import { cn } from "../utils/cn";
import {
  authCodeStatusLabels,
  contractStatusLabels,
  identityTypeLabels,
  numberStatusLabels,
  priorityLabels,
  requestTypeLabels,
  ui,
} from "../i18n/zh-CN";

const STEP_LABELS = [
  "基本信息",
  "用户与号码",
  "身份与号码证据",
  "计费与合约",
  "携转历史",
  "提交预览",
];

/** 仅供技术调试模式使用，正式演示界面不展示此内容。 */
const EXAMPLE_JSON = {
  schema_version: "1.0",
  case_id: "CASE-03",
  assessment_time: "2026-07-01T00:00:00Z",
  subscriber: { subscriber_id: "SUB-03" },
  phone_number: { masked_number: "138****0003" },
  account: { account_id: "ACC-03" },
  evidence: {
    identity: { matched: true, source_system: "CRM", status: "VALID" },
    number_status: { status_code: "ACTIVE", source_system: "HLR", status: "VALID" },
    billing: { outstanding_amount: 0, source_system: "BILLING", status: "VALID" },
    contract: {
      contract_status: "ACTIVE",
      contract_end_time: "2027-06-01T00:00:00Z",
      source_system: "CONTRACT",
      status: "VALID",
    },
    porting_history: {
      days_since_last_port: 400,
      source_system: "MNP_HISTORY",
      status: "VALID",
    },
  },
};

const technicalViewEnabled =
  import.meta.env.DEV && import.meta.env.VITE_ENABLE_TECHNICAL_VIEW === "true";

function optionsFrom(map: Record<string, string>) {
  return Object.entries(map).map(([value, label]) => ({ value, label }));
}

export function NewAssessment() {
  const [step, setStep] = useState(1);
  const [mode, setMode] = useState<"form" | "json">("form");
  const [jsonText, setJsonText] = useState(JSON.stringify(EXAMPLE_JSON, null, 2));
  const [priority, setPriority] = useState("NORMAL");
  const [numberStatus, setNumberStatus] = useState("ACTIVE");
  const [contractStatus, setContractStatus] = useState("ACTIVE");
  const [authStatus, setAuthStatus] = useState("VALID");
  const totalSteps = STEP_LABELS.length;
  const showForm = !technicalViewEnabled || mode === "form";
  const showTechnical = technicalViewEnabled && mode === "json";

  const loadExample = () => {
    if (technicalViewEnabled) {
      setJsonText(JSON.stringify(EXAMPLE_JSON, null, 2));
    }
    setPriority("NORMAL");
    setNumberStatus("ACTIVE");
    setContractStatus("ACTIVE");
    setAuthStatus("VALID");
    setStep(1);
  };

  return (
    <div className="p-6 max-w-3xl space-y-5 min-w-0 overflow-x-hidden">
      <div className="flex flex-wrap items-center gap-3">
        {technicalViewEnabled ? (
          <div className="bg-white border border-slate-200 rounded-lg p-0.5 flex">
            {(
              [
                { id: "form" as const, label: ui.formEntry },
                { id: "json" as const, label: ui.technicalDebug },
              ] as const
            ).map((m) => (
              <button
                key={m.id}
                type="button"
                onClick={() => setMode(m.id)}
                className={cn(
                  "px-4 py-1.5 rounded-md text-xs font-medium transition-colors",
                  mode === m.id
                    ? "bg-blue-600 text-white"
                    : "text-slate-600 hover:text-slate-800",
                )}
              >
                {m.label}
              </button>
            ))}
          </div>
        ) : (
          <div className="bg-white border border-slate-200 rounded-lg px-4 py-1.5 text-xs font-medium text-slate-700">
            {ui.formEntry}
          </div>
        )}
        <button
          type="button"
          onClick={loadExample}
          className="flex items-center gap-1.5 text-xs text-blue-600 hover:text-blue-700 border border-blue-200 px-3 py-1.5 rounded-md bg-blue-50"
        >
          <RefreshCw size={11} /> {ui.loadExample}（案例三）
        </button>
      </div>

      {technicalViewEnabled && showTechnical && (
        <div className="text-xs text-amber-700 bg-amber-50 border border-amber-200 rounded-lg px-3 py-2">
          {ui.technicalDebugHint}
        </div>
      )}

      {showForm && (
        <>
          <div className="bg-white border border-slate-200 rounded-lg p-4 overflow-x-auto">
            <div className="flex items-center gap-1 min-w-[520px]">
              {STEP_LABELS.map((label, i) => {
                const n = i + 1;
                return (
                  <div key={n} className="flex items-center gap-1 flex-1 min-w-0">
                    <button
                      type="button"
                      onClick={() => setStep(n)}
                      className="flex items-center gap-1.5 min-w-0"
                    >
                      <div
                        className={cn(
                          "w-6 h-6 rounded-full flex items-center justify-center text-[11px] font-bold flex-shrink-0",
                          n < step
                            ? "bg-emerald-500 text-white"
                            : n === step
                              ? "bg-blue-600 text-white"
                              : "bg-slate-100 text-slate-400",
                        )}
                      >
                        {n < step ? <CheckCircle2 size={12} /> : n}
                      </div>
                      <span
                        className={cn(
                          "text-[10px] hidden sm:block truncate",
                          n === step ? "text-blue-700 font-medium" : "text-slate-400",
                        )}
                      >
                        {label}
                      </span>
                    </button>
                    {i < totalSteps - 1 && (
                      <div
                        className={cn(
                          "flex-1 h-px",
                          n < step ? "bg-emerald-300" : "bg-slate-200",
                        )}
                      />
                    )}
                  </div>
                );
              })}
            </div>
          </div>

          <div className="bg-white border border-slate-200 rounded-lg p-5">
            <h3 className="text-sm font-semibold text-slate-700 mb-4">
              {STEP_LABELS[step - 1]}
            </h3>
            {step === 1 && (
              <div className="grid grid-cols-1 sm:grid-cols-2 gap-4">
                <FormField label="案例名称" placeholder="案例十" required />
                <FormField
                  label="申请类型"
                  type="select"
                  options={optionsFrom(requestTypeLabels)}
                />
                <FormField label="提交时间" type="datetime" />
                <FormField label="来源系统" placeholder="客户关系系统" />
                <FormField label="运营商标识" placeholder="运营商一" />
                <FormField
                  label="优先级"
                  type="select"
                  value={priority}
                  onChange={setPriority}
                  options={optionsFrom(priorityLabels)}
                />
              </div>
            )}
            {step === 2 && (
              <div className="grid grid-cols-1 sm:grid-cols-2 gap-4">
                <FormField label="订户编号" placeholder="订户三" required />
                <FormField label="手机号码" placeholder="138****0003" required />
                <FormField label="账户编号" placeholder="账户三" />
                <FormField
                  label="账户状态"
                  type="select"
                  options={[
                    { value: "ACTIVE", label: numberStatusLabels.ACTIVE },
                    { value: "SUSPENDED", label: numberStatusLabels.SUSPENDED },
                    { value: "CLOSED", label: numberStatusLabels.CLOSED },
                  ]}
                />
              </div>
            )}
            {step === 3 && (
              <div className="grid grid-cols-1 sm:grid-cols-2 gap-4">
                <FormField
                  label="证件类型"
                  type="select"
                  options={optionsFrom(identityTypeLabels)}
                />
                <FormField label="证件号码" placeholder="已脱敏" />
                <FormField label="证件有效期至" type="date" />
                <FormField
                  label="号码状态"
                  type="select"
                  value={numberStatus}
                  onChange={setNumberStatus}
                  options={optionsFrom(numberStatusLabels)}
                />
                <FormField label="号码注册时间" type="datetime" />
                <FormField label="距上次携转天数" placeholder="400" type="number" />
              </div>
            )}
            {step === 4 && (
              <div className="grid grid-cols-1 sm:grid-cols-2 gap-4">
                <FormField label="未结费用（元）" placeholder="0.00" type="number" />
                <FormField label="最近账单日期" type="date" />
                <FormField
                  label="合约状态"
                  type="select"
                  value={contractStatus}
                  onChange={setContractStatus}
                  options={optionsFrom(contractStatusLabels)}
                />
                <FormField label="合约到期时间" type="date" />
                <FormField label="合约编号" placeholder="合约三" />
              </div>
            )}
            {step === 5 && (
              <div className="grid grid-cols-1 sm:grid-cols-2 gap-4">
                <FormField label="上次携转日期" type="date" />
                <FormField label="授权码" placeholder="已脱敏" />
                <FormField label="授权码签发时间" type="datetime" />
                <FormField
                  label="授权码状态"
                  type="select"
                  value={authStatus}
                  onChange={setAuthStatus}
                  options={optionsFrom(authCodeStatusLabels)}
                />
                <FormField label="原运营商" placeholder="运营商甲" />
                <FormField label="目标运营商" placeholder="运营商乙" />
              </div>
            )}
            {step === 6 && (
              <div className="space-y-3 text-xs">
                <div className="bg-slate-50 border border-slate-200 rounded-lg p-3">
                  <div className="font-semibold text-slate-700 mb-2">提交前确认</div>
                  <div className="text-slate-500 leading-relaxed">
                    请确认以上字段填写正确。提交后系统将执行评估流程，结果将在评估结果页面显示。
                  </div>
                </div>
                <div className="flex items-center gap-2 text-amber-600 bg-amber-50 border border-amber-200 rounded p-2">
                  <AlertTriangle size={13} />
                  <span>当前为演示环境，提交不会写入真实数据库。</span>
                </div>
              </div>
            )}
          </div>

          <div className="flex items-center gap-3">
            {step > 1 && (
              <button
                type="button"
                onClick={() => setStep(step - 1)}
                className="flex items-center gap-1.5 text-xs text-slate-600 border border-slate-200 px-3 py-1.5 rounded-md hover:bg-slate-50"
              >
                <ChevronLeft size={13} /> 上一步
              </button>
            )}
            {step < totalSteps ? (
              <button
                type="button"
                onClick={() => setStep(step + 1)}
                className="flex items-center gap-1.5 bg-blue-600 hover:bg-blue-700 text-white text-xs px-4 py-1.5 rounded-md font-medium transition-colors"
              >
                下一步 <ChevronRight size={13} />
              </button>
            ) : (
              <button
                type="button"
                className="flex items-center gap-1.5 bg-emerald-600 hover:bg-emerald-700 text-white text-xs px-4 py-1.5 rounded-md font-medium transition-colors"
              >
                <Play size={11} /> {ui.submitAssessment}
              </button>
            )}
          </div>
        </>
      )}

      {showTechnical && (
        <div className="bg-white border border-slate-200 rounded-lg p-4">
          <div className="flex items-center justify-between mb-3">
            <span className="text-xs font-semibold text-slate-600">{ui.technicalDebug}</span>
            <span className="text-[10px] text-slate-400">
              数据规范：{ui.schemaVersion}
            </span>
          </div>
          <textarea
            className="w-full h-80 text-xs bg-slate-950 text-emerald-300 rounded-lg p-4 outline-none resize-none leading-relaxed border border-slate-800"
            value={jsonText}
            onChange={(e) => setJsonText(e.target.value)}
          />
          <div className="flex items-center gap-3 mt-3">
            <button
              type="button"
              className="flex items-center gap-1.5 bg-blue-600 hover:bg-blue-700 text-white text-xs px-4 py-1.5 rounded-md font-medium transition-colors"
            >
              <Play size={11} /> {ui.submitAssessment}
            </button>
            <span className="text-xs text-slate-400">演示环境不会写入真实数据库</span>
          </div>
        </div>
      )}
    </div>
  );
}
