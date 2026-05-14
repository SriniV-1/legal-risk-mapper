import { useEffect, useRef } from "react";
import { Link } from "react-router-dom";

const STATS = [
  { value: 116,    decimals: 0, label: "EDGAR Contracts" },
  { value: 18001,  decimals: 0, label: "Clause Chunks" },
  { value: 0.965,  decimals: 3, label: "Avg Detection F1" },
  { value: 6,      decimals: 0, label: "Clause Categories" },
];

function useCountUp(ref, target, decimals, duration = 1200) {
  useEffect(() => {
    const el = ref.current;
    if (!el) return;
    const start = performance.now();
    const from = 0;
    function step(now) {
      const elapsed = now - start;
      const progress = Math.min(elapsed / duration, 1);
      const eased = 1 - Math.pow(1 - progress, 3);
      const current = from + (target - from) * eased;
      el.textContent = current.toFixed(decimals);
      if (progress < 1) requestAnimationFrame(step);
    }
    requestAnimationFrame(step);
  }, []);
}

function StatItem({ value, decimals, label }) {
  const ref = useRef(null);
  useCountUp(ref, value, decimals);
  return (
    <div>
      <span ref={ref} className="hs-n">{value.toFixed(decimals)}</span>
      <span className="hs-l">{label}</span>
    </div>
  );
}

