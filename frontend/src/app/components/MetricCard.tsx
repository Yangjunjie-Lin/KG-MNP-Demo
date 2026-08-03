import { cn } from "../utils/cn";

export function MetricCard({
  label,
  value,
  sub,
  color,
}: {
  label: string;
  value: string | number;
  sub?: string;
  color?: string;
}) {
  return (
    <div className="bg-white border border-slate-200 rounded-lg p-4 flex flex-col gap-1 min-w-0">
      <div className="text-xs text-slate-500 font-medium tracking-wide">{label}</div>
      <div className={cn("text-2xl font-bold", color || "text-slate-800")}>{value}</div>
      {sub && <div className="text-xs text-slate-400">{sub}</div>}
    </div>
  );
}
