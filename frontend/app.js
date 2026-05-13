/**
 * Legal Risk Mapper v2 — Frontend (vanilla JS)
 * Talks to FastAPI backend at /analyze and /health.
 * Renders hero stats, three charts, filter bar, and grouped risk cards.
 */

// In production, set window.LRM_API_BASE via a <script> tag or env config.
// Falls back to localhost:8000 for local development.
const API_BASE = window.LRM_API_BASE || "http://localhost:8000";

// ─────────────────────────────────────────────────────────────────────────────
//  SAMPLE DOCUMENTS
// ─────────────────────────────────────────────────────────────────────────────
const SAMPLES = {
  contract: {
    title: "SaaS Service Agreement",
    text: `SERVICE AGREEMENT

This Service Agreement is entered into between Acme Software Inc. ("Company") and the customer ("Client").

1. SERVICES
Company provides software-as-a-service access. Services are provided AS-IS without any warranty of fitness for a particular purpose or merchantability.

2. PAYMENT TERMS
Client shall pay all invoices within Net 30 days. Unpaid balances accrue interest at 18% per annum. Company may unilaterally change pricing at any time with 7 days notice.

3. AUTO-RENEWAL
This Agreement automatically renews annually unless cancelled in writing 90 days prior. Early termination fee of 75% of remaining contract value applies.

4. LIABILITY
IN NO EVENT SHALL COMPANY BE LIABLE FOR CONSEQUENTIAL, INCIDENTAL, OR PUNITIVE DAMAGES. Client shall indemnify and hold harmless Company from any third-party claims.

5. DATA PROCESSING
Company collects personal data including usage metrics and user information. This data may be shared with third-party analytics providers. Company may sell aggregated user data.

6. COMPLIANCE
Client must comply with all applicable laws and regulations, including GDPR and export control requirements.

7. MODIFICATIONS
Company reserves the right to modify these terms at its sole discretion at any time without notice.`
  },
  privacy: {
    title: "Privacy Policy — DataFlow App",
    text: `PRIVACY POLICY

We collect personally identifiable information (PII) including your name, email, location data, and browsing behavior. We track your activity across our platform using cookies and similar tracking technologies.

Your personal data may be shared with third-party advertising partners for targeted marketing. We may sell your data to data brokers. We retain user information indefinitely unless you request deletion.

Our facial recognition feature collects biometric data for personalization. We comply with applicable laws regarding children's data collection.

We may change this policy from time to time at our discretion without prior notice. Data may be transferred to countries without adequate GDPR protections.`
  },
  startup: {
    title: "Startup Business Description",
    text: `MediLink connects patients with healthcare providers via a mobile app. We collect health records, including biometric data and medical history, for personalized care recommendations.

Revenue Model:
- Subscription fees from providers (automatic renewal, no early termination refund)
- Sale of anonymized patient data to pharmaceutical companies
- Licensing fee of $50,000 minimum commitment per enterprise client

Compliance: We believe our platform is broadly compliant with applicable laws. HIPAA requirements will be addressed as we scale.

Risk Factors: Users indemnify MediLink for any claims arising from health recommendations. Our liability is limited to fees paid. Platform provided as-is without warranty.

We may unilaterally adjust business terms, pricing, and data use policies as the business evolves.`
  },
  sneaky: {
    title: "Paraphrased Contract (semantic test)",
    text: `Agreement for Platform Access

The receiving party agrees to make the disclosing party whole for any costs, expenses, or financial losses incurred as a result of any breach of this agreement, without limit as to amount or duration.

User-specific information gathered during your engagement with our platform may be transmitted to and retained on servers located in jurisdictions outside your country of residence where data protection standards may differ.

The company may take such actions as it sees fit to protect its interests, and its determinations on matters of interpretation shall be final.

This agreement shall continue for successive annual terms unless either party provides written notice of non-renewal at least ninety days before the end of the then-current term.

Platform services are delivered on a commercially reasonable basis and the provider makes no guarantees regarding continuous availability, fitness for any particular purpose, or accuracy of results.

We may gather facial geometry and voice patterns during authentication for improved security and personalization of the user experience.`
  },
};

// ─────────────────────────────────────────────────────────────────────────────
//  STATE
// ─────────────────────────────────────────────────────────────────────────────
const state = {
  currentTab: "text",
  file: null,
  risks: [],
  severityFilter: "all",
  sourceFilter: "all",
  viewMode: "grouped",
  charts: { category: null, severity: null, source: null },
  lastAnalysis: null,
};

