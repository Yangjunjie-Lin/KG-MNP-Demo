import {
  LayoutDashboard,
  Plus,
  FolderOpen,
  Network,
  HelpCircle,
  BookOpen,
  FlaskConical,
  Activity,
  Menu,
} from "lucide-react";
import { cn } from "../utils/cn";
import { ui } from "../i18n/zh-CN";
import type { PageId } from "../types/common";

const NAV_ITEMS: Array<{ id: PageId; label: string; icon: typeof LayoutDashboard }> = [
  { id: "overview", label: ui.navOverview, icon: LayoutDashboard },
  { id: "new-assessment", label: ui.navNewAssessment, icon: Plus },
  { id: "case-history", label: ui.navCaseHistory, icon: FolderOpen },
  { id: "ontology", label: ui.navOntology, icon: Network },
  { id: "competency", label: ui.navCompetency, icon: HelpCircle },
  { id: "rules", label: ui.navRules, icon: BookOpen },
  { id: "whatif", label: ui.navWhatIf, icon: FlaskConical },
  { id: "system-status", label: ui.navSystemStatus, icon: Activity },
];

export function Sidebar({
  current,
  onNavigate,
  collapsed,
  onToggle,
}: {
  current: PageId;
  onNavigate: (p: PageId) => void;
  collapsed?: boolean;
  onToggle?: () => void;
}) {
  if (collapsed) {
    return (
      <aside className="w-12 flex-shrink-0 bg-slate-900 flex flex-col h-full border-r border-slate-800">
        <button
          type="button"
          onClick={onToggle}
          className="h-14 flex items-center justify-center text-slate-300 hover:text-white hover:bg-slate-800 transition-colors"
          aria-label="展开导航"
        >
          <Menu size={18} />
        </button>
        <nav className="flex-1 px-1.5 py-2 flex flex-col gap-0.5 overflow-y-auto">
          {NAV_ITEMS.map((item) => {
            const Icon = item.icon;
            const active =
              current === item.id || (current === "result" && item.id === "case-history");
            return (
              <button
                key={item.id}
                type="button"
                title={item.label}
                onClick={() => onNavigate(item.id)}
                className={cn(
                  "flex items-center justify-center p-2.5 rounded-md transition-colors",
                  active
                    ? "bg-blue-600 text-white"
                    : "text-slate-400 hover:text-slate-200 hover:bg-slate-800",
                )}
              >
                <Icon size={15} />
              </button>
            );
          })}
        </nav>
      </aside>
    );
  }

  return (
    <aside className="w-60 flex-shrink-0 bg-slate-900 flex flex-col h-full border-r border-slate-800 min-w-0">
      <div className="px-4 py-4 border-b border-slate-800">
        <div className="flex items-start gap-2.5">
          <div className="w-8 h-8 rounded-md bg-blue-600 flex items-center justify-center flex-shrink-0 mt-0.5">
            <Network size={15} className="text-white" />
          </div>
          <div className="min-w-0 flex-1">
            <div className="text-[13px] font-bold text-white leading-snug break-words">
              {ui.systemName}
            </div>
          </div>
          {onToggle && (
            <button
              type="button"
              onClick={onToggle}
              className="lg:hidden text-slate-400 hover:text-white p-1 flex-shrink-0"
              aria-label="折叠导航"
            >
              <Menu size={16} />
            </button>
          )}
        </div>
      </div>
      <nav className="flex-1 px-2 py-3 flex flex-col gap-0.5 overflow-y-auto">
        {NAV_ITEMS.map((item) => {
          const Icon = item.icon;
          const active =
            current === item.id || (current === "result" && item.id === "case-history");
          return (
            <button
              key={item.id}
              type="button"
              onClick={() => onNavigate(item.id)}
              className={cn(
                "flex items-center gap-2.5 px-3 py-2 rounded-md text-sm transition-colors w-full text-left min-w-0",
                active
                  ? "bg-blue-600 text-white font-medium"
                  : "text-slate-400 hover:text-slate-200 hover:bg-slate-800",
              )}
            >
              <Icon size={15} className="flex-shrink-0" />
              <span className="truncate">{item.label}</span>
            </button>
          );
        })}
      </nav>
      <div className="px-4 py-3 border-t border-slate-800">
        <div className="text-[10px] text-slate-500">{ui.prototypeFooter}</div>
      </div>
    </aside>
  );
}
