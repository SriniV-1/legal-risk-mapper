import { useEffect, useRef } from "react";
import { Link } from "react-router-dom";

const STATS = [
  { value: 116,   decimals: 0, label: "EDGAR Contracts" },
  { value: 18001, decimals: 0, label: "Clause Chunks" },
  { value: 0.965, decimals: 3, label: "Avg Detection F1" },
  { value: 6,     decimals: 0, label: "Clause Categories" },
];

const FACULTIES = [
  {
    no: "01", kicker: "ML Risk Classification", title: "Five-category risk scoring",
    body: "An ensemble of five independent logistic-regression models over MiniLM-L6 sentence embeddings — not a general-purpose LLM. Detects Liability, Financial, Privacy, Compliance, and Contractual-Ambiguity risk with per-category severity and source attribution.",
    measure: "0.965 avg detection F1",
  },
  {
    no: "02", kicker: "Structured Extraction", title: "Field-level parsing, grounded",
    body: "Each of six clause types has a dedicated schema whose every field carries a verbatim source quote, enforced in the prompt and validated at the schema level. Measured per-field F1 against hand-labeled evaluation sets.",
    measure: "6 clause types",
  },
  {
    no: "03", kicker: "Market Benchmarking", title: "EDGAR percentile ranking",
    body: "pgvector retrieves the most similar clauses from 18,001 chunks of real SEC EX-10 filings, then computes field distributions so your clause is placed against the market rather than against opinion.",
    measure: "MRR@5 = 0.917",
  },
  {
    no: "04", kicker: "Grounded Redlines", title: "Citation-backed edits",
    body: "Every suggestion must cite a specific market statistic drawn from the corpus — “appears in 81% of similar contracts” — with an exact-quote original and a concrete proposed replacement traceable to a filed document.",
    measure: "Cites real filings",
  },
];

const PROCEDURE = [
  { n: "i",   title: "Paste or upload", body: "Submit any clause as text or a .pdf, .txt, or .md file. The clause type is auto-detected." },
  { n: "ii",  title: "Risk analysis",   body: "The ML classifier scores five risk categories with severity ratings, confidence, and the exact flagged text." },
  { n: "iii", title: "Market benchmark", body: "pgvector retrieves similar clauses from 116 EDGAR contracts and computes field distributions against the market." },
  { n: "iv",  title: "Redline",          body: "The model returns two to four edits, each citing a specific market statistic from a real SEC filing." },
];

const APPENDIX = [
  { cat: "Privacy / Data Risk",   det: "1.000", sev: "1.000", cv: "0.994" },
  { cat: "Financial Risk",        det: "0.980", sev: "0.984", cv: "0.955" },
  { cat: "Contractual Ambiguity", det: "0.977", sev: "0.980", cv: "0.957" },
  { cat: "Liability Risk",        det: "0.941", sev: "0.830", cv: "0.959" },
  { cat: "Compliance Risk",       det: "0.927", sev: "0.966", cv: "0.979" },
];

const Arrow = () => (
  <svg viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2" strokeLinecap="round" strokeLinejoin="round">
    <line x1="5" y1="12" x2="19" y2="12" /><polyline points="12 5 19 12 12 19" />
  </svg>
);

/* Wax-seal monogram — an engraved court stamp, the publication's signature mark. */
const Seal = ({ className = "" }) => (
  <span className={`seal ${className}`} aria-hidden="true">
    <svg viewBox="0 0 120 120">
      <defs>
        <path id="seal-arc-top" d="M60 60 m-44 0 a44 44 0 0 1 88 0" />
        <path id="seal-arc-bot" d="M60 60 m44 0 a44 44 0 0 1 -88 0" />
      </defs>
      <circle cx="60" cy="60" r="56" className="seal-ring" />
      <circle cx="60" cy="60" r="47" className="seal-ring thin" />
      <text className="seal-text"><textPath href="#seal-arc-top" startOffset="50%">AUTOMATED LEGAL</textPath></text>
      <text className="seal-text"><textPath href="#seal-arc-bot" startOffset="50%">RISK · MONITOR</textPath></text>
      <text x="60" y="74" className="seal-mono">A</text>
    </svg>
  </span>
);

