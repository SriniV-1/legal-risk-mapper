/**
 * App — top-level layout.
 * Left rail (Sidebar) + main column with UploadPanel, hero, charts, filter bar, risks.
 */
import { useEffect, useMemo, useState } from "react";
import Sidebar from "./components/Sidebar.jsx";
import UploadPanel from "./components/UploadPanel.jsx";
import StatsHero from "./components/StatsHero.jsx";
import ChartsRow from "./components/ChartsRow.jsx";
import FilterBar from "./components/FilterBar.jsx";
import RiskCard from "./components/RiskCard.jsx";
import RiskGroup from "./components/RiskGroup.jsx";
import LoadingOverlay from "./components/LoadingOverlay.jsx";
import { getHealth, analyzeText, analyzeFile } from "./api.js";

export default function App() {
  const [health, setHealth] = useState({ status: "checking" });
  const [activeView, setActiveView] = useState("analyze");
  const [result, setResult] = useState(null);
  const [isAnalyzing, setIsAnalyzing] = useState(false);
  const [error, setError] = useState(null);
  const [filters, setFilters] = useState({ severity: "all", source: "all" });
  const [viewMode, setViewMode] = useState("grouped");

  // ── Initial health check ──
  useEffect(() => {
    getHealth()
      .then((h) => setHealth({ status: "ok", ...h }))
      .catch(() => setHealth({ status: "err" }));
  }, []);

  // ── Run analysis ──
  const handleAnalyze = async ({ mode, text, file, title }) => {
    setError(null);
    setIsAnalyzing(true);
    try {
      const data = mode === "file"
        ? await analyzeFile(file, title)
        : await analyzeText({ text, document_title: title });
      setResult(data);
    } catch (e) {
      setError(e.message || "Analysis failed");
      setResult(null);
    } finally {
      setIsAnalyzing(false);
    }
  };

  // ── Filter risks ──
  const filteredRisks = useMemo(() => {
    if (!result?.risks) return [];
    return result.risks.filter((r) => {
      if (filters.severity !== "all" && r.severity !== filters.severity) return false;
      if (filters.source !== "all") {
        const srcs = r.sources || ["regex"];
        const hasBoth = srcs.includes("regex") && srcs.includes("semantic");
        if (filters.source === "both" && !hasBoth) return false;
        if (filters.source === "regex" && (hasBoth || !srcs.includes("regex"))) return false;
        if (filters.source === "semantic" && (hasBoth || !srcs.includes("semantic"))) return false;
      }
      return true;
    });
  }, [result, filters]);

  // ── Group by category ──
  const grouped = useMemo(() => {
    const out = {};
    filteredRisks.forEach((r) => {
      (out[r.risk_type] ||= []).push(r);
    });
    return out;
  }, [filteredRisks]);

  return (
    <div className="min-h-screen bg-slate-50">
      <Sidebar health={health} activeView={activeView} onNavigate={setActiveView} />

      <main className="lg:pl-64">
        <div className="max-w-6xl mx-auto px-5 lg:px-8 py-6 lg:py-10 space-y-6">
          {/* ── Page header ── */}
          <header className="flex items-end justify-between flex-wrap gap-3">
            <div>
              <h1 className="text-2xl lg:text-3xl font-extrabold text-slate-900 tracking-tight">Legal Risk Analysis</h1>
              <p className="text-sm text-slate-500 mt-1">Hybrid pattern-matching + semantic AI — fully local</p>
            </div>
            {result && (
              <button
                onClick={() => { setResult(null); setError(null); }}
                className="text-xs font-semibold text-slate-500 hover:text-blue-600 transition-colors"
              >
                ← New analysis
              </button>
            )}
          </header>

          {/* ── Upload panel ── */}
          <UploadPanel onAnalyze={handleAnalyze} isAnalyzing={isAnalyzing} error={error} />

          {/* ── Results ── */}
          {result && (
            <>
              <StatsHero result={result} />
              <ChartsRow risks={result.risks} />
              <FilterBar
                filters={filters}
                onChange={setFilters}
                viewMode={viewMode}
                onViewChange={setViewMode}
                total={result.risks.length}
                shown={filteredRisks.length}
              />

              {filteredRisks.length === 0 ? (
                <div className="card p-10 text-center text-sm text-slate-500">
                  No risks match the current filters.
                </div>
              ) : viewMode === "grouped" ? (
                <div className="space-y-5">
                  {Object.entries(grouped).map(([cat, items]) => (
                    <RiskGroup key={cat} category={cat} risks={items} />
                  ))}
                </div>
              ) : (
                <div className="space-y-3">
                  {filteredRisks.map((r, i) => <RiskCard key={i} risk={r} />)}
                </div>
              )}

              {/* ── Disclaimer ── */}
              <div className="card p-5 bg-amber-50 border-amber-200">
                <p className="text-xs text-amber-800 leading-relaxed">
                  <strong>Disclaimer:</strong> This tool provides automated risk detection for educational purposes only.
                  It is not a substitute for legal review. Always consult a qualified attorney before signing contracts
                  or relying on the findings above.
                </p>
              </div>
            </>
          )}
        </div>
      </main>

      <LoadingOverlay show={isAnalyzing} />
    </div>
  );
}
