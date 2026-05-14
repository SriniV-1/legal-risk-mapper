import { useState, useEffect, useRef } from "react";
import { Link } from "react-router-dom";
import {
  checkHealth,
  analyzeText,
  analyzeFile,
  extractText,
  benchmarkText,
  generateRedlines,
} from "../api/client.js";
import ContractReader from "../components/ContractReader.jsx";
import BenchmarkResults from "../components/BenchmarkResults.jsx";
import RedlineResults from "../components/RedlineResults.jsx";
import Loader from "../components/Loader.jsx";

const SAMPLES = {
  contract: {
    label: "SaaS Service Agreement",
    text: `SERVICE AGREEMENT\n\nThis Service Agreement is entered into between Acme Software Inc. ("Company") and the customer ("Client").\n\n1. SERVICES\nCompany provides software-as-a-service access. Services are provided AS-IS without any warranty of fitness for a particular purpose or merchantability.\n\n2. PAYMENT TERMS\nClient shall pay all invoices within Net 30 days. Unpaid balances accrue interest at 18% per annum. Company may unilaterally change pricing at any time with 7 days notice.\n\n3. AUTO-RENEWAL\nThis Agreement automatically renews annually unless cancelled in writing 90 days prior. Early termination fee of 75% of remaining contract value applies.\n\n4. LIABILITY\nIN NO EVENT SHALL COMPANY BE LIABLE FOR CONSEQUENTIAL, INCIDENTAL, OR PUNITIVE DAMAGES. Client shall indemnify and hold harmless Company from any third-party claims.\n\n5. DATA PROCESSING\nCompany collects personal data including usage metrics and user information. This data may be shared with third-party analytics providers. Company may sell aggregated user data.\n\n6. COMPLIANCE\nClient must comply with all applicable laws and regulations, including GDPR and export control requirements.\n\n7. MODIFICATIONS\nCompany reserves the right to modify these terms at its sole discretion at any time without notice.`,
  },
  privacy: {
    label: "Privacy Policy — DataFlow",
    text: `PRIVACY POLICY\n\nWe collect personally identifiable information (PII) including your name, email, location data, and browsing behavior. We track your activity across our platform using cookies and similar tracking technologies.\n\nYour personal data may be shared with third-party advertising partners for targeted marketing. We may sell your data to data brokers. We retain user information indefinitely unless you request deletion.\n\nOur facial recognition feature collects biometric data for personalization. We comply with applicable laws regarding children's data collection.\n\nWe may change this policy from time to time at our discretion without prior notice. Data may be transferred to countries without adequate GDPR protections.`,
  },
  startup: {
    label: "MediLink — Startup Terms",
    text: `MediLink connects patients with healthcare providers via a mobile app. We collect health records, including biometric data and medical history, for personalized care recommendations.\n\nRevenue Model:\n- Subscription fees from providers (automatic renewal, no early termination refund)\n- Sale of anonymized patient data to pharmaceutical companies\n- Licensing fee of $50,000 minimum commitment per enterprise client\n\nCompliance: We believe our platform is broadly compliant with applicable laws. HIPAA requirements will be addressed as we scale.\n\nRisk Factors: Users indemnify MediLink for any claims arising from health recommendations. Our liability is limited to fees paid. Platform provided as-is without warranty.`,
  },
  sneaky: {
    label: "Paraphrased Contract (semantic)",
    text: `Agreement for Platform Access\n\nThe receiving party agrees to make the disclosing party whole for any costs, expenses, or financial losses incurred as a result of any breach of this agreement, without limit as to amount or duration.\n\nUser-specific information gathered during your engagement with our platform may be transmitted to and retained on servers located in jurisdictions outside your country of residence where data protection standards may differ.\n\nThis agreement shall continue for successive annual terms unless either party provides written notice of non-renewal at least ninety days before the end of the then-current term.\n\nWe may gather facial geometry and voice patterns during authentication for improved security and personalization of the user experience.`,
  },
};

// Inline SVG icons to avoid external icon library dependency
function Icon({ name, size = 14 }) {
  const paths = {
    "arrow-left": <><line x1="19" y1="12" x2="5" y2="12"/><polyline points="12 19 5 12 12 5"/></>,
    "file-text":  <><path d="M14 2H6a2 2 0 0 0-2 2v16a2 2 0 0 0 2 2h12a2 2 0 0 0 2-2V8z"/><polyline points="14 2 14 8 20 8"/><line x1="16" y1="13" x2="8" y2="13"/><line x1="16" y1="17" x2="8" y2="17"/><polyline points="10 9 9 9 8 9"/></>,
    "upload-cloud": <><polyline points="16 16 12 12 8 16"/><line x1="12" y1="12" x2="12" y2="21"/><path d="M20.39 18.39A5 5 0 0 0 18 9h-1.26A8 8 0 1 0 3 16.3"/></>,
    "check-circle": <><path d="M22 11.08V12a10 10 0 1 1-5.93-9.14"/><polyline points="22 4 12 14.01 9 11.01"/></>,
    "search":     <><circle cx="11" cy="11" r="8"/><line x1="21" y1="21" x2="16.65" y2="16.65"/></>,
    "bar-chart-2":<><line x1="18" y1="20" x2="18" y2="10"/><line x1="12" y1="20" x2="12" y2="4"/><line x1="6" y1="20" x2="6" y2="14"/></>,
    "x":          <><line x1="18" y1="6" x2="6" y2="18"/><line x1="6" y1="6" x2="18" y2="18"/></>,
    "alert-circle": <><circle cx="12" cy="12" r="10"/><line x1="12" y1="8" x2="12" y2="12"/><line x1="12" y1="16" x2="12.01" y2="16"/></>,
    "scale":      <><line x1="12" y1="1" x2="12" y2="23"/><path d="M17 5H9.5a3.5 3.5 0 0 0 0 7h5a3.5 3.5 0 0 1 0 7H6"/></>,
  };
  return (
    <svg width={size} height={size} viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2" strokeLinecap="round" strokeLinejoin="round">
      {paths[name]}
    </svg>
  );
}