// ─────────────────────────────────────────────────────────────────────────────
//  DOM REFS
// ─────────────────────────────────────────────────────────────────────────────
const $ = (id) => document.getElementById(id);
const analyzeBtn = $("analyzeBtn");
const clearBtn = $("clearBtn");
const textInput = $("textInput");
const docTitle = $("docTitle");
const fileInput = $("fileInput");
const dropzone = $("dropzone");
const fileNameEl = $("fileName");
const charCount = $("charCount");
const errorBox = $("errorBox");
const resultsSection = $("resultsSection");
const loaderOverlay = $("loaderOverlay");
const riskContainer = $("riskContainer");
const healthPill = $("healthPill");
const healthLabel = $("healthLabel");

// ─────────────────────────────────────────────────────────────────────────────
//  INITIAL HEALTH CHECK
// ─────────────────────────────────────────────────────────────────────────────
async function checkHealth() {
  try {
    const r = await fetch(`${API_BASE}/health`);
    const data = await r.json();
    healthPill.classList.add("ok");
    healthPill.classList.remove("err");
    healthLabel.textContent = `Backend v${data.version} · ${data.nlp_engine.split("+").length} layers active`;
  } catch {
    healthPill.classList.add("err");
    healthPill.classList.remove("ok");
    healthLabel.textContent = "Backend offline";
  }
}
checkHealth();

// ─────────────────────────────────────────────────────────────────────────────
//  TABS
// ─────────────────────────────────────────────────────────────────────────────
document.querySelectorAll(".tab").forEach((tab) => {
  tab.addEventListener("click", () => {
    state.currentTab = tab.dataset.tab;
    document.querySelectorAll(".tab").forEach((t) => t.classList.remove("active"));
    document.querySelectorAll(".tab-content").forEach((c) => c.classList.remove("active"));
    tab.classList.add("active");
    $("tab-" + state.currentTab).classList.add("active");
  });
});

// ─────────────────────────────────────────────────────────────────────────────
//  CHAR COUNT
// ─────────────────────────────────────────────────────────────────────────────
textInput.addEventListener("input", () => {
  const n = textInput.value.length;
  charCount.textContent = `${n.toLocaleString()} character${n !== 1 ? "s" : ""}`;
});

// ─────────────────────────────────────────────────────────────────────────────
//  SAMPLES
// ─────────────────────────────────────────────────────────────────────────────
document.querySelectorAll(".sample-card").forEach((card) => {
  card.addEventListener("click", () => {
    const sample = SAMPLES[card.dataset.sample];
    if (!sample) return;
    textInput.value = sample.text;
    docTitle.value = sample.title;
    charCount.textContent = `${sample.text.length.toLocaleString()} characters`;
    document.querySelector('[data-tab="text"]').click();
  });
});

// ─────────────────────────────────────────────────────────────────────────────
//  FILE UPLOAD
// ─────────────────────────────────────────────────────────────────────────────
fileInput.addEventListener("change", (e) => e.target.files[0] && setFile(e.target.files[0]));
dropzone.addEventListener("click", () => fileInput.click());
dropzone.addEventListener("dragover", (e) => { e.preventDefault(); dropzone.classList.add("dragover"); });
dropzone.addEventListener("dragleave", () => dropzone.classList.remove("dragover"));
dropzone.addEventListener("drop", (e) => {
  e.preventDefault();
  dropzone.classList.remove("dragover");
  if (e.dataTransfer.files[0]) setFile(e.dataTransfer.files[0]);
});
function setFile(file) {
  state.file = file;
  fileNameEl.textContent = `Selected: ${file.name} (${(file.size / 1024).toFixed(1)} KB)`;
}

// ─────────────────────────────────────────────────────────────────────────────
//  CLEAR
// ─────────────────────────────────────────────────────────────────────────────
clearBtn.addEventListener("click", () => {
  textInput.value = "";
  docTitle.value = "";
  charCount.textContent = "0 characters";
  state.file = null;
  fileNameEl.textContent = "No file selected";
  fileInput.value = "";
  resultsSection.classList.add("hidden");
  benchmarkSection.classList.add("hidden");
  hideError();
});

// ─────────────────────────────────────────────────────────────────────────────
//  EXPORT
// ─────────────────────────────────────────────────────────────────────────────
document.addEventListener("click", (e) => {
  const btn = e.target.closest("#exportRiskBtn");
  if (btn && state.lastAnalysis) {
    const blob = new Blob(
      [JSON.stringify(state.lastAnalysis, null, 2)],
      { type: "application/json" },
    );
    const url = URL.createObjectURL(blob);
    const a = document.createElement("a");
    const title = (state.lastAnalysis.document_title || "analysis").replace(/[^a-z0-9]/gi, "_").toLowerCase();
    a.href = url;
    a.download = `legal_risk_${title}.json`;
    a.click();
    URL.revokeObjectURL(url);
  }
});

