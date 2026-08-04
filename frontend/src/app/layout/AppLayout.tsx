import { useEffect, useState, type ReactNode } from "react";
import { useSystemStatus } from "../query/hooks/useAppQueries";
import { OfflineBanner } from "../components/dataStates";
import { Sidebar } from "./Sidebar";
import { TopBar } from "./TopBar";

const zhFont = '"Microsoft YaHei", "PingFang SC", "Noto Sans SC", system-ui, sans-serif';

export function AppLayout({ children }: { children: ReactNode }) {
  const [collapsed, setCollapsed] = useState(false);
  const system = useSystemStatus();
  useEffect(() => {
    const sync = () => setCollapsed(window.innerWidth < 1024);
    sync(); window.addEventListener("resize", sync); return () => window.removeEventListener("resize", sync);
  }, []);
  return <div className="flex h-screen w-screen flex-col overflow-hidden bg-slate-100" style={{ fontFamily: zhFont }}>
    <TopBar onToggleSidebar={() => setCollapsed((value) => !value)} />
    {system.isError && <OfflineBanner />}
    <div className="flex min-w-0 flex-1 overflow-hidden"><Sidebar collapsed={collapsed} onToggle={() => setCollapsed((value) => !value)} /><main className="flex min-w-0 flex-1 flex-col overflow-hidden bg-slate-50">{children}</main></div>
  </div>;
}
