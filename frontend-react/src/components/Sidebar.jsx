/**
 * Sidebar — fixed left rail.
 * Shows: brand, nav links, backend health status, resources.
 * On mobile collapses into a top bar via responsive classes.
 */
export default function Sidebar({ health, activeView, onNavigate }) {
  const navItems = [
    { id: "analyze", label: "Analyze", icon: IconSearch },
    { id: "samples", label: "Samples", icon: IconSparkles },
    { id: "about",   label: "About",   icon: IconInfo },
  ];

  return (
    <aside className="hidden lg:flex lg:w-64 lg:flex-col lg:fixed lg:inset-y-0 lg:z-40 bg-slate-950 text-slate-200 border-r border-slate-800">
      {/* ── Brand ── */}
      <div className="px-6 py-6 border-b border-slate-800">
        <div className="flex items-center gap-3">
          <div className="w-11 h-11 rounded-xl bg-gradient-to-br from-blue-500 to-violet-500 flex items-center justify-center text-xl shadow-lg shadow-blue-500/30">
            ⚖
          </div>
          <div>
            <h1 className="text-base font-extrabold text-white tracking-tight">Risk Mapper</h1>
            <p className="text-[11px] text-slate-400 font-medium">Hybrid AI v2</p>
          </div>
        </div>
      </div>

      {/* ── Navigation ── */}
      <nav className="flex-1 px-3 py-5 space-y-1">
        <p className="px-3 mb-2 text-[10px] font-bold uppercase tracking-wider text-slate-500">Workspace</p>
        {navItems.map((item) => {
          const Icon = item.icon;
          const active = activeView === item.id;
          return (
            <button
              key={item.id}
              onClick={() => onNavigate(item.id)}
              className={`w-full flex items-center gap-3 px-3 py-2.5 rounded-lg text-sm font-semibold transition-colors ${
                active
                  ? "bg-blue-600 text-white shadow-md shadow-blue-600/30"
                  : "text-slate-300 hover:bg-slate-800 hover:text-white"
              }`}
            >
              <Icon className="w-4 h-4" />
              {item.label}
            </button>
          );
        })}
      </nav>

      {/* ── Backend health ── */}
      <div className="px-4 py-4 border-t border-slate-800">
        <div className="rounded-lg bg-slate-900 border border-slate-800 p-3">
          <div className="flex items-center gap-2 mb-1.5">
            <span
              className={`w-2 h-2 rounded-full ${
                health.status === "ok"
                  ? "bg-emerald-400 shadow-[0_0_0_3px_rgba(52,211,153,.25)]"
                  : health.status === "err"
                  ? "bg-red-400 shadow-[0_0_0_3px_rgba(248,113,113,.25)]"
                  : "bg-slate-500"
              }`}
            />
            <span className="text-[11px] font-bold uppercase tracking-wider text-slate-400">
              {health.status === "ok" ? "Backend online" : health.status === "err" ? "Offline" : "Checking…"}
            </span>
          </div>
          {health.nlp_engine && (
            <p className="text-[11px] text-slate-500 leading-snug">
              {health.nlp_engine.split(" + ").map((l, i) => (
                <span key={i} className="block">• {l}</span>
              ))}
            </p>
          )}
        </div>
        <p className="text-[10px] text-slate-600 mt-3 leading-relaxed px-1">
          Not legal advice. Always consult a qualified attorney.
        </p>
      </div>
    </aside>
  );
}

/* ── Inline icons (no extra dependency) ── */
function IconSearch({ className }) {
  return (
    <svg className={className} viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2" strokeLinecap="round" strokeLinejoin="round">
      <circle cx="11" cy="11" r="8" /><line x1="21" y1="21" x2="16.65" y2="16.65" />
    </svg>
  );
}
function IconSparkles({ className }) {
  return (
    <svg className={className} viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2" strokeLinecap="round" strokeLinejoin="round">
      <path d="M12 3v4M12 17v4M3 12h4M17 12h4M5.6 5.6l2.8 2.8M15.6 15.6l2.8 2.8M5.6 18.4l2.8-2.8M15.6 8.4l2.8-2.8" />
    </svg>
  );
}
function IconInfo({ className }) {
  return (
    <svg className={className} viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2" strokeLinecap="round" strokeLinejoin="round">
      <circle cx="12" cy="12" r="10" /><line x1="12" y1="16" x2="12" y2="12" /><line x1="12" y1="8" x2="12.01" y2="8" />
    </svg>
  );
}
