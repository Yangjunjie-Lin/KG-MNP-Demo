import { AlertCircle, CloudOff, LoaderCircle, RefreshCw } from "lucide-react";
import { errorMessage, isApiError } from "../../api/errors";

export function RetryButton({ onRetry }: { onRetry: () => void }) {
  return <button type="button" onClick={onRetry} className="inline-flex items-center gap-1.5 rounded bg-blue-600 px-3 py-1.5 text-xs font-medium text-white hover:bg-blue-700"><RefreshCw size={12} />重试</button>;
}

export function ApiErrorState({ error, onRetry }: { error: unknown; onRetry: () => void }) {
  const fieldErrors = isApiError(error) ? error.fieldErrors : [];
  return <div role="alert" className="m-6 rounded border border-red-200 bg-red-50 p-5 text-sm text-red-800"><div className="mb-2 flex items-center gap-2 font-medium"><AlertCircle size={16} />{errorMessage(error)}</div>{fieldErrors.length > 0 && <ul className="mb-3 list-disc pl-5 text-xs">{fieldErrors.map((field) => <li key={field}>{field}</li>)}</ul>}<RetryButton onRetry={onRetry} /></div>;
}

export function OfflineBanner() {
  return <div role="status" className="flex items-center gap-2 border-b border-amber-200 bg-amber-50 px-4 py-2 text-xs text-amber-800"><CloudOff size={14} />后端服务暂时不可用，部分功能无法使用。</div>;
}

export function PageSkeleton() {
  return <div aria-label="加载中" className="space-y-4 p-6"><div className="h-8 w-48 animate-pulse rounded bg-slate-200" /><div className="grid grid-cols-2 gap-3 lg:grid-cols-4">{[1,2,3,4].map((item) => <div key={item} className="h-24 animate-pulse rounded bg-slate-100" />)}</div><div className="h-64 animate-pulse rounded bg-slate-100" /></div>;
}

export function EmptyState({ message = "暂无数据" }: { message?: string }) {
  return <div className="m-6 rounded border border-dashed border-slate-300 p-10 text-center text-sm text-slate-500">{message}</div>;
}

export function MutationStatus({ pending, error, success }: { pending: boolean; error?: unknown; success?: string }) {
  if (pending) return <div className="flex items-center gap-2 text-xs text-blue-700"><LoaderCircle className="animate-spin" size={13} />正在处理请求…</div>;
  if (error) return <div role="alert" className="text-xs text-red-700">{errorMessage(error)}</div>;
  return success ? <div className="text-xs text-emerald-700">{success}</div> : null;
}

export function FieldErrorSummary({ error }: { error: unknown }) {
  if (!isApiError(error) || !error.fieldErrors.length) return null;
  return <div role="alert" className="rounded border border-red-200 bg-red-50 p-3 text-xs text-red-700"><div className="mb-1 font-medium">请检查以下字段：</div>{error.fieldErrors.join("、")}</div>;
}
