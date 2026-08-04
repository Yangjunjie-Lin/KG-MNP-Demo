import { useState } from "react";
import { Controller, type FieldPath, useForm } from "react-hook-form";
import { RefreshCw, Send } from "lucide-react";
import { useNavigate } from "react-router";
import {
  adaptAssessmentFormToPayload,
  adaptExamplePayloadToAssessmentForm,
  formatTechnicalAssessmentPayload,
  parseTechnicalAssessmentPayload,
} from "../../api/adapters/assessmentFormAdapter";
import { apiConfig } from "../../api/config";
import { ApiErrorState, FieldErrorSummary, MutationStatus } from "../components/dataStates";
import { FormField } from "../components/FormField";
import {
  caseLabels,
  currencyLabels,
  dataSourceLabels,
  numberStatusLabels,
} from "../i18n/zh-CN";
import { useCreateAssessment } from "../query/hooks/useAppQueries";
import { getExample } from "../services/exampleService";
import {
  emptyAssessmentFormValues,
  type AssessmentFormValues,
} from "../types/assessmentForm";

const caseOptions = [
  { value: "", label: "请选择案例" },
  ...Object.entries(caseLabels).map(([value, label]) => ({ value, label })),
];
const sourceSystemOptions = Object.entries(dataSourceLabels).map(([value, label]) => ({
  value,
  label,
}));
const numberStatusOptions = Object.entries(numberStatusLabels).map(([value, label]) => ({
  value,
  label,
}));
const currencyOptions = Object.entries(currencyLabels).map(([value, label]) => ({
  value,
  label,
}));
const evidenceStatusOptions = [
  { value: "VALID", label: "有效" },
  { value: "EXPIRED", label: "已过期" },
];

type FormFieldType = "text" | "datetime" | "number" | "select";
type FormFieldOption = { value: string; label: string };

