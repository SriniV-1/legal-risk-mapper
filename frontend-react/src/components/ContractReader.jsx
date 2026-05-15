import { useState } from "react";

function ShieldIcon() {
  return (
    <svg width="15" height="15" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2" strokeLinecap="round" strokeLinejoin="round">
      <path d="M12 22s8-4 8-10V5l-8-3-8 3v7c0 6 8 10 8 10z"/>
    </svg>
  );
}

function FileTextIcon() {
  return (
    <svg width="15" height="15" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2" strokeLinecap="round" strokeLinejoin="round">
      <path d="M14 2H6a2 2 0 0 0-2 2v16a2 2 0 0 0 2 2h12a2 2 0 0 0 2-2V8z"/>
      <polyline points="14 2 14 8 20 8"/>
      <line x1="16" y1="13" x2="8" y2="13"/>
      <line x1="16" y1="17" x2="8" y2="17"/>
      <polyline points="10 9 9 9 8 9"/>
    </svg>
  );
}

function DownloadIcon() {
  return (
    <svg width="12" height="12" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2" strokeLinecap="round" strokeLinejoin="round">
      <path d="M21 15v4a2 2 0 0 1-2 2H5a2 2 0 0 1-2-2v-4"/>
      <polyline points="7 10 12 15 17 10"/>
      <line x1="12" y1="15" x2="12" y2="3"/>
    </svg>
  );
}

/** Match a risk to a paragraph index via substring search on text_snippet */
function findParaIndex(paragraphs, snippet) {
  if (!snippet) return -1;
  // Use first 60 chars of snippet for matching (handles truncation)
  const needle = snippet.slice(0, 60).toLowerCase().trim();
  if (!needle) return -1;
  for (let i = 0; i < paragraphs.length; i++) {
    if (paragraphs[i].toLowerCase().includes(needle)) return i;
  }
  // Fallback: try shorter prefix
  const short = needle.slice(0, 30);
  if (short.length >= 10) {
    for (let i = 0; i < paragraphs.length; i++) {
      if (paragraphs[i].toLowerCase().includes(short)) return i;
    }
  }
  return -1;
}

function InlineRisk({ risk, onClose }) {
  const sev = risk.severity || "Low";
  const sevLower = sev.toLowerCase();
  const sources = new Set(risk.sources || []);
  const confirmed = sources.has("regex") && sources.has("semantic");
  const conf = Math.min(100, Math.round(risk.score || 0));

  return (
    <div className={`cr-expanded-risk ${sevLower}`}>
      <div className={`cr-exp-header ${sevLower}`}>
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
        <button
          style={{ marginLeft: "auto", background: "none", border: "none", cursor: "pointer", color: "var(--text-3)", lineHeight: 1, padding: "2px" }}
          onClick={onClose}
        >
          <svg width="13" height="13" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2" strokeLinecap="round" strokeLinejoin="round">
            <line x1="18" y1="6" x2="6" y2="18"/><line x1="6" y1="6" x2="18" y2="18"/>
          </svg>
        </button>
      </div>
      <div className="cr-exp-body">
        {risk.text_snippet && (
          <div className="cr-exp-snippet">"{risk.text_snippet}"</div>
        )}
        {risk.explanation && (
          <div className="cr-exp-explanation">{risk.explanation}</div>
        )}
        <div className="cr-exp-conf">
          <span>Confidence</span>
          <div className="cr-exp-conf-track">
            <div className="cr-exp-conf-fill" style={{ width: `${conf}%` }} />
          </div>
          <span style={{ fontWeight: 500 }}>{conf}%</span>
        </div>
      </div>
    </div>
  );
}

