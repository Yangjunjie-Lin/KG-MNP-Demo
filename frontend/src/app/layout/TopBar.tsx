import { Menu, Play } from "lucide-react";
import { ui } from "../i18n/zh-CN";

export function TopBar({
  onRunDemo,
  onToggleSidebar,
}: {
  onRunDemo: () => void;
  onToggleSidebar?: () => void;
}) {
  return (
    <header className="min-h-12 bg-white border-b border-slate-200 flex items-center px-4 gap-3 flex-shrink-0 overflow-x-hidden">
      {onToggleSidebar && (
        <button
          type="button"
          onClick={onToggleSidebar}
          className="lg:hidden flex items-center justify-center w-8 h-8 rounded-md text-slate-500 hover:bg-slate-100 flex-shrink-0"
          aria-label="切换导航"
        >
          <Menu size={16} />
        </button>
      )}
      <div className="flex flex-wrap items-center gap-x-4 gap-y-1 text-xs text-slate-500 min-w-0 flex-1">
        <span>
          系统名称：
          <span className="text-slate-700 font-medium">{ui.systemName}</span>
        </span>
        <span className="hidden sm:inline text-slate-200">|</span>
        <span>
          后端服务：
          <span className="text-emerald-600 font-medium">{ui.backendOnline}</span>
        </span>
        <span>
          运行环境：
          <span className="text-blue-600 font-medium">{ui.envDemo}</span>
        </span>
        <span>
          接口版本：
          <span className="text-slate-700 font-medium">{ui.apiVersion}</span>
        </span>
        <span>
          数据规范：
          <span className="text-slate-700 font-medium">{ui.schemaVersion}</span>
        </span>
      </div>
      <button
        type="button"
        onClick={onRunDemo}
        className="flex items-center gap-1.5 bg-blue-600 hover:bg-blue-700 text-white text-xs px-3 py-1.5 rounded-md font-medium transition-colors flex-shrink-0"
      >
        <Play size={11} /> {ui.runDemo}
      </button>
    </header>
  );
}