function useCountUp(ref, target, decimals, duration = 1300) {
  useEffect(() => {
    const el = ref.current;
    if (!el) return;
    const start = performance.now();
    function step(now) {
      const p = Math.min((now - start) / duration, 1);
      const eased = 1 - Math.pow(1 - p, 3);
      el.textContent = (target * eased).toFixed(decimals);
      if (p < 1) requestAnimationFrame(step);
    }
    requestAnimationFrame(step);
  }, []); // eslint-disable-line react-hooks/exhaustive-deps
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

/* Reveal sections as they scroll into view (graceful: everything shows if unsupported). */
function useReveal() {
  useEffect(() => {
    const els = Array.from(document.querySelectorAll(".obs"));
    if (!("IntersectionObserver" in window)) {
      els.forEach((el) => el.classList.add("in"));
      return;
    }
    const io = new IntersectionObserver(
      (entries) => entries.forEach((e) => {
        if (e.isIntersecting) { e.target.classList.add("in"); io.unobserve(e.target); }
      }),
      { threshold: 0.16, rootMargin: "0px 0px -8% 0px" }
    );
    els.forEach((el) => io.observe(el));
    return () => io.disconnect();
  }, []);
}

export default function Landing() {
  useReveal();

  return (
    <div className="bs">
      {/* ── Masthead ── */}
      <header className="mast">
        <a href="/" className="mast-mark">ALRM</a>
        <span className="mast-rule" />
        <span className="mast-sub">The Automated Legal Risk Monitor</span>
        <span className="mast-spacer" />
        <span className="mast-dateline">Vol. I · No. 01</span>
        <Link to="/app" className="mast-cta">Launch the Monitor</Link>
      </header>

      <div className="bs-page">
        {/* ── Front page ── */}
        <section className="frontpage">
          <div className="dateline-row reveal r1">
            <span>Forensic Contract Review</span>
            <span>Established MMXXVI</span>
            <span>A Portfolio Instrument · Not Legal Advice</span>
          </div>

          <h1 className="headline reveal r2">
            <span className="ln"><span>Know the risk</span></span>
            <span className="ln"><span>before you <em>sign.</em></span></span>
          </h1>

          <div className="hero-grid">
            <div className="lede-col reveal r3">
              <p className="standfirst">
                <span className="dropcap">A</span>
                machine-read examination of SaaS contract clauses, weighed against 116 real
                SEC EDGAR filings. Structured extraction, market benchmarking, and grounded
                redlines — each finding traceable to a filed document, returned in seconds.
              </p>
              <div className="byline">
                <Link to="/app" className="btn-stamp">Analyze a Clause <Arrow /></Link>
                <span className="filed">
                  Filed under — Liability · Privacy · Financial · Compliance · Ambiguity
                </span>
              </div>
            </div>

            {/* Forensic specimen */}
            <aside className="exhibit reveal r4">
              <Seal className="exhibit-seal" />
              <span className="exhibit-tab"><span className="tab-rec" />Exhibit A — Liability Clause</span>
              <div className="exhibit-doc is-analyzing">
                <div className="scanline" aria-hidden="true" />
                <div className="exhibit-meta">
                  <span>SaaS MSA · § 9.2</span>
                  <span className="elive"><span className="elive-dot" />Live analysis</span>
                </div>
                <p className="exhibit-clause">
                  Company's aggregate liability shall{" "}
                  <span className="mark-high" data-note="High · 6th-percentile cap">not exceed $5,000 regardless of the form of action</span>,
                  and Company may{" "}
                  <span className="mark-med" data-note="Medium · unilateral change">modify these terms at any time without notice</span> to Customer.
                </p>
                <div className="exhibit-margin">
                  <span className="margin-tag">High · Liability</span>
                  <span>Cap sits in the 6th percentile of the market — far below the median fees-paid limit.</span>
                </div>
                <div className="redline-strip">
                  <span className="rl-cut">shall not exceed $5,000 regardless of damages</span>{" "}
                  <span className="rl-add">→ shall not exceed fees paid in the prior 12 months</span>
                </div>
                <div className="emeter">
                  <span className="emeter-label">Risk confidence</span>
                  <div className="emeter-track"><i /></div>
                  <span className="emeter-val">82%</span>
                </div>
              </div>
            </aside>
          </div>

          {/* Ledger */}
          <div className="ledger reveal r5">
            {STATS.map((s) => <StatItem key={s.label} {...s} />)}
          </div>
        </section>

        {/* ── § I — Faculties ── */}
        <section className="article obs">
          <div className="art-head">
            <span className="art-sec">§ I</span>
            <h2 className="art-title">The four faculties</h2>
            <span className="art-kicker">What it does</span>
          </div>
          <div className="faculties">
            {FACULTIES.map((f) => (
              <article className="faculty" key={f.no}>
                <div className="fac-no">{f.no}</div>
                <div>
                  <div className="fac-kicker">{f.kicker}</div>
                  <h3 className="fac-title">{f.title}</h3>
                  <p className="fac-body">{f.body}</p>
                  <span className="fac-measure">{f.measure}</span>
                </div>
              </article>
            ))}
          </div>
        </section>

        {/* ── § II — Procedure ── */}
        <section className="article obs">
          <div className="art-head">
            <span className="art-sec">§ II</span>
            <h2 className="art-title">The procedure</h2>
            <span className="art-kicker">How it works</span>
          </div>
          <ol className="procedure">
            {PROCEDURE.map((s) => (
              <li className="step" key={s.n}>
                <div className="step-no">{s.n} —</div>
                <div className="step-title">{s.title}</div>
                <p className="step-body">{s.body}</p>
              </li>
            ))}
          </ol>
        </section>

        {/* ── § III — Statistical appendix ── */}
        <section className="article obs">
          <div className="art-head">
            <span className="art-sec">§ III</span>
            <h2 className="art-title">Statistical appendix</h2>
            <span className="art-kicker">Risk classifier · 5-fold CV</span>
          </div>
          <div className="appendix-wrap">
            <table className="appendix">
              <caption>Table 1 — Per-category performance over 617 labeled clauses.</caption>
              <thead>
                <tr>
                  <th>Risk Category</th>
                  <th>Detection F1</th>
                  <th>Severity Macro F1</th>
                  <th>CV Score</th>
                </tr>
              </thead>
              <tbody>
                {APPENDIX.map((r) => (
                  <tr key={r.cat}>
                    <td>{r.cat}</td>
                    <td><span className="fig-strong">{r.det}</span></td>
                    <td>{r.sev}</td>
                    <td>{r.cv}</td>
                  </tr>
                ))}
                <tr className="row-avg">
                  <td>Average</td>
                  <td><span className="fig-strong">0.965</span></td>
                  <td>0.952</td>
                  <td>—</td>
                </tr>
              </tbody>
            </table>
          </div>
        </section>

        {/* ── Colophon ── */}
        <section className="colophon obs">
          <div className="colophon-head">
            Read the fine print<br /><em>before it reads you.</em>
          </div>
          <div className="colophon-aside">
            <Seal className="colophon-seal" />
            <Link to="/app" className="btn-stamp">Open the Tool <Arrow /></Link>
            <p className="set-in">
              Set in Fraunces &amp; Newsreader.<br />
              Corpus: 116 SEC EDGAR EX-10 filings.<br />
              Retrieval: pgvector · MRR@5 0.917.
            </p>
          </div>
        </section>
      </div>

      {/* ── Footer ── */}
      <footer className="bs-foot">
        <div className="bs-foot-inner">
          <span>ALRM — Automated Legal Risk Monitor · Portfolio project · Not legal advice.</span>
          <span>
            <a href="https://github.com/SriniV-1/legal-risk-mapper" target="_blank" rel="noopener noreferrer">GitHub</a>
            &nbsp;&nbsp;·&nbsp;&nbsp;Always consult a licensed attorney.
          </span>
        </div>
      </footer>
    </div>
  );
}
