export function SectionHeader({ title, sub }: { title: string; sub?: string }) {
  return (
    <div className="flex items-baseline gap-3 mb-4 min-w-0">
      <h2 className="text-sm font-semibold text-slate-700 tracking-wider">{title}</h2>
      {sub && <span className="text-xs text-slate-400 truncate">{sub}</span>}
    </div>
  );
}
