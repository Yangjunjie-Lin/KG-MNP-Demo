import { Activity, BookOpen, FlaskConical, FolderOpen, HelpCircle, LayoutDashboard, Menu, Network, Plus } from "lucide-react";
import { NavLink, useLocation } from "react-router";
import { ui } from "../i18n/zh-CN";
import { cn } from "../utils/cn";

const navItems = [
  { to: "/overview", label: ui.navOverview, icon: LayoutDashboard },
  { to: "/assessments/new", label: ui.navNewAssessment, icon: Plus },
  { to: "/cases", label: ui.navCaseHistory, icon: FolderOpen },
  { to: "/ontology", label: ui.navOntology, icon: Network },
  { to: "/competency-questions", label: ui.navCompetency, icon: HelpCircle },
  { to: "/rules", label: ui.navRules, icon: BookOpen },
  { to: "/what-if", label: ui.navWhatIf, icon: FlaskConical },
  { to: "/system", label: ui.navSystemStatus, icon: Activity },
];

export function Sidebar({ collapsed, onToggle }: { collapsed?: boolean; onToggle?: () => void }) {
  const location = useLocation();
  return <aside className={cn("flex h-full flex-shrink-0 flex-col border-r border-slate-800 bg-slate-900", collapsed ? "w-12" : "w-60")}>
    <button type="button" onClick={onToggle} className={cn("flex h-14 items-center text-slate-300 hover:bg-slate-800 hover:text-white", collapsed ? "justify-center" : "justify-start gap-2 px-4")} aria-label={collapsed ? "展开导航" : "折叠导航"}><Menu size={18} />{!collapsed && <span className="text-sm font-bold text-white">{ui.systemName}</span>}</button>
    <nav className="flex flex-1 flex-col gap-0.5 overflow-y-auto px-2 py-3">
      {navItems.map(({ to, label, icon: Icon }) => <NavLink key={to} to={to} className={({ isActive }) => { const assessmentDetailActive = to === "/cases" && /^\/assessments\/(?!new(?:\/|$))/.test(location.pathname); return cn("flex items-center rounded-md py-2 text-sm transition-colors", collapsed ? "justify-center px-2" : "gap-2.5 px-3", isActive || assessmentDetailActive ? "bg-blue-600 font-medium text-white" : "text-slate-400 hover:bg-slate-800 hover:text-slate-200"); }} title={collapsed ? label : undefined}><Icon size={15} className="flex-shrink-0" />{!collapsed && <span className="truncate">{label}</span>}</NavLink>)}
    </nav>
    {!collapsed && <div className="border-t border-slate-800 px-4 py-3 text-[10px] text-slate-500">{ui.prototypeFooter}</div>}
  </aside>;
}