// ─────────────────────────────────────────────────────────────────────────────
//  ANALYZE
// ─────────────────────────────────────────────────────────────────────────────
analyzeBtn.addEventListener("click", runAnalyze);

async function runAnalyze() {
  hideError();
  if (state.currentTab === "file" && state.file) return analyzeFile(state.file);

  const text = textInput.value.trim();
  if (text.length < 10) return showError("Please enter at least 10 characters of text to analyze.");
  await analyzeText(text, docTitle.value.trim() || null);
}

async function analyzeText(text, title) {
  showLoader();
  try {
    const res = await fetch(`${API_BASE}/analyze`, {
      method: "POST",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify({ text, document_title: title }),
    });
    await handleResponse(res);
  } catch (err) {
    showError(`Could not reach the backend. Make sure the server is running on port 8000.\n\n${err.message}`);
  } finally {
    hideLoader();
  }
}

async function analyzeFile(file) {
  showLoader();
  try {
    const form = new FormData();
    form.append("file", file);
    if (docTitle.value.trim()) form.append("document_title", docTitle.value.trim());
    const res = await fetch(`${API_BASE}/analyze/upload`, { method: "POST", body: form });
    await handleResponse(res);
  } catch (err) {
    showError(`Could not reach the backend: ${err.message}`);
  } finally {
    hideLoader();
  }
}

async function handleResponse(res) {
  if (!res.ok) {
    const err = await res.json().catch(() => ({ detail: res.statusText }));
    throw new Error(err.detail || "Server error");
  }
  renderResults(await res.json());
}

// ─────────────────────────────────────────────────────────────────────────────
//  RENDER
// ─────────────────────────────────────────────────────────────────────────────
function renderResults(data) {
  state.risks = data.risks || [];
  state.lastAnalysis = data;  // store for export

  // Hero
  const lvl = data.overall_risk_level;
  const hero = $("overallBadge");
  hero.textContent = lvl.toUpperCase();
  hero.className = `hero-badge ${lvl}`;
  $("heroDocTitle").textContent = data.document_title ? `Document: ${data.document_title}` : "";

  // Stats
  $("statTotal").textContent = data.total_risks;
  $("statHigh").textContent = data.severity_breakdown.High || 0;
  $("statMed").textContent = data.severity_breakdown.Medium || 0;
  $("statLow").textContent = data.severity_breakdown.Low || 0;

  // Charts
  renderCharts(data);

  // Risks
  renderRisks();

  // Notes
  $("notesCard").innerHTML = `<strong>ℹ Analysis:</strong> ${escHtml(data.analysis_notes)}`;

  resultsSection.classList.remove("hidden");
  resultsSection.scrollIntoView({ behavior: "smooth", block: "start" });
}

function renderCharts(data) {
  const baseOpts = {
    responsive: true,
    maintainAspectRatio: false,
    plugins: { legend: { labels: { font: { size: 11, family: "Inter" } } } },
  };

  // CATEGORY (bar)
  const catLabels = Object.keys(data.risk_summary);
  const catValues = Object.values(data.risk_summary);
  if (state.charts.category) state.charts.category.destroy();
  state.charts.category = new Chart($("categoryChart"), {
    type: "bar",
    data: {
      labels: catLabels.map((l) => l.replace(" Risk", "").replace("Contractual ", "")),
      datasets: [{
        data: catValues,
        backgroundColor: ["#3b82f6", "#8b5cf6", "#ec4899", "#f59e0b", "#10b981"],
        borderRadius: 8,
      }],
    },
    options: {
      ...baseOpts,
      plugins: { legend: { display: false } },
      scales: {
        y: { beginAtZero: true, ticks: { stepSize: 1, font: { size: 11 } }, grid: { color: "#f1f5f9" } },
        x: { ticks: { font: { size: 10 } }, grid: { display: false } },
      },
    },
  });

  // SEVERITY (doughnut)
  if (state.charts.severity) state.charts.severity.destroy();
  state.charts.severity = new Chart($("severityChart"), {
    type: "doughnut",
    data: {
      labels: ["High", "Medium", "Low"],
      datasets: [{
        data: [data.severity_breakdown.High || 0, data.severity_breakdown.Medium || 0, data.severity_breakdown.Low || 0],
        backgroundColor: ["#dc2626", "#d97706", "#059669"],
        borderWidth: 3,
        borderColor: "#fff",
      }],
    },
    options: { ...baseOpts, cutout: "65%", plugins: { legend: { position: "bottom" } } },
  });

  // DETECTION SOURCE (doughnut)
  const counts = { regex: 0, semantic: 0, hybrid: 0 };
  state.risks.forEach((r) => {
    const s = new Set(r.sources || []);
    if (s.has("regex") && s.has("semantic")) counts.hybrid++;
    else if (s.has("regex")) counts.regex++;
    else if (s.has("semantic")) counts.semantic++;
  });
  if (state.charts.source) state.charts.source.destroy();
  state.charts.source = new Chart($("sourceChart"), {
    type: "doughnut",
    data: {
      labels: ["Confirmed (both)", "Pattern only", "Semantic only"],
      datasets: [{
        data: [counts.hybrid, counts.regex, counts.semantic],
        backgroundColor: ["#0891b2", "#2563eb", "#8b5cf6"],
        borderWidth: 3,
        borderColor: "#fff",
      }],
    },
    options: { ...baseOpts, cutout: "65%", plugins: { legend: { position: "bottom" } } },
  });
}