export default function ContractReader({ contractText, data, sevFilter, onFilterChange }) {
  const [expandedKey, setExpandedKey] = useState(null); // "paraIdx-riskIdx"

  const lvl = (data.overall_risk_level || "none").toLowerCase();
  const total = data.total_risks || 0;
  const high = data.severity_breakdown?.High || 0;
  const med = data.severity_breakdown?.Medium || 0;
  const low = data.severity_breakdown?.Low || 0;
  const risks = data.risks || [];

  // Split text into non-empty paragraphs
  const paragraphs = (contractText || "")
    .split(/\n+/)
    .map((p) => p.trim())
    .filter((p) => p.length > 0);

  // Map each risk to a paragraph index (or -1 = unmatched)
  const riskParaMap = risks.map((r) => findParaIndex(paragraphs, r.text_snippet));

  // Build per-paragraph risk index lists
  const paraRisks = Array.from({ length: paragraphs.length }, () => []);
  const unmatchedRisks = [];
  risks.forEach((r, rIdx) => {
    const pIdx = riskParaMap[rIdx];
    if (pIdx >= 0) {
      paraRisks[pIdx].push(rIdx);
    } else {
      unmatchedRisks.push(rIdx);
    }
  });

  // Severity ordering for filtering
  const sevOrder = { High: 0, Medium: 1, Low: 2 };

  function isVisible(rIdx) {
    if (sevFilter === "all") return true;
    return risks[rIdx]?.severity === sevFilter;
  }

  function toggleRisk(paraIdx, riskIdx) {
    const key = `${paraIdx}-${riskIdx}`;
    setExpandedKey(expandedKey === key ? null : key);
  }

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
    <div className="cr-wrap">
      {/* ── SUMMARY CARD ── */}
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
      </div>

      {/* ── CONTRACT BODY ── */}
      <div className="cr-body">
        <div className="cr-body-header">
          <FileTextIcon />
          <span className="cr-body-title">Contract Text</span>
          <div className="cr-filter-row">
            {["all", "High", "Medium", "Low"].map((f) => {
              const activeClass = sevFilter === f ? ` active-${f.toLowerCase()}` : "";
              return (
                <button
                  key={f}
                  className={`filter-chip${activeClass}`}
                  onClick={() => { onFilterChange(f); setExpandedKey(null); }}
                >
                  {f === "all" ? "All" : f}
                </button>
              );
            })}
          </div>
        </div>

        {paragraphs.length === 0 ? (
          <div className="empty-state" style={{ padding: "32px 24px" }}>
            No contract text available.
          </div>
        ) : (
          <div className="cr-paragraphs">
            {paragraphs.map((para, pIdx) => {
              const visibleRiskIdxs = paraRisks[pIdx].filter(isVisible);
              const hasRisk = visibleRiskIdxs.length > 0;

              const activeRiskIdx = visibleRiskIdxs
                .map(rIdx => ({ rIdx, key: `${pIdx}-${rIdx}` }))
                .find(x => x.key === expandedKey)?.rIdx;
              const highlightSev = activeRiskIdx != null
                ? (risks[activeRiskIdx].severity || "Low").toLowerCase()
                : null;
              const paraStyle = highlightSev
                ? {
                    borderLeft: `3px solid var(--${highlightSev})`,
                    background: highlightSev === "high"
                      ? "rgba(239,68,68,0.08)"
                      : highlightSev === "medium"
                        ? "rgba(245,158,11,0.08)"
                        : "rgba(34,197,94,0.08)",
                    transition: "background 0.2s ease, border-color 0.2s ease",
                  }
                : { transition: "background 0.2s ease, border-color 0.2s ease" };

              return (
                <div key={pIdx} className="cr-para-block" style={paraStyle}>
                  {/* Left margin — dots */}
                  <div className="cr-margin">
                    {visibleRiskIdxs
                      .sort((a, b) => sevOrder[risks[a].severity] - sevOrder[risks[b].severity])
                      .map((rIdx) => {
                        const sev = (risks[rIdx].severity || "Low").toLowerCase();
                        const key = `${pIdx}-${rIdx}`;
                        return (
                          <div
                            key={rIdx}
                            className={`cr-dot ${sev}${expandedKey === key ? " active" : ""}`}
                            title={`${risks[rIdx].severity} — ${risks[rIdx].risk_type}`}
                            onClick={() => toggleRisk(pIdx, rIdx)}
                          />
                        );
                      })}
                  </div>

                  {/* Right: paragraph text + expanded panels */}
                  <div className="cr-para-right">
                    <div className={`cr-para-text${hasRisk ? " has-risk" : ""}`}>
                      {para}
                    </div>

                    {/* Expanded risk panels for this paragraph */}
                    {visibleRiskIdxs.map((rIdx) => {
                      const key = `${pIdx}-${rIdx}`;
                      if (expandedKey !== key) return null;
                      return (
                        <div key={rIdx} className="cr-expanded">
                          <InlineRisk
                            risk={risks[rIdx]}
                            onClose={() => setExpandedKey(null)}
                          />
                        </div>
                      );
                    })}
                  </div>
                </div>
              );
            })}

            {/* ── Fallback: unmatched risks ── */}
            {unmatchedRisks.filter(isVisible).length > 0 && (
              <div className="cr-fallback">
                <div className="cr-fallback-header">
                  Additional Risks — location not pinpointed in text
                </div>
                <div className="cr-expanded">
                  {unmatchedRisks.filter(isVisible).map((rIdx) => {
                    const key = `fallback-${rIdx}`;
                    return (
                      <InlineRisk
                        key={rIdx}
                        risk={risks[rIdx]}
                        onClose={() => {}}
                      />
                    );
                  })}
                </div>
              </div>
            )}
          </div>
        )}
      </div>
    </div>
  );
}
