/**
 * FilterBar — severity + source filters and view-mode toggle.
 */
export default function FilterBar({ filters, onChange, viewMode, onViewChange, total, shown }) {
  const sevOptions = [
    { id: "all",    label: "All" },
    { id: "High",   label: "High" },
    { id: "Medium", label: "Medium" },
    { id: "Low",    label: "Low" },
  ];
  const srcOptions = [
    { id: "all",      label: "All sources" },
    { id: "regex",    label: "Pattern" },
    { id: "semantic", label: "Semantic" },
    { id: "both",     label: "Confirmed" },
  ];

  const pill = (active) =>
    `px-3 py-1.5 rounded-lg text-xs font-semibold transition-all ${
      active
        ? "bg-blue-600 text-white shadow-sm"
        : "bg-white text-slate-600 border border-slate-200 hover:border-blue-400 hover:text-blue-600"
    }`;

  return (
    <div className="card p-4 flex flex-wrap items-center gap-4 animate-fade-in">
      <div className="flex items-center gap-2">
        <span className="text-[11px] font-bold uppercase tracking-wider text-slate-500">Severity</span>
        <div className="flex gap-1.5">
          {sevOptions.map((o) => (
            <button key={o.id} onClick={() => onChange({ ...filters, severity: o.id })} className={pill(filters.severity === o.id)}>
              {o.label}
            </button>
          ))}
        </div>
      </div>

      <div className="flex items-center gap-2">
        <span className="text-[11px] font-bold uppercase tracking-wider text-slate-500">Source</span>
        <div className="flex gap-1.5">
          {srcOptions.map((o) => (
            <button key={o.id} onClick={() => onChange({ ...filters, source: o.id })} className={pill(filters.source === o.id)}>
              {o.label}
            </button>
          ))}
        </div>
      </div>

      <div className="ml-auto flex items-center gap-3">
        <span className="text-xs text-slate-500 tabular-nums">
          Showing <span className="font-bold text-slate-900">{shown}</span> of {total}
        </span>
        <div className="flex gap-1 p-1 bg-slate-100 rounded-lg border border-slate-200">
          <button
            onClick={() => onViewChange("grouped")}
            className={`px-3 py-1 rounded-md text-xs font-semibold transition-all ${viewMode === "grouped" ? "bg-white text-blue-600 shadow-sm" : "text-slate-500"}`}
          >
            Grouped
          </button>
          <button
            onClick={() => onViewChange("flat")}
            className={`px-3 py-1 rounded-md text-xs font-semibold transition-all ${viewMode === "flat" ? "bg-white text-blue-600 shadow-sm" : "text-slate-500"}`}
          >
            Flat
          </button>
        </div>
      </div>
    </div>
  );
}
