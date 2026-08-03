import { MetricCard } from "../components/MetricCard";
import { SectionHeader } from "../components/SectionHeader";
import { cn } from "../utils/cn";
import { serviceStatusLabels, t } from "../i18n/zh-CN";

const SERVICES = [
  { name: "本体推理服务", status: "ONLINE", latency: "42 毫秒", uptime: "99.97%", checkedAt: "2026-07-01 09:12" },
  { name: "约束校验服务", status: "ONLINE", latency: "18 毫秒", uptime: "100%", checkedAt: "2026-07-01 09:12" },
  { name: "规则引擎", status: "ONLINE", latency: "67 毫秒", uptime: "99.94%", checkedAt: "2026-07-01 09:11" },
  { name: "图谱存储", status: "ONLINE", latency: "12 毫秒", uptime: "99.99%", checkedAt: "2026-07-01 09:12" },
  { name: "查询接口", status: "ONLINE", latency: "85 毫秒", uptime: "99.91%", checkedAt: "2026-07-01 09:10" },
  { name: "数据规范注册", status: "ONLINE", latency: "8 毫秒", uptime: "100%", checkedAt: "2026-07-01 09:12" },
  { name: "证据采集服务", status: "DEGRADED", latency: "340 毫秒", uptime: "98.12%", checkedAt: "2026-07-01 09:09" },
  { name: "审计日志服务", status: "ONLINE", latency: "22 毫秒", uptime: "99.88%", checkedAt: "2026-07-01 09:12" },
];

export function SystemStatus() {
  const online = SERVICES.filter((s) => s.status === "ONLINE").length;
  const degraded = SERVICES.filter((s) => s.status === "DEGRADED").length;

  return (
    <div className="p-6 space-y-5 min-w-0 overflow-x-hidden">
      <SectionHeader title="系统状态" sub="实时监控" />
      <div className="grid grid-cols-2 lg:grid-cols-4 gap-3">
        <MetricCard label="全部服务" value={SERVICES.length} sub="监控中" />
        <MetricCard label="运行正常" value={online} color="text-emerald-600" />
        <MetricCard label="性能降级" value={degraded} color="text-amber-600" />
        <MetricCard label="系统可用性" value="99.72%" sub="最近三十天" color="text-blue-700" />
      </div>
      <div className="bg-white border border-slate-200 rounded-lg overflow-x-auto">
        <table className="w-full text-xs min-w-[640px]">
          <thead>
            <tr className="border-b border-slate-200 bg-slate-50">
              {["服务名称", "状态", "响应延迟", "可用率", "最后检查"].map((h) => (
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
            {SERVICES.map((s, i) => (
              <tr
                key={s.name}
                className={cn("border-b border-slate-100", i % 2 === 0 ? "" : "bg-slate-50/50")}
              >
                <td className="px-4 py-3 text-slate-700">{s.name}</td>
                <td className="px-4 py-3">
                  <span
                    className={cn(
                      "inline-flex items-center gap-1 text-[10px] font-medium px-2 py-0.5 rounded",
                      s.status === "ONLINE"
                        ? "text-emerald-700 bg-emerald-50"
                        : "text-amber-700 bg-amber-50",
                    )}
                  >
                    <span
                      className={cn(
                        "w-1.5 h-1.5 rounded-full",
                        s.status === "ONLINE" ? "bg-emerald-500" : "bg-amber-500",
                      )}
                    />
                    {t(serviceStatusLabels, s.status)}
                  </span>
                </td>
                <td className="px-4 py-3 text-slate-600">{s.latency}</td>
                <td className="px-4 py-3 text-slate-600">{s.uptime}</td>
                <td className="px-4 py-3 text-slate-400">{s.checkedAt}</td>
              </tr>
            ))}
          </tbody>
        </table>
      </div>
    </div>
  );
}