export function NewAssessment() {
  const navigate = useNavigate();
  const mutation = useCreateAssessment();
  const [loadError, setLoadError] = useState<unknown>();
  const [loadingExample, setLoadingExample] = useState(false);
  const [mode, setMode] = useState<"form" | "technical">("form");
  const [technicalPayload, setTechnicalPayload] = useState("");
  const [technicalError, setTechnicalError] = useState("");
  const [formConversionError, setFormConversionError] = useState("");
  const {
    control,
    handleSubmit,
    reset,
    formState: { errors },
  } = useForm<AssessmentFormValues>({ defaultValues: emptyAssessmentFormValues });

  const loadExample = async () => {
    setLoadingExample(true);
    setLoadError(undefined);
    try {
      const example = await getExample("CASE-03");
      const formValues = adaptExamplePayloadToAssessmentForm(example.input);
      setTechnicalPayload(formatTechnicalAssessmentPayload(example.input));
      reset(formValues);
      setFormConversionError("");
      setTechnicalError("");
    } catch (error) {
      setLoadError(error);
    } finally {
      setLoadingExample(false);
    }
  };

  const submit = (values: AssessmentFormValues) => {
    setFormConversionError("");
    try {
      const payload = adaptAssessmentFormToPayload(values);
      mutation.mutate(payload, {
        onSuccess: (assessment) => navigate(`/assessments/${assessment.executionId}`),
      });
    } catch {
      setFormConversionError("请检查时间和数值格式后重试。");
    }
  };

  const submitTechnical = () => {
    setTechnicalError("");
    try {
      const payload = parseTechnicalAssessmentPayload(technicalPayload);
      mutation.mutate(payload, {
        onSuccess: (assessment) => navigate(`/assessments/${assessment.executionId}`),
      });
    } catch {
      setTechnicalError("调试输入格式或必填结构无效，请检查后重试。");
    }
  };

  const field = (
    name: FieldPath<AssessmentFormValues>,
    label: string,
    type: FormFieldType = "text",
    options?: FormFieldOption[],
    required = true,
  ) => (
    <Controller
      name={name}
      control={control}
      rules={
        required
          ? {
              validate: (value) =>
                (value !== undefined && value !== null && value !== "") || `${label}为必填项`,
            }
          : undefined
      }
      render={({ field: input }) => (
        <FormField
          label={label}
          required={required}
          type={type}
          options={options}
          value={String(input.value ?? "")}
          onChange={input.onChange}
          optional={!required}
        />
      )}
    />
  );

  if (loadError) {
    return <ApiErrorState error={loadError} onRetry={() => void loadExample()} />;
  }

  if (mode === "technical") {
    return (
      <div className="max-w-4xl space-y-4 overflow-y-auto p-6">
        <div className="flex flex-wrap items-center justify-between gap-3">
          <div>
            <h1 className="text-lg font-semibold text-slate-800">技术调试输入</h1>
            <p className="mt-1 text-xs text-slate-500">调试提交仍由后端执行完整资格评估。</p>
          </div>
          <button
            type="button"
            onClick={() => setMode("form")}
            className="rounded border border-slate-200 bg-white px-3 py-2 text-xs text-slate-700"
          >
            返回表单录入
          </button>
        </div>
        <textarea
          aria-label="调试评估输入"
          value={technicalPayload}
          onChange={(event) => {
            setTechnicalPayload(event.target.value);
            setTechnicalError("");
          }}
          className="min-h-[520px] w-full rounded border border-slate-300 bg-white p-3 font-mono text-xs"
        />
        <div className="flex flex-wrap items-center gap-3">
          <button
            type="button"
            onClick={() => void loadExample()}
            disabled={loadingExample}
            className="rounded border border-blue-200 bg-blue-50 px-3 py-2 text-xs text-blue-700"
          >
            加载后端示例
          </button>
          <button
            type="button"
            onClick={submitTechnical}
            disabled={mutation.isPending}
            className="rounded bg-blue-600 px-4 py-2 text-xs font-medium text-white disabled:opacity-50"
          >
            提交真实评估
          </button>
        </div>
        {technicalError && (
          <div role="alert" className="text-xs text-red-700">
            {technicalError}
          </div>
        )}
        <FieldErrorSummary error={mutation.error} />
        <MutationStatus pending={mutation.isPending} error={mutation.error} />
      </div>
    );
  }

  return (
    <form onSubmit={handleSubmit(submit)} className="max-w-4xl space-y-5 overflow-y-auto p-6">
      <div className="flex flex-wrap items-center justify-between gap-3">
        <div>
          <h1 className="text-lg font-semibold text-slate-800">新建资格评估</h1>
          <p className="mt-1 text-xs text-slate-500">所有资格结论由后端规则与知识图谱计算。</p>
        </div>
        <div className="flex gap-2">
          {apiConfig.technicalViewEnabled && (
            <button
              type="button"
              onClick={() => setMode("technical")}
              className="rounded border border-slate-200 bg-white px-3 py-2 text-xs text-slate-600"
            >
              技术调试
            </button>
          )}
          <button
            type="button"
            onClick={() => void loadExample()}
            disabled={loadingExample}
            className="inline-flex items-center gap-1.5 rounded border border-blue-200 bg-blue-50 px-3 py-2 text-xs font-medium text-blue-700"
          >
            <RefreshCw size={13} className={loadingExample ? "animate-spin" : ""} />
            加载示例（案例三）
          </button>
        </div>
      </div>

      <section className="rounded-lg border border-slate-200 bg-white p-5">
        <h2 className="mb-4 text-sm font-semibold text-slate-700">基本信息</h2>
        <div className="grid gap-4 md:grid-cols-2">
          {field("caseId", "案例编号", "select", caseOptions)}
          {field("assessmentTime", "评估时间", "datetime")}
          {field("subscriber.subscriberId", "订户编号")}
          {field("phoneNumber.maskedNumber", "脱敏手机号码")}
          {field("account.accountId", "账户编号")}
        </div>
      </section>

      <section className="rounded-lg border border-slate-200 bg-white p-5">
        <h2 className="mb-4 text-sm font-semibold text-slate-700">实名与号码证据</h2>
        <div className="grid gap-4 md:grid-cols-2">
          {field("evidence.identity.matched", "实名信息是否一致", "select", [
            { value: "true", label: "一致" },
            { value: "false", label: "不一致" },
          ])}
          {field("evidence.identity.sourceSystem", "实名证据来源", "select", sourceSystemOptions)}
          {field("evidence.identity.status", "实名证据状态", "select", evidenceStatusOptions)}
          {field("evidence.identity.generatedAt", "实名证据生成时间", "datetime")}
          {field("evidence.identity.validUntil", "实名证据有效期", "datetime")}
          {field("evidence.numberStatus.statusCode", "号码状态", "select", numberStatusOptions)}
          {field(
            "evidence.numberStatus.sourceSystem",
            "号码证据来源",
            "select",
            sourceSystemOptions,
          )}
          {field("evidence.numberStatus.status", "号码证据状态", "select", evidenceStatusOptions)}
          {field("evidence.numberStatus.generatedAt", "号码证据生成时间", "datetime")}
          {field("evidence.numberStatus.validUntil", "号码证据有效期", "datetime")}
        </div>
      </section>

      <section className="rounded-lg border border-slate-200 bg-white p-5">
        <h2 className="mb-4 text-sm font-semibold text-slate-700">计费与合约证据</h2>
        <div className="grid gap-4 md:grid-cols-2">
          {field("evidence.billing.outstandingAmount", "未结费用", "number")}
          {field("evidence.billing.currency", "货币", "select", currencyOptions)}
          {field("evidence.billing.hasPaymentArrangement", "是否有付款安排", "select", [
            { value: "false", label: "否" },
            { value: "true", label: "是" },
          ])}
          {field("evidence.billing.sourceSystem", "计费证据来源", "select", sourceSystemOptions)}
          {field("evidence.billing.status", "计费证据状态", "select", evidenceStatusOptions)}
          {field("evidence.billing.generatedAt", "计费证据生成时间", "datetime")}
          {field("evidence.billing.validUntil", "计费证据有效期", "datetime")}
          {field("evidence.contract.contractStatus", "合约状态", "select", [
            { value: "ACTIVE", label: "有效" },
            { value: "EXPIRED", label: "已到期" },
            { value: "TERMINATED", label: "已解除" },
          ])}
          {field("evidence.contract.contractEndTime", "合约结束时间", "datetime", undefined, false)}
          {field("evidence.contract.sourceSystem", "合约证据来源", "select", sourceSystemOptions)}
          {field("evidence.contract.status", "合约证据状态", "select", evidenceStatusOptions)}
          {field("evidence.contract.generatedAt", "合约证据生成时间", "datetime")}
          {field("evidence.contract.validUntil", "合约证据有效期", "datetime")}
        </div>
      </section>

      <section className="rounded-lg border border-slate-200 bg-white p-5">
        <h2 className="mb-4 text-sm font-semibold text-slate-700">携转历史证据</h2>
        <div className="grid gap-4 md:grid-cols-2">
          {field("evidence.portingHistory.daysSinceLastPort", "距上次携转天数", "number")}
          {field(
            "evidence.portingHistory.sourceSystem",
            "携转历史来源",
            "select",
            sourceSystemOptions,
          )}
          {field("evidence.portingHistory.status", "携转历史证据状态", "select", evidenceStatusOptions)}
          {field("evidence.portingHistory.generatedAt", "携转历史生成时间", "datetime")}
          {field("evidence.portingHistory.validUntil", "携转历史有效期", "datetime")}
        </div>
      </section>

      {Object.keys(errors).length > 0 && (
        <div role="alert" className="rounded border border-red-200 bg-red-50 p-3 text-xs text-red-700">
          请完整填写所有必填字段。
        </div>
      )}
      {formConversionError && (
        <div role="alert" className="rounded border border-red-200 bg-red-50 p-3 text-xs text-red-700">
          {formConversionError}
        </div>
      )}
      <FieldErrorSummary error={mutation.error} />
      <MutationStatus pending={mutation.isPending} error={mutation.error} />
      <button
        type="submit"
        disabled={mutation.isPending}
        className="inline-flex items-center gap-2 rounded-md bg-blue-600 px-4 py-2 text-sm font-medium text-white hover:bg-blue-700 disabled:opacity-50"
      >
        <Send size={14} />
        {mutation.isPending ? "正在提交" : "提交真实评估"}
      </button>
    </form>
  );
}
