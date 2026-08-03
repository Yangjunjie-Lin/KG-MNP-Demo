import { useEffect, useState, type ReactNode } from "react";
import { Sidebar } from "./Sidebar";
import { TopBar } from "./TopBar";
import type { PageId } from "../types/common";

const ZH_FONT =
  '"Microsoft YaHei", "PingFang SC", "Noto Sans SC", system-ui, sans-serif';

export function AppLayout({
  current,
  onNavigate,
  onRunDemo,
  children,
}: {
  current: PageId;
  onNavigate: (p: PageId) => void;
  onRunDemo: () => void;
  children: ReactNode;
}) {
  const [collapsed, setCollapsed] = useState(false);

  useEffect(() => {
    const sync = () => {
      if (window.innerWidth < 1024) {
        setCollapsed(true);
      } else {
        setCollapsed(false);
      }
    };
    sync();
    window.addEventListener("resize", sync);
    return () => window.removeEventListener("resize", sync);
  }, []);

  return (
    <div
      className="h-screen w-screen flex flex-col overflow-hidden overflow-x-hidden bg-slate-100"
      style={{ fontFamily: ZH_FONT }}
    >
      <TopBar
        onRunDemo={onRunDemo}
        onToggleSidebar={() => setCollapsed((c) => !c)}
      />
      <div className="flex flex-1 overflow-hidden min-w-0">
        <Sidebar
          current={current}
          onNavigate={onNavigate}
          collapsed={collapsed}
          onToggle={() => setCollapsed((c) => !c)}
        />
        <main className="flex-1 overflow-hidden flex flex-col bg-slate-50 min-w-0 overflow-x-hidden">
          {children}
        </main>
      </div>
    </div>
  );
}
