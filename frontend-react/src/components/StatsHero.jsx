/**
 * StatsHero — shown after analysis.
 * Big overall-risk badge + 4 stat cards (Total / High / Medium / Low).
 */
export default function StatsHero({ result }) {
  if (!result) return null;
  const { overall_risk, total_risks_found, risks } = result;
  const counts = { High: 0, Medium: 0, Low: 0 };
  risks.forEach((r) => { counts[r.severity] = (counts[r.severity] || 0) + 1; });

  const overallStyle =
    overall_risk === "High"
      ? "from-red-500 to-rose-600 shadow-red-500/30"
      : overall_risk === "Medium"
      ? "from-amber-500 to-orange-600 shadow-amber-500/30"
      : "from-emerald-500 to-teal-600 shadow-emerald-500/30";

  const stats = [
    { label: "Total Risks",   value: total_risks_found, tone: "slate" },
    { label: "High Severity", value: counts.High,       tone: "red" },
    { label: "Medium",        value: counts.Medium,     tone: "amber" },
    { label: "Low",           value: counts.Low,        tone: "emerald" },
  ];

  const toneClasses = {
    slate:   "bg-slate-50 border-slate-200 text-slate-900",
    red:     "bg-red-50 border-red-200 text-red-700",
    amber:   "bg-amber-50 border-amber-200 text-amber-700",
    emerald: "bg-emerald-50 border-emerald-200 text-emerald-700",
  };

  return (
    <div className="card p-6 lg:p-7 animate-fade-in">
      <div className="flex flex-col lg:flex-row lg:items-center gap-6">
        {/* ── Overall badge ── */}
        <div className="flex items-center gap-5">
          <div className={`w-24 h-24 rounded-2xl bg-gradient-to-br ${overallStyle} shadow-lg flex flex-col items-center justify-center text-white flex-shrink-0`}>
            <div className="text-[10px] font-bold uppercase tracking-wider opacity-90">Overall</div>
            <div className="text-2xl font-extrabold leading-none mt-1">{overall_risk}</div>
          </div>
          <div>
            <h2 className="text-lg font-extrabold text-slate-900 tracking-tight">Analysis Complete</h2>
            <p className="text-xs text-slate-500 mt-1 max-w-xs">
              {result.document_title || "Document"} analyzed across {risks.length} risk{risks.length === 1 ? "" : "s"}.
            </p>
          </div>
        </div>

        {/* ── Stat cards ── */}
        <div className="grid grid-cols-2 sm:grid-cols-4 gap-3 flex-1 lg:ml-auto lg:max-w-2xl">
          {stats.map((s) => (
            <div key={s.label} className={`rounded-xl border p-4 ${toneClasses[s.tone]}`}>
              <div className="text-[10px] font-bold uppercase tracking-wider opacity-70">{s.label}</div>
              <div className="text-3xl font-extrabold tabular-nums mt-1">{s.value}</div>
            </div>
          ))}
        </div>
      </div>
    </div>
  );
}
