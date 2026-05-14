function DownloadIcon() {
  return (
    <svg width="12" height="12" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2" strokeLinecap="round" strokeLinejoin="round">
      <path d="M21 15v4a2 2 0 0 1-2 2H5a2 2 0 0 1-2-2v-4"/>
      <polyline points="7 10 12 15 17 10"/>
      <line x1="12" y1="15" x2="12" y2="3"/>
    </svg>
  );
}

function ShieldIcon() {
  return (
    <svg width="15" height="15" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2" strokeLinecap="round" strokeLinejoin="round">
      <path d="M12 22s8-4 8-10V5l-8-3-8 3v7c0 6 8 10 8 10z"/>
    </svg>
  );
}

function RiskCard({ risk }) {
  const sev = risk.severity || "Low";
  const sources = new Set(risk.sources || []);
  const confirmed = sources.has("regex") && sources.has("semantic");
  const conf = Math.min(100, Math.round(risk.score || 0));

  return (
    <div className={`risk-card ${sev}`}>
      <div className="risk-card-header">
        <span className={`sev-badge ${sev}`}>{sev}</span>
        <span className="risk-type">{risk.risk_type}</span>
        <div className="src-chips">
          {confirmed ? (
            <span className="src-chip confirmed">Confirmed</span>
          ) : (
            <>
              {sources.has("regex")    && <span className="src-chip">Pattern</span>}
              {sources.has("semantic") && <span className="src-chip">Semantic</span>}
            </>
          )}
        </div>
      </div>
      <div className="risk-card-body">
        {risk.text_snippet && (
          <div className="risk-snippet">"{risk.text_snippet}"</div>
        )}
        {risk.explanation && (
          <div className="risk-explanation">{risk.explanation}</div>
        )}
        <div className="confidence-row">
          <span className="conf-label">Confidence</span>
          <div className="conf-track">
            <div className="conf-fill" style={{ width: `${conf}%` }} />
          </div>
          <span className="conf-pct">{conf}%</span>
        </div>
      </div>
    </div>
  );
}

export default function RiskResults({ data, sevFilter, onFilterChange }) {
  const lvl = (data.overall_risk_level || "none").toLowerCase();
  const total = data.total_risks || 0;
  const high = data.severity_breakdown?.High || 0;
  const med = data.severity_breakdown?.Medium || 0;
  const low = data.severity_breakdown?.Low || 0;

  const risks = data.risks || [];
  const filtered = sevFilter === "all"
    ? risks
    : risks.filter((r) => r.severity === sevFilter);

  function exportJson() {
    const blob = new Blob([JSON.stringify(data, null, 2)], { type: "application/json" });
    const a = Object.assign(document.createElement("a"), {
      href: URL.createObjectURL(blob),
      download: "legal_risk_analysis.json",
    });
    a.click();
    URL.revokeObjectURL(a.href);
  }

  return (
    <div className="card">
      <div className="card-header">
        <ShieldIcon />
        <span className="card-title">Risk Analysis</span>
        <div className="card-header-spacer" />
        <button className="btn-export" onClick={exportJson}>
          <DownloadIcon />
          Export JSON
        </button>
      </div>

      <div className="overall-row">
        <span className={`risk-level-badge ${lvl}`}>{lvl.toUpperCase()}</span>
        <span className="risk-subtitle">{total} risk{total !== 1 ? "s" : ""} detected</span>
      </div>

      <div className="stats-row">
        <div className="stat-chip">
          <span className="stat-chip-num">{total}</span>
          <span>Total</span>
        </div>
        <div className="stat-chip">
          <span className={`stat-chip-num ${high > 0 ? "high" : ""}`}>{high}</span>
          <span>High</span>
        </div>
        <div className="stat-chip">
          <span className={`stat-chip-num ${med > 0 ? "med" : ""}`}>{med}</span>
          <span>Medium</span>
        </div>
        <div className="stat-chip">
          <span className={`stat-chip-num ${low > 0 ? "low" : ""}`}>{low}</span>
          <span>Low</span>
        </div>
      </div>

      {data.analysis_notes && (
        <div className="notes-section">{data.analysis_notes}</div>
      )}

      <div className="filter-row">
        {["all", "High", "Medium", "Low"].map((f) => (
          <button
            key={f}
            className={`filter-chip${sevFilter === f ? " active" : ""}`}
            onClick={() => onFilterChange(f)}
          >
            {f === "all" ? "All" : f}
          </button>
        ))}
      </div>

      <div className="risk-list">
        {filtered.length === 0 ? (
          <div className="empty-state">No risks match the selected filter.</div>
        ) : (
          filtered.map((r, i) => <RiskCard key={i} risk={r} />)
        )}
      </div>
    </div>
  );
}