export default function AppPage() {
  const [health, setHealth] = useState(null); // null | { status: "ok"|"err", label: string }
  const [tab, setTab] = useState("text");
  const [inputText, setInputText] = useState("");
  const [file, setFile] = useState(null);
  const [dragging, setDragging] = useState(false);
  const [loading, setLoading] = useState(false);
  const [loadingMsg, setLoadingMsg] = useState("");
  const [error, setError] = useState(null);

  // Results
  const [riskData, setRiskData] = useState(null);
  const [contractText, setContractText] = useState(""); // text shown in reader
  const [benchmarkData, setBenchmarkData] = useState(null);
  const [redlineData, setRedlineData] = useState(null);
  const [sevFilter, setSevFilter] = useState("all");
  const [view, setView] = useState("placeholder"); // "placeholder" | "risk" | "benchmark"

  const fileInputRef = useRef(null);
  const mainRef = useRef(null);

  useEffect(() => {
    checkHealth()
      .then((d) => setHealth({ status: "ok", label: `v${d.version || "?"} · online` }))
      .catch(() => setHealth({ status: "err", label: "Backend offline" }));
  }, []);

  function loadSample(key) {
    setInputText(SAMPLES[key].text);
    setTab("text");
    setError(null);
  }

  function handleFileSet(f) {
    setFile(f);
    setError(null);
  }

  function handleDrop(e) {
    e.preventDefault();
    setDragging(false);
    if (e.dataTransfer.files[0]) handleFileSet(e.dataTransfer.files[0]);
  }

  function clearAll() {
    setInputText("");
    setFile(null);
    setError(null);
    setRiskData(null);
    setContractText("");
    setBenchmarkData(null);
    setRedlineData(null);
    setSevFilter("all");
    setView("placeholder");
    if (fileInputRef.current) fileInputRef.current.value = "";
  }

  async function handleAnalyze() {
    setError(null);
    try {
      setLoading(true);
      setLoadingMsg("Running ML risk classifier…");
      let data;
      let resolvedText = "";
      if (tab === "file" && file) {
        const name = file.name.toLowerCase();
        if (name.endsWith(".pdf")) {
          setLoadingMsg("Extracting text from PDF…");
          const res = await extractText(file);
          resolvedText = res.text || "";
          setLoadingMsg("Running ML risk classifier…");
          data = await analyzeText(resolvedText);
        } else {
          resolvedText = await file.text();
          data = await analyzeText(resolvedText);
        }
      } else {
        resolvedText = inputText.trim();
        if (resolvedText.length < 10) { setError("Please enter at least 10 characters."); return; }
        data = await analyzeText(resolvedText);
      }
      setContractText(resolvedText);
      setRiskData(data);
      setSevFilter("all");
      setBenchmarkData(null);
      setRedlineData(null);
      setView("risk");
      mainRef.current?.scrollTo({ top: 0, behavior: "smooth" });
    } catch (e) {
      setError(`Analysis failed: ${e.message}`);
    } finally {
      setLoading(false);
    }
  }

  async function handleBenchmark() {
    setError(null);
    let text = "";
    try {
      setLoading(true);
      setLoadingMsg("Preparing text…");

      if (tab === "file" && file) {
        if (file.name.toLowerCase().endsWith(".pdf")) {
          setLoadingMsg("Extracting text from PDF…");
          const res = await extractText(file);
          text = res.text;
        } else {
          text = await file.text();
        }
      } else {
        text = inputText.trim();
      }

      if (text.trim().length < 30) {
        setError("Please enter at least 30 characters to benchmark.");
        return;
      }

      setLoadingMsg("Benchmarking against SEC EDGAR corpus…");
      const bench = await benchmarkText(text, "auto");

      setLoadingMsg(`Generating ${bench.clause_type.replace(/_/g, " ")} redlines…`);
      const redlines = await generateRedlines(text, bench.clause_type);

      setBenchmarkData(bench);
      setRedlineData(redlines);
      setRiskData(null);
      setView("benchmark");
      mainRef.current?.scrollTo({ top: 0, behavior: "smooth" });
    } catch (e) {
      setError(`Benchmark failed: ${e.message}`);
    } finally {
      setLoading(false);
    }
  }

  return (
    <div style={{ fontFamily: "var(--sans)" }}>
      {loading && <Loader message={loadingMsg} />}

      {/* HEADER */}
      <header className="app-header">
        <Link to="/" className="back-link">
          <Icon name="arrow-left" size={14} />
          ALRM
        </Link>
        <div className="header-divider" />
        <span className="header-title">Analysis</span>
        <div className="header-spacer" />
        <div className="health-indicator">
          <span className={`health-dot${health ? ` ${health.status}` : ""}`} />
          <span>{health ? health.label : "Checking…"}</span>
        </div>
      </header>

      {/* LAYOUT */}
      <div className="app-layout">
        {/* SIDEBAR */}
        <aside className="sidebar">
          {/* TABS */}
          <div className="tabs">
            <button
              className={`tab-btn${tab === "text" ? " active" : ""}`}
              onClick={() => setTab("text")}
            >
              Paste Text
            </button>
            <button
              className={`tab-btn${tab === "file" ? " active" : ""}`}
              onClick={() => setTab("file")}
            >
              Upload File
            </button>
          </div>

          {/* PASTE TEXT */}
          <div className={`tab-panel${tab === "text" ? " active" : ""}`} id="tab-text">
            <textarea
              className="clause-textarea"
              placeholder="Paste a contract clause or section here…"
              value={inputText}
              onChange={(e) => setInputText(e.target.value)}
            />
            <div className="char-count">
              {inputText.length.toLocaleString()} character{inputText.length !== 1 ? "s" : ""}
            </div>
          </div>

          {/* UPLOAD FILE */}
          <div className={`tab-panel${tab === "file" ? " active" : ""}`} id="tab-file">
            <div
              className={`dropzone${dragging ? " dragover" : ""}`}
              onClick={() => fileInputRef.current?.click()}
              onDragOver={(e) => { e.preventDefault(); setDragging(true); }}
              onDragLeave={() => setDragging(false)}
              onDrop={handleDrop}
            >
              <div className="dropzone-icon">
                <Icon name="upload-cloud" size={24} />
              </div>
              <div className="dropzone-label">Drop file here or click to browse</div>
              <div className="dropzone-hint" style={{ color: "var(--text-3)" }}>.pdf · .txt · .md</div>
            </div>
            {file && (
              <div className="file-selected">
                <Icon name="check-circle" size={13} />
                {file.name} ({(file.size / 1024).toFixed(1)} KB)
              </div>
            )}
            <input
              ref={fileInputRef}
              type="file"
              accept=".pdf,.txt,.md"
              style={{ display: "none" }}
              onChange={(e) => e.target.files[0] && handleFileSet(e.target.files[0])}
            />
          </div>

          {/* SAMPLES */}
          <div className="panel-section">
            <div className="panel-label">Sample Documents</div>
            <div className="samples-list">
              {Object.entries(SAMPLES).map(([key, s]) => (
                <button key={key} className="sample-btn" onClick={() => loadSample(key)}>
                  <Icon name="file-text" size={13} />
                  {s.label}
                </button>
              ))}
            </div>
          </div>

          {/* ERROR */}
          {error && (
            <div className="error-box">
              <Icon name="alert-circle" size={14} />
              <span>{error}</span>
            </div>
          )}

          {/* CONTROLS */}
          <div className="controls-section">
            <div className="btn-row">
              <button
                className="btn btn-primary"
                disabled={loading}
                onClick={handleAnalyze}
              >
                <Icon name="search" size={14} />
                Analyze Risk
              </button>
              <button
                className="btn btn-secondary"
                disabled={loading}
                onClick={handleBenchmark}
              >
                <Icon name="bar-chart-2" size={14} />
                Benchmark
              </button>
            </div>
            <button className="btn btn-ghost btn-full" onClick={clearAll}>
              <Icon name="x" size={14} />
              Clear
            </button>
          </div>
        </aside>

        {/* MAIN CONTENT */}
        <main className="main-content" ref={mainRef}>
          {view === "placeholder" && (
            <div className="card">
              <div className="placeholder">
                <div className="placeholder-icon">
                  <Icon name="scale" size={22} />
                </div>
                <div className="placeholder-title">No analysis yet</div>
                <p className="placeholder-hint">
                  Paste a contract clause or upload a file, then click Analyze Risk or Benchmark.
                </p>
              </div>
            </div>
          )}

          {view === "risk" && riskData && (
            <ContractReader
              contractText={contractText}
              data={riskData}
              sevFilter={sevFilter}
              onFilterChange={setSevFilter}
            />
          )}

          {view === "benchmark" && benchmarkData && (
            <>
              <BenchmarkResults data={benchmarkData} />
              {redlineData && <RedlineResults data={redlineData} />}
            </>
          )}
        </main>
      </div>
    </div>
  );
}
