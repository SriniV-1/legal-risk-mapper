import { useState, useEffect } from "react";
import { Link } from "react-router-dom";
import { checkHealth, fetchLimits } from "../api/client.js";
import useFileUpload from "../hooks/useFileUpload.js";
import useAnalysis from "../hooks/useAnalysis.js";
import useBenchmark from "../hooks/useBenchmark.js";
import useWarmup from "../hooks/useWarmup.js";
import { DEFAULT_LIMITS, checkSize } from "../constants/limits.js";
import Loader from "../components/Loader.jsx";
import Icon from "../components/Icon.jsx";
import InputPanel from "../components/InputPanel.jsx";
import ResultsPanel from "../components/ResultsPanel.jsx";
import SAMPLES from "../constants/samples.js";

export default function AppPage() {
  const [health, setHealth] = useState(null);
  const [dismissed, setDismissed] = useState(false);
  const [limits, setLimits] = useState(DEFAULT_LIMITS);
  const apiBase = import.meta.env.VITE_API_BASE_URL || "http://localhost:8000";

  const warm = useWarmup();
  const fileUpload = useFileUpload();
  const analysis = useAnalysis();
  const benchmark = useBenchmark({
    setLoading: analysis.setLoading,
    setLoadingMsg: analysis.setLoadingMsg,
    setError: analysis.setError,
    setView: analysis.setView,
    setRiskData: analysis.setRiskData,
    mainRef: analysis.mainRef,
  });

  useEffect(() => {
    checkHealth()
      .then((d) => setHealth({ status: "ok", label: `v${d.version || "?"} · online`, version: d.version || "?" }))
      .catch(() => setHealth({ status: "err", label: "Backend offline", version: null }));

    // Keep the disclaimer's numbers identical to what the server enforces.
    fetchLimits()
      .then(setLimits)
      .catch(() => setLimits(DEFAULT_LIMITS));
  }, []);

  /**
   * Show the loading overlay only if the user got here before background
   * warmup finished. When warmup is already done (the common case) this is a
   * no-op and the run starts instantly.
   */
  async function ensureWarm() {
    if (warm.status !== "warming") return;
    analysis.setLoading(true);
    analysis.setLoadingMsg("Warming up models (first run only)…");
    await warm.wait();
  }

  /** Block oversized input up front instead of letting it 413/429 downstream. */
  function blockedBySize(text, mode) {
    const result = checkSize(text, mode, limits);
    if (!result.ok) {
      analysis.setError(result.message);
      return true;
    }
    return false;
  }

  async function handleAnalyzeSample(key) {
    fileUpload.loadSample(key, SAMPLES);
    benchmark.clearBenchmark();
    await ensureWarm();
    await analysis.analyzeSample(SAMPLES[key].text);
  }

  async function handleAnalyze() {
    if (fileUpload.tab === "text") {
      if (fileUpload.inputText.trim().length < 10) {
        analysis.setError("Please enter at least 10 characters.");
        return;
      }
      if (blockedBySize(fileUpload.inputText, "local")) return;
    }
    benchmark.clearBenchmark();
    await ensureWarm();
    await analysis.analyze(fileUpload.getResolvedText);
  }

  async function handleBenchmark() {
    if (fileUpload.tab === "text" && blockedBySize(fileUpload.inputText, "llm")) return;
    await ensureWarm();
    await benchmark.runBenchmark(fileUpload.getResolvedText);
  }

  function handleLoadSample(key) {
    fileUpload.loadSample(key, SAMPLES);
    analysis.setError(null);
  }

  function clearAll() {
    fileUpload.clearInput();
    analysis.clearAnalysis();
    benchmark.clearBenchmark();
  }

  const anyLoading = analysis.loading || benchmark.benchmarkLoading || benchmark.redlineLoading;

  return (
    <div style={{ fontFamily: "var(--sans)" }}>
      {analysis.loading && <Loader message={analysis.loadingMsg} />}

      <header className="app-header">
        <Link to="/" className="back-link">
          <Icon name="arrow-left" size={14} />
          ALRM
        </Link>
        <div className="header-divider" />
        <span className="header-title">Analysis</span>
        <div className="header-spacer" />
        <div className="health-wrapper">
          <div className="health-indicator">
            <span className={`health-dot${health ? ` ${health.status}` : ""}`} />
            <span>{health ? health.label : "Checking…"}</span>
          </div>
          <div className="health-tooltip">
            <strong>API</strong> {apiBase}<br />
            <strong>Version</strong> {health?.version || "—"}<br />
            <strong>Status</strong> {health?.status === "ok" ? "Online" : health?.status === "err" ? "Offline" : "Checking…"}
          </div>
        </div>
      </header>

      {health?.status === "err" && !dismissed && (
        <div className="offline-banner">
          <svg viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2" strokeLinecap="round" strokeLinejoin="round">
            <circle cx="12" cy="12" r="10"/><line x1="12" y1="8" x2="12" y2="12"/><line x1="12" y1="16" x2="12.01" y2="16"/>
          </svg>
          Backend is offline — analysis requests will fail. The API may be sleeping on Hugging Face (cold start ~30s).
          <button className="offline-banner-dismiss" onClick={() => setDismissed(true)}>
            <svg viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2" strokeLinecap="round" strokeLinejoin="round">
              <line x1="18" y1="6" x2="6" y2="18"/><line x1="6" y1="6" x2="18" y2="18"/>
            </svg>
          </button>
        </div>
      )}

      <div className="app-layout" style={health?.status === "err" && !dismissed ? { marginTop: "44px" } : {}}>
        <InputPanel
          tab={fileUpload.tab}
          setTab={fileUpload.setTab}
          inputText={fileUpload.inputText}
          setInputText={fileUpload.setInputText}
          file={fileUpload.file}
          dragging={fileUpload.dragging}
          setDragging={fileUpload.setDragging}
          fileInputRef={fileUpload.fileInputRef}
          handleFileSet={(f) => { fileUpload.handleFileSet(f); analysis.setError(null); }}
          samples={SAMPLES}
          loadSample={handleLoadSample}
          error={analysis.error}
          anyLoading={anyLoading}
          limits={limits}
          onAnalyze={handleAnalyze}
          onBenchmark={handleBenchmark}
          onClear={clearAll}
        />

        <ResultsPanel
          ref={analysis.mainRef}
          view={analysis.view}
          riskData={analysis.riskData}
          contractText={analysis.contractText}
          sevFilter={analysis.sevFilter}
          onFilterChange={analysis.setSevFilter}
          benchmarkData={benchmark.benchmarkData}
          benchmarkLoading={benchmark.benchmarkLoading}
          redlineData={benchmark.redlineData}
          redlineLoading={benchmark.redlineLoading}
          onAnalyzeSample={handleAnalyzeSample}
        />
      </div>
    </div>
  );
}
