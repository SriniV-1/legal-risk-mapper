/**
 * RiskGroup — collapsible category section wrapping a list of RiskCards.
 */
import { useState } from "react";
import RiskCard from "./RiskCard.jsx";

export default function RiskGroup({ category, risks, defaultOpen = true }) {
  const [open, setOpen] = useState(defaultOpen);
  const highCount = risks.filter((r) => r.severity === "High").length;

  return (
    <div className="animate-fade-in">
      <button
        onClick={() => setOpen(!open)}
        className="w-full flex items-center justify-between px-4 py-3 rounded-xl bg-slate-50 border border-slate-200 hover:bg-white hover:border-slate-300 transition-all mb-3"
      >
        <div className="flex items-center gap-3">
          <span className={`inline-block transition-transform ${open ? "rotate-90" : ""}`}>▸</span>
          <span className="text-sm font-bold text-slate-900">{category}</span>
          <span className="px-2 py-0.5 rounded bg-slate-200 text-[10px] font-bold text-slate-700 tabular-nums">
            {risks.length}
          </span>
          {highCount > 0 && (
            <span className="px-2 py-0.5 rounded bg-red-100 text-[10px] font-bold text-red-700 tabular-nums">
              {highCount} HIGH
            </span>
          )}
        </div>
      </button>
      {open && (
        <div className="space-y-3 pl-2">
          {risks.map((r, i) => <RiskCard key={i} risk={r} />)}
        </div>
      )}
    </div>
  );
}