// ─────────────────────────────────────────────────────────────────────────────
//  RISK LIST (with filters + grouping)
// ─────────────────────────────────────────────────────────────────────────────
function renderRisks() {
  const filtered = state.risks.filter((r) => {
    if (state.severityFilter !== "all" && r.severity !== state.severityFilter) return false;
    if (state.sourceFilter !== "all") {
      const s = new Set(r.sources || []);
      const isHybrid = s.has("regex") && s.has("semantic");
      if (state.sourceFilter === "hybrid" && !isHybrid) return false;
      if (state.sourceFilter === "regex" && !(s.has("regex") && !s.has("semantic"))) return false;
      if (state.sourceFilter === "semantic" && !(s.has("semantic") && !s.has("regex"))) return false;
    }
    return true;
  });

  if (!filtered.length) {
    riskContainer.innerHTML = `
      <div class="card empty-state">
        <div class="empty-icon">🔍</div>
        <div><strong>No risks match the current filter.</strong></div>
        <div>Try adjusting severity or source filters.</div>
      </div>`;
    return;
  }

  if (state.viewMode === "grouped") renderGrouped(filtered);
  else renderFlat(filtered);
}

function renderGrouped(risks) {
  const groups = {};
  risks.forEach((r) => {
    (groups[r.risk_type] ||= []).push(r);
  });

  const orderedCats = Object.keys(groups).sort((a, b) => groups[b].length - groups[a].length);

  riskContainer.innerHTML = orderedCats
    .map((cat) => {
      const group = groups[cat];
      const avgScore = group.reduce((s, r) => s + r.score, 0) / group.length;
      const highN = group.filter((r) => r.severity === "High").length;
      return `
        <div class="category-group">
          <div class="category-header" onclick="this.parentElement.classList.toggle('collapsed')">
            <div class="category-title-row">
              <span>${escHtml(cat)}</span>
              <span class="category-count-pill">${group.length}</span>
            </div>
            <div class="category-meta">
              ${highN} High · Avg confidence ${Math.round(avgScore * 100)}%
              <span class="category-chevron">▾</span>
            </div>
          </div>
          <div class="category-body">
            ${group.map(riskCardHtml).join("")}
          </div>
        </div>
      `;
    })
    .join("");
}

function renderFlat(risks) {
  riskContainer.innerHTML = `<div class="category-body" style="display:flex;flex-direction:column;gap:.8rem">${risks.map(riskCardHtml).join("")}</div>`;
}

function riskCardHtml(r) {
  const sources = new Set(r.sources || []);
  const hasBoth = sources.has("regex") && sources.has("semantic");

  const sourceBadges = [];
  if (hasBoth) sourceBadges.push(`<span class="src-badge hybrid">✓ CONFIRMED</span>`);
  else {
    if (sources.has("regex")) sourceBadges.push(`<span class="src-badge regex">PATTERN</span>`);
    if (sources.has("semantic")) sourceBadges.push(`<span class="src-badge semantic">SEMANTIC</span>`);
  }

  const keywords = (r.keywords_matched || [])
    .slice(0, 6)
    .map((k) => `<span class="keyword-tag">${escHtml(k)}</span>`)
    .join("");

  const simPct = r.semantic_similarity != null ? Math.round(r.semantic_similarity * 100) : null;
  const confPct = Math.round(r.score * 100);

  return `
    <div class="risk-card ${r.severity}">
      <div class="risk-header">
        <span class="severity-badge ${r.severity}">${r.severity}</span>
        <span class="risk-type-label">${escHtml(r.risk_type)}</span>
        <span class="source-badges">${sourceBadges.join("")}</span>
      </div>

      <div class="risk-snippet">${escHtml(r.text_snippet)}</div>

      <div class="risk-explanation">${escHtml(r.explanation)}</div>

      <div class="risk-metrics">
        <div class="confidence-block">
          <div class="confidence-label"><span>Confidence</span><b>${confPct}%</b></div>
          <div class="confidence-bar"><div class="confidence-fill ${r.severity}" style="width:${confPct}%"></div></div>
        </div>
        ${simPct != null ? `
        <div class="confidence-block">
          <div class="confidence-label"><span>Semantic similarity</span><b>${simPct}%</b></div>
          <div class="confidence-bar"><div class="confidence-fill Medium" style="width:${simPct}%"></div></div>
        </div>` : ""}
      </div>

      ${keywords || r.clause_index != null ? `
      <div class="risk-footer">
        ${keywords}
        ${r.clause_index != null ? `<span class="clause-ref">Clause #${r.clause_index}</span>` : ""}
      </div>` : ""}
    </div>
  `;
}

