import { useState } from "react";

export default function RiskCard({ risk }) {
  const [expanded, setExpanded] = useState(false);
  const sev = risk.severity;
  const sevStyles = {
    High:   { border: "border-l-red-500",     bg: "bg-gradient-to-r from-red-50/60 to-white",     badge: "bg-red-100 text-red-700" },
    Medium: { border: "border-l-amber-500",   bg: "bg-gradient-to-r from-amber-50/60 to-white",   badge: "bg-amber-100 text-amber-700" },
    Low:    { border: "border-l-emerald-500", bg: "bg-gradient-to-r from-emerald-50/50 to-white", badge: "bg-emerald-100 text-emerald-700" },
  }[sev] || { border: "border-l-slate-400", bg: "bg-white", badge: "bg-slate-100 text-slate-700" };

  const sources = risk.sources || ["regex"];
  const sourceBadges = [];
  if (sources.includes("regex") && sources.includes("semantic")) {
    sourceBadges.push({ label: "CONFIRMED", cls: "bg-blue-600 text-white" });
  } else if (sources.includes("semantic")) {
    sourceBadges.push({ label: "SEMANTIC", cls: "bg-violet-600 text-white" });
  } else {
    sourceBadges.push({ label: "PATTERN", cls: "bg-indigo-600 text-white" });
  }

  const confidencePct = Math.min(100, Math.round(risk.score));
  const simPct = risk.semantic_similarity != null ? Math.round(risk.semantic_similarity * 100) : null;

  return (
    <div className={`rounded-xl border border-slate-200 border-l-[5px] ${sevStyles.border} ${sevStyles.bg} p-5 hover:shadow-md transition-shadow animate-fade-in`}>
      {/* ── Header row ── */}
      <div className="flex items-start justify-between gap-3 mb-3">
        <div className="flex items-center gap-2 flex-wrap">
          <span className={`px-2.5 py-1 rounded-md text-[10px] font-extrabold uppercase tracking-wider ${sevStyles.badge}`}>
            {sev}
          </span>
          <span className="text-[13px] font-bold text-slate-900">{risk.risk_type}</span>
          {sourceBadges.map((b) => (
            <span key={b.label} className={`px-2 py-0.5 rounded text-[9px] font-extrabold tracking-wider ${b.cls}`}>
              {b.label}
            </span>
          ))}
        </div>
        <span className="text-[11px] text-slate-400 tabular-nums font-mono">#{(risk.clause_index ?? 0) + 1}</span>
      </div>

      {/* ── Snippet ── */}
      <blockquote className="text-[13px] text-slate-700 leading-relaxed font-mono bg-white/70 border-l-2 border-slate-300 pl-3 py-2 rounded-sm mb-2">
        "{risk.text_snippet}"
      </blockquote>

      {/* ── Expand toggle ── */}
      <button
        onClick={() => setExpanded(!expanded)}
        className="text-[11px] font-semibold text-blue-600 hover:text-blue-800 mb-2 flex items-center gap-1"
      >
        <span className={`inline-block transition-transform ${expanded ? "rotate-90" : ""}`}>&#9656;</span>
        {expanded ? "Hide reasoning" : "Show reasoning"}
      </button>

      {expanded && (
        <>
          {/* ── Explanation ── */}
          <p className="text-sm text-slate-700 leading-relaxed mb-4">{risk.explanation}</p>

          {/* ── Metrics ── */}
          <div className="grid grid-cols-1 sm:grid-cols-2 gap-3 mb-3">
            <Metric label="Risk score" value={`${confidencePct}/100`} pct={confidencePct} color={confidencePct >= 70 ? "bg-red-500" : confidencePct >= 40 ? "bg-amber-500" : "bg-emerald-500"} />
            {simPct != null && (
              <Metric label="Semantic match" value={`${simPct}%`} pct={simPct} color="bg-violet-600" />
            )}
          </div>

          {/* ── Keywords ── */}
          {risk.keywords_matched?.length > 0 && (
            <div className="flex flex-wrap gap-1.5 pt-3 border-t border-slate-200/70">
              {risk.keywords_matched.slice(0, 8).map((k, i) => (
                <span key={i} className="px-2 py-0.5 rounded bg-slate-100 border border-slate-200 text-[11px] font-mono text-slate-600">
                  {k}
                </span>
              ))}
            </div>
          )}
        </>
      )}
    </div>
  );
}

function Metric({ label, value, pct, color }) {
  return (
    <div>
      <div className="flex justify-between text-[10px] font-bold uppercase tracking-wider text-slate-500 mb-1">
        <span>{label}</span>
        <span className="tabular-nums text-slate-700">{value}</span>
      </div>
      <div className="h-1.5 bg-slate-200 rounded-full overflow-hidden">
        <div className={`h-full ${color} rounded-full transition-all`} style={{ width: `${pct}%` }} />
      </div>
    </div>
  );
}