export default function Landing() {
  return (
    <div style={{ minHeight: "100vh", fontFamily: "var(--sans)" }}>
      {/* NAV */}
      <nav className="landing-nav">
        <a href="/" className="nav-logo">ALRM</a>
        <div style={{ flex: 1 }} />
        <span className="nav-label">Automated Legal Risk Monitor</span>
        <Link to="/app" className="nav-cta">
          Launch App
          <svg width="13" height="13" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2" strokeLinecap="round" strokeLinejoin="round">
            <line x1="5" y1="12" x2="19" y2="12"/><polyline points="12 5 19 12 12 19"/>
          </svg>
        </Link>
      </nav>

      {/* HERO */}
      <section className="landing-hero" style={{ paddingTop: "100px" }}>
        <div className="section-wrap">
          <div className="hero-inner">
            <div>
              <div className="hero-eyebrow">Portfolio Project · Not Legal Advice</div>
              <h1>Know the risk<br />before you <em>sign.</em></h1>
              <p className="hero-lead">
                ML-powered analysis of SaaS contract clauses against 116 real SEC EDGAR filings.
                Structured extraction, market benchmarking, and grounded redlines — in seconds.
              </p>
              <Link to="/app" className="btn-hero">
                Analyze a Contract
                <svg width="15" height="15" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2" strokeLinecap="round" strokeLinejoin="round">
                  <line x1="5" y1="12" x2="19" y2="12"/><polyline points="12 5 19 12 12 19"/>
                </svg>
              </Link>
              <div className="hero-stats">
                {STATS.map((s) => (
                  <StatItem key={s.label} {...s} />
                ))}
              </div>
            </div>

            {/* Preview widget */}
            <div>
              <div className="preview-widget">
                <div className="pw-bar">
                  <div className="pw-dot" />
                  <div className="pw-dot" />
                  <div className="pw-dot" />
                  <span className="pw-bar-title">Risk Analysis · Liability Clause</span>
                </div>
                <div className="pw-section-head">
                  <svg width="13" height="13" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2" strokeLinecap="round" strokeLinejoin="round">
                    <path d="M12 22s8-4 8-10V5l-8-3-8 3v7c0 6 8 10 8 10z"/>
                    <path d="m9 12 2 2 4-4"/>
                  </svg>
                  Risks Detected
                  <span className="pw-badge high">3 Risks Found</span>
                </div>
                <div className="pw-risk-item">
                  <div className="pw-risk-header">
                    <span className="pw-sev high">High</span>
                    <span className="pw-risk-type">Liability Risk</span>
                  </div>
                  <div className="pw-snippet">"Company's aggregate liability shall not exceed $5,000 regardless of…"</div>
                  <div className="pw-conf">
                    <span>Confidence</span>
                    <div className="pw-track"><div className="pw-fill" style={{ width: "82%" }} /></div>
                    <span>82%</span>
                  </div>
                </div>
                <div className="pw-risk-item">
                  <div className="pw-risk-header">
                    <span className="pw-sev med">Medium</span>
                    <span className="pw-risk-type">Contractual Ambiguity</span>
                  </div>
                  <div className="pw-snippet">"Company may modify these terms at any time without notice…"</div>
                  <div className="pw-conf">
                    <span>Confidence</span>
                    <div className="pw-track"><div className="pw-fill" style={{ width: "61%" }} /></div>
                    <span>61%</span>
                  </div>
                </div>
                <div className="pw-redline-section">
                  <div className="pw-redline-head">
                    <svg width="12" height="12" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2" strokeLinecap="round" strokeLinejoin="round">
                      <circle cx="18" cy="18" r="3"/><circle cx="6" cy="6" r="3"/>
                      <path d="M13 6h3a2 2 0 0 1 2 2v7"/><line x1="6" y1="9" x2="6" y2="21"/>
                    </svg>
                    Redline Suggestion
                    <span className="pw-badge high" style={{ marginLeft: "auto" }}>High Priority</span>
                  </div>
                  <div className="pw-diff-orig">— "shall not exceed $5,000 regardless of damages"</div>
                  <div className="pw-diff-new">+ "shall not exceed fees paid in prior 12 months"</div>
                </div>
              </div>
            </div>
          </div>
        </div>
      </section>

      {/* CAPABILITIES */}
      <section className="capabilities-section">
        <div className="section-wrap">
          <div className="section-eyebrow">What it does</div>
          <h2>Four layers of <em>contract intelligence</em></h2>
          <div className="cap-layout">
            {/* Featured */}
            <div className="cap-card featured">
              <div className="cap-icon">
                <svg width="18" height="18" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2" strokeLinecap="round" strokeLinejoin="round">
                  <path d="M12 22s8-4 8-10V5l-8-3-8 3v7c0 6 8 10 8 10z"/>
                </svg>
              </div>
              <div className="cap-num">01 — ML Risk Classification</div>
              <h3>Five-Category Risk Scoring</h3>
              <p className="cap-desc">
                Trained on 617 labeled clauses using all-MiniLM-L6-v2 embeddings and logistic regression.
                Detects Liability, Financial, Privacy, Compliance, and Contractual Ambiguity risks with severity
                scores and source attribution. Replaces brittle regex rules with a model that generalizes to new language.
              </p>
              <span className="cap-badge">0.965 Avg Detection F1</span>
            </div>

            <div className="cap-right-col">
              <div className="cap-card">
                <div className="cap-icon">
                  <svg width="18" height="18" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2" strokeLinecap="round" strokeLinejoin="round">
                    <polyline points="22 12 18 12 15 21 9 3 6 12 2 12"/>
                  </svg>
                </div>
                <div className="cap-num">02 — Structured Extraction</div>
                <h3>Field-Level Parsing</h3>
                <p className="cap-desc">LLM extracts 7–9 structured fields per clause type (liability caps, cure periods, governing jurisdiction, etc.). Results compared to market corpus.</p>
                <span className="cap-badge">6 Clause Types</span>
              </div>
              <div className="cap-card">
                <div className="cap-icon">
                  <svg width="18" height="18" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2" strokeLinecap="round" strokeLinejoin="round">
                    <line x1="18" y1="20" x2="18" y2="10"/><line x1="12" y1="20" x2="12" y2="4"/>
                    <line x1="6" y1="20" x2="6" y2="14"/>
                  </svg>
                </div>
                <div className="cap-num">03 — Market Benchmarking</div>
                <h3>SEC EDGAR Percentile Ranking</h3>
                <p className="cap-desc">pgvector search retrieves the 20 most similar clauses from real EDGAR filings. Field-level distributions show where your clause stands.</p>
                <span className="cap-badge">MRR@5 = 0.917</span>
              </div>
            </div>

            <div className="cap-card cap-wide">
              <div>
                <div className="cap-icon">
                  <svg width="18" height="18" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2" strokeLinecap="round" strokeLinejoin="round">
                    <circle cx="18" cy="18" r="3"/><circle cx="6" cy="6" r="3"/>
                    <path d="M13 6h3a2 2 0 0 1 2 2v7"/><line x1="6" y1="9" x2="6" y2="21"/>
                  </svg>
                </div>
              </div>
              <div style={{ flex: 1 }}>
                <div className="cap-num">04 — Grounded Redlines</div>
                <h3>Citation-Backed Edit Suggestions</h3>
                <p className="cap-desc" style={{ maxWidth: "80ch" }}>
                  Every redline suggestion cites specific market statistics and real SEC filings — not LLM opinion.
                  Original vs. proposed diff view with priority scoring and risk labels. Each suggestion is traceable to a real contract.
                </p>
              </div>
              <div>
                <span className="cap-badge">Cites Real Filings</span>
              </div>
            </div>
          </div>
        </div>
      </section>

      {/* PIPELINE */}
      <section className="pipeline-section">
        <div className="section-wrap">
          <div className="section-eyebrow">How it works</div>
          <h2>From clause to redline <em>in four steps</em></h2>
          <div className="pipeline-grid">
            <div className="pipe-card">
              <div className="pipe-number">1</div>
              <div className="pipe-icon">
                <svg width="16" height="16" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2" strokeLinecap="round" strokeLinejoin="round">
                  <path d="M21 15v4a2 2 0 0 1-2 2H5a2 2 0 0 1-2-2v-4"/>
                  <polyline points="17 8 12 3 7 8"/>
                  <line x1="12" y1="3" x2="12" y2="15"/>
                </svg>
              </div>
              <div className="pipe-title">Paste or Upload</div>
              <p className="pipe-desc">Submit any clause as text or upload a .pdf, .txt, or .md file. Clause type is auto-detected.</p>
            </div>
            <div className="pipe-card">
              <div className="pipe-number">2</div>
              <div className="pipe-icon">
                <svg width="16" height="16" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2" strokeLinecap="round" strokeLinejoin="round">
                  <rect x="4" y="4" width="16" height="16" rx="2" ry="2"/>
                  <rect x="9" y="9" width="6" height="6"/>
                  <line x1="9" y1="2" x2="9" y2="4"/>
                  <line x1="15" y1="2" x2="15" y2="4"/>
                  <line x1="9" y1="20" x2="9" y2="22"/>
                  <line x1="15" y1="20" x2="15" y2="22"/>
                  <line x1="20" y1="9" x2="22" y2="9"/>
                  <line x1="20" y1="14" x2="22" y2="14"/>
                  <line x1="2" y1="9" x2="4" y2="9"/>
                  <line x1="2" y1="14" x2="4" y2="14"/>
                </svg>
              </div>
              <div className="pipe-title">Risk Analysis</div>
              <p className="pipe-desc">ML classifier scores across five risk categories with severity ratings, confidence scores, and flagged text.</p>
            </div>
            <div className="pipe-card">
              <div className="pipe-number">3</div>
              <div className="pipe-icon">
                <svg width="16" height="16" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2" strokeLinecap="round" strokeLinejoin="round">
                  <ellipse cx="12" cy="5" rx="9" ry="3"/>
                  <path d="M21 12c0 1.66-4 3-9 3s-9-1.34-9-3"/>
                  <path d="M3 5v14c0 1.66 4 3 9 3s9-1.34 9-3V5"/>
                </svg>
              </div>
              <div className="pipe-title">Market Benchmark</div>
              <p className="pipe-desc">pgvector search retrieves similar clauses from 116 EDGAR contracts. Field distributions computed against the market.</p>
            </div>
            <div className="pipe-card">
              <div className="pipe-number">4</div>
              <div className="pipe-icon">
                <svg width="16" height="16" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2" strokeLinecap="round" strokeLinejoin="round">
                  <path d="M12 20h9"/>
                  <path d="M16.5 3.5a2.121 2.121 0 0 1 3 3L7 19l-4 1 1-4L16.5 3.5z"/>
                </svg>
              </div>
              <div className="pipe-title">Redline Generation</div>
              <p className="pipe-desc">LLM generates 2–4 edit suggestions, each citing specific market statistics from real SEC filings.</p>
            </div>
          </div>
        </div>
      </section>

      {/* CTA */}
      <section className="cta-section">
        <div className="section-wrap">
          <div className="cta-inner">
            <div className="cta-text">Ready to analyze<br /><em>your first clause?</em></div>
            <Link to="/app" className="btn-hero">
              Open the Tool
              <svg width="15" height="15" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2" strokeLinecap="round" strokeLinejoin="round">
                <line x1="5" y1="12" x2="19" y2="12"/><polyline points="12 5 19 12 12 19"/>
              </svg>
            </Link>
          </div>
        </div>
      </section>

      {/* FOOTER */}
      <footer>
        <div className="footer-inner">
          <span className="footer-text">ALRM — Automated Legal Risk Monitor. Portfolio project. Not legal advice.</span>
          <span className="footer-text">
            <a href="https://github.com/SriniV-1/legal-risk-mapper" target="_blank" rel="noopener noreferrer">GitHub</a>
            &nbsp;&nbsp;Always consult a licensed attorney for legal decisions.
          </span>
        </div>
      </footer>
    </div>
  );
}