// ─────────────────────────────────────────────────────────────────────────────
//  FILTER + VIEW CONTROLS
// ─────────────────────────────────────────────────────────────────────────────
document.querySelectorAll("[data-filter-sev]").forEach((btn) => {
  btn.addEventListener("click", () => {
    document.querySelectorAll("[data-filter-sev]").forEach((b) => b.classList.remove("active"));
    btn.classList.add("active");
    state.severityFilter = btn.dataset.filterSev;
    renderRisks();
  });
});
document.querySelectorAll("[data-filter-src]").forEach((btn) => {
  btn.addEventListener("click", () => {
    document.querySelectorAll("[data-filter-src]").forEach((b) => b.classList.remove("active"));
    btn.classList.add("active");
    state.sourceFilter = btn.dataset.filterSrc;
    renderRisks();
  });
});
document.querySelectorAll("[data-view]").forEach((btn) => {
  btn.addEventListener("click", () => {
    document.querySelectorAll("[data-view]").forEach((b) => b.classList.remove("active"));
    btn.classList.add("active");
    state.viewMode = btn.dataset.view;
    renderRisks();
  });
});

// ─────────────────────────────────────────────────────────────────────────────
//  HELPERS
// ─────────────────────────────────────────────────────────────────────────────
function showLoader(hint) {
  loaderOverlay.classList.remove("hidden");
  analyzeBtn.disabled = true;
  $("benchmarkBtn").disabled = true;
  if (hint) $("loaderHint").textContent = hint;
}
function hideLoader() {
  loaderOverlay.classList.add("hidden");
  analyzeBtn.disabled = false;
  $("benchmarkBtn").disabled = false;
  $("loaderHint").textContent = "Running hybrid NLP pipeline";
}
function showError(msg) { errorBox.textContent = "⚠ " + msg; errorBox.classList.remove("hidden"); }
function hideError() { errorBox.classList.add("hidden"); }
function escHtml(str) {
  return String(str)
    .replace(/&/g, "&amp;").replace(/</g, "&lt;").replace(/>/g, "&gt;").replace(/"/g, "&quot;");
}

// ─────────────────────────────────────────────────────────────────────────────
//  BENCHMARK & REDLINE
// ─────────────────────────────────────────────────────────────────────────────
const benchmarkBtn = $("benchmarkBtn");
const benchmarkSection = $("benchmarkSection");

benchmarkBtn.addEventListener("click", runBenchmark);

async function runBenchmark() {
  hideError();
  const text = textInput.value.trim();
  if (text.length < 30) return showError("Please enter at least 30 characters of clause text to benchmark.");

  const clauseType = $("clauseTypeSelect").value;  // "auto" or explicit type

  showLoader("Detecting clause type and benchmarking against SEC EDGAR corpus...");
  try {
    // Call benchmark endpoint — passes "auto" or an explicit override
    const benchRes = await fetch(`${API_BASE}/benchmark`, {
      method: "POST",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify({ text, clause_type: clauseType }),
    });
    if (!benchRes.ok) {
      const err = await benchRes.json().catch(() => ({ detail: benchRes.statusText }));
      throw new Error(err.detail || "Benchmark failed");
    }
    const benchmark = await benchRes.json();

    // Update loader hint for redline step
    $("loaderHint").textContent = `Generating ${benchmark.clause_type} redline suggestions...`;

    // Redline uses the resolved type returned by benchmark (not the raw "auto")
    const redlineRes = await fetch(`${API_BASE}/redline`, {
      method: "POST",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify({ text, clause_type: benchmark.clause_type }),
    });
    if (!redlineRes.ok) {
      const err = await redlineRes.json().catch(() => ({ detail: redlineRes.statusText }));
      throw new Error(err.detail || "Redline generation failed");
    }
    const redline = await redlineRes.json();

    renderBenchmarkResults(benchmark, redline);
  } catch (err) {
    showError(`Benchmark error: ${err.message}\n\nMake sure Ollama is running (ollama serve) and the backend is on port 8000.`);
  } finally {
    hideLoader();
  }
}

function renderBenchmarkResults(benchmark, redline) {
  // Hero stats
  $("benchSampleSize").textContent = benchmark.sample_size;
  const typeLabel = benchmark.clause_type.replace(/_/g, " ");
  $("benchSubtitle").textContent = `${typeLabel} clause · ${benchmark.sample_size} similar clauses from SEC EDGAR`;
  $("benchExamples").textContent = benchmark.cited_examples.length;
  $("benchRedlines").textContent = redline.suggestions.length;

  // User extraction
  renderExtraction(benchmark.user_extraction, benchmark.clause_type);

  // Market distributions
  renderDistributions(benchmark.field_distributions, benchmark.user_extraction, benchmark.user_percentiles, benchmark.clause_type);

  // Cited examples
  renderCitedExamples(benchmark.cited_examples);

  // Redline suggestions
  renderRedlines(redline);

  benchmarkSection.classList.remove("hidden");
  resultsSection.classList.add("hidden");
  benchmarkSection.scrollIntoView({ behavior: "smooth", block: "start" });
}

// ── Per-category field definitions for extraction display ──
const EXTRACTION_FIELDS = {
  liability: [
    { label: "Liability Cap", get: (e) => e.liability_cap?.has_cap },
    { label: "Cap Type", get: (e) => e.liability_cap?.cap_type || "—" },
    { label: "Mutual", get: (e) => e.is_mutual },
    { label: "Carve-Outs", get: (e) => e.has_carve_outs },
    { label: "Consequential Excluded", get: (e) => e.consequential_damages?.excluded },
    { label: "Indemnification", get: (e) => e.has_indemnification },
    { label: "Warranty Disclaimer", get: (e) => e.has_warranty_disclaimer },
  ],
  termination: [
    { label: "For Cause", get: (e) => e.has_termination_for_cause },
    { label: "For Convenience", get: (e) => e.has_termination_for_convenience },
    { label: "Cure Period", get: (e) => e.cure_period?.has_cure_period },
    { label: "Cure Days", get: (e) => e.cure_period?.cure_days ?? "—" },
    { label: "Notice Period", get: (e) => e.notice_period?.has_notice_period },
    { label: "Auto-Renewal", get: (e) => e.has_auto_renewal },
    { label: "Survival Clause", get: (e) => e.has_survival_clause },
    { label: "Termination Fee", get: (e) => e.has_termination_fee },
  ],
  payment: [
    { label: "Payment Terms", get: (e) => e.has_payment_terms },
    { label: "Payment Days", get: (e) => e.payment_days ?? "—" },
    { label: "Late Fee", get: (e) => e.late_fee?.has_late_fee },
    { label: "Price Escalation", get: (e) => e.has_price_escalation },
    { label: "Non-Refundable", get: (e) => e.has_non_refundable },
    { label: "Minimum Commitment", get: (e) => e.has_minimum_commitment },
    { label: "Dispute Process", get: (e) => e.has_dispute_process },
  ],
  confidentiality: [
    { label: "Broad Definition", get: (e) => e.has_broad_definition },
    { label: "Standard Exclusions", get: (e) => e.has_standard_exclusions },
    { label: "Duration Specified", get: (e) => e.has_duration },
    { label: "Permitted Disclosures", get: (e) => e.has_permitted_disclosures },
    { label: "Return/Destroy", get: (e) => e.has_return_or_destroy },
    { label: "Residuals Clause", get: (e) => e.has_residuals_clause },
    { label: "Injunctive Relief", get: (e) => e.has_injunctive_relief },
    { label: "Mutual", get: (e) => e.is_mutual },
  ],
  ip: [
    { label: "Customer Owns Deliverables", get: (e) => e.has_customer_owns_deliverables },
    { label: "Provider Owns Deliverables", get: (e) => e.has_provider_owns_deliverables },
    { label: "Pre-Existing IP Carveout", get: (e) => e.has_pre_existing_ip_carveout },
    { label: "Work for Hire", get: (e) => e.has_work_for_hire },
    { label: "IP Assignment", get: (e) => e.has_ip_assignment },
    { label: "License Grant", get: (e) => e.has_license_grant },
    { label: "Feedback Clause", get: (e) => e.has_feedback_clause },
    { label: "Source Code Escrow", get: (e) => e.has_source_code_escrow },
    { label: "Non-Compete", get: (e) => e.has_non_compete },
  ],
  governing_law: [
    { label: "Governing Law", get: (e) => e.has_governing_law },
    { label: "Jurisdiction", get: (e) => e.governing_law_jurisdiction || "—" },
    { label: "Venue Selection", get: (e) => e.has_venue_selection },
    { label: "Arbitration", get: (e) => e.has_arbitration },
    { label: "Jury Waiver", get: (e) => e.has_jury_waiver },
    { label: "Class Action Waiver", get: (e) => e.has_class_action_waiver },
    { label: "Prevailing Party Fees", get: (e) => e.has_prevailing_party_fees },
  ],
};

function renderExtraction(ext, clauseType) {
  const grid = $("extractionGrid");
  if (!ext) {
    grid.innerHTML = '<div class="extraction-item"><div class="extraction-value">Extraction failed</div></div>';
    return;
  }

  const fieldDefs = EXTRACTION_FIELDS[clauseType] || EXTRACTION_FIELDS.liability;
  const fields = fieldDefs.map((f) => ({ label: f.label, value: f.get(ext) }));
  // Always add confidence at the end
  fields.push({
    label: "Confidence",
    value: ext.extraction_confidence != null ? (ext.extraction_confidence * 100).toFixed(0) + "%" : "—",
  });

  grid.innerHTML = fields.map((f) => {
    const isBoolean = typeof f.value === "boolean";
    const displayVal = isBoolean ? (f.value ? "Yes" : "No") : f.value;
    const valClass = isBoolean ? (f.value ? "true" : "false") : "";
    return `
      <div class="extraction-item">
        <div class="extraction-label">${escHtml(f.label)}</div>
        <div class="extraction-value ${valClass}">${escHtml(String(displayVal))}</div>
      </div>
    `;
  }).join("");
}

// ── Per-category field labels + user value getters for distribution bars ──
const DISTRIBUTION_FIELDS = {
  liability: {
    labels: { has_cap: "Liability Cap", is_mutual: "Mutual Limitation", has_carve_outs: "Carve-Outs", consequential_excluded: "Consequential Excluded", has_indemnification: "Indemnification", has_warranty_disclaimer: "Warranty Disclaimer" },
    getUserVal: (ext, field) => {
      if (field === "has_cap") return ext?.liability_cap?.has_cap;
      if (field === "consequential_excluded") return ext?.consequential_damages?.excluded;
      return ext?.[field];
    },
  },
  termination: {
    labels: { has_termination_for_cause: "Termination for Cause", has_termination_for_convenience: "For Convenience", has_cure_period: "Cure Period", has_notice_period: "Notice Period", has_auto_renewal: "Auto-Renewal", has_survival_clause: "Survival Clause", has_post_termination_obligations: "Post-Termination Obligations", has_termination_fee: "Termination Fee" },
    getUserVal: (ext, field) => {
      if (field === "has_cure_period") return ext?.cure_period?.has_cure_period;
      if (field === "has_notice_period") return ext?.notice_period?.has_notice_period;
      return ext?.[field];
    },
  },
  payment: {
    labels: { has_payment_terms: "Payment Terms", has_late_fee: "Late Fee", has_price_escalation: "Price Escalation", has_non_refundable: "Non-Refundable", has_minimum_commitment: "Minimum Commitment", has_dispute_process: "Dispute Process", has_right_of_setoff: "Right of Setoff" },
    getUserVal: (ext, field) => {
      if (field === "has_late_fee") return ext?.late_fee?.has_late_fee;
      return ext?.[field];
    },
  },
  confidentiality: {
    labels: { has_broad_definition: "Broad Definition", has_standard_exclusions: "Standard Exclusions", has_duration: "Duration Specified", has_permitted_disclosures: "Permitted Disclosures", has_return_or_destroy: "Return/Destroy", has_residuals_clause: "Residuals Clause", has_injunctive_relief: "Injunctive Relief", is_mutual: "Mutual" },
    getUserVal: (ext, field) => ext?.[field],
  },
  ip: {
    labels: { has_customer_owns_deliverables: "Customer Owns Deliverables", has_provider_owns_deliverables: "Provider Owns Deliverables", has_pre_existing_ip_carveout: "Pre-Existing IP Carveout", has_work_for_hire: "Work for Hire", has_ip_assignment: "IP Assignment", has_license_grant: "License Grant", has_feedback_clause: "Feedback Clause", has_source_code_escrow: "Source Code Escrow", has_non_compete: "Non-Compete" },
    getUserVal: (ext, field) => ext?.[field],
  },
  governing_law: {
    labels: { has_governing_law: "Governing Law", has_venue_selection: "Venue Selection", has_arbitration: "Arbitration", has_jury_waiver: "Jury Waiver", has_class_action_waiver: "Class Action Waiver", has_prevailing_party_fees: "Prevailing Party Fees" },
    getUserVal: (ext, field) => ext?.[field],
  },
};

function renderDistributions(dists, userExt, percentiles, clauseType) {
  const container = $("distributionBars");
  const config = DISTRIBUTION_FIELDS[clauseType] || DISTRIBUTION_FIELDS.liability;
  const fieldLabels = config.labels;
  const getUserVal = config.getUserVal;

  const rows = Object.entries(dists)
    .filter(([k, v]) => v.total > 0 && !v.value_counts?.length && fieldLabels[k])
    .map(([fieldName, dist]) => {
      const userVal = getUserVal(userExt, fieldName);
      const pct = dist.true_pct;
      const userIndicator = userVal === true
        ? '<span class="dist-user-indicator has">You have this</span>'
        : userVal === false
        ? '<span class="dist-user-indicator lacks">You lack this</span>'
        : '';

      return `
        <div class="dist-row">
          <div class="dist-label">${fieldLabels[fieldName] || fieldName}</div>
          <div class="dist-bar-wrap">
            <div class="dist-bar-fill market" style="width: ${Math.max(pct, 3)}%">${pct.toFixed(0)}%</div>
          </div>
          <div class="dist-pct">${dist.true_count}/${dist.total}</div>
          ${userIndicator}
        </div>
      `;
    });

  container.innerHTML = rows.join("");
}

function renderCitedExamples(examples) {
  const container = $("citedExamples");
  if (!examples.length) {
    container.innerHTML = '<p style="color:var(--text-muted)">No cited examples available.</p>';
    return;
  }

  container.innerHTML = examples.map((ex) => {
    const simPct = (ex.similarity * 100).toFixed(1);
    const link = ex.exhibit_url
      ? `<a class="cited-link" href="${escHtml(ex.exhibit_url)}" target="_blank" rel="noopener">View SEC Filing &rarr;</a>`
      : '';

    return `
      <div class="cited-example">
        <div class="cited-header">
          <span class="cited-company">${escHtml(ex.company || ex.contract_id)}</span>
          <div class="cited-meta">
            ${ex.filed_date ? `<span>${escHtml(ex.filed_date)}</span>` : ''}
            <span class="cited-sim">${simPct}% match</span>
          </div>
        </div>
        <div class="cited-snippet">${escHtml(ex.text_snippet)}</div>
        ${link}
      </div>
    `;
  }).join("");
}

function renderRedlines(redline) {
  $("redlineSummary").textContent = redline.summary || "";
  const container = $("redlineSuggestions");

  if (!redline.suggestions.length) {
    container.innerHTML = '<p style="color:var(--text-muted)">No redline suggestions. Your clause aligns with market norms.</p>';
    return;
  }

  container.innerHTML = redline.suggestions.map((s, i) => `
    <div class="redline-item ${s.priority}">
      <div class="redline-header">
        <span class="redline-priority ${s.priority}">${escHtml(s.priority)}</span>
        <span class="redline-risk">${escHtml(s.risk_addressed)}</span>
        <button class="btn-copy-redline" data-idx="${i}" title="Copy proposed text">Copy</button>
      </div>
      <div class="redline-diff">
        <div class="redline-diff-label">Original</div>
        <div class="redline-original">${escHtml(s.original_text)}</div>
        <div class="redline-diff-label">Proposed</div>
        <div class="redline-proposed">${escHtml(s.proposed_text)}</div>
      </div>
      <div class="redline-justification">${escHtml(s.justification)}</div>
      ${s.market_citation ? `<div class="redline-citation">${escHtml(s.market_citation)}</div>` : ''}
    </div>
  `).join("");

  // Wire copy buttons (after innerHTML is set)
  container.querySelectorAll(".btn-copy-redline").forEach((btn) => {
    btn.addEventListener("click", () => {
      const idx = parseInt(btn.dataset.idx, 10);
      const text = redline.suggestions[idx]?.proposed_text || "";
      navigator.clipboard.writeText(text).then(() => {
        btn.textContent = "Copied!";
        setTimeout(() => { btn.textContent = "Copy"; }, 1500);
      }).catch(() => {
        btn.textContent = "Error";
      });
    });
  });
}
