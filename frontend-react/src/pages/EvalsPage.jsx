import Masthead from "../components/Masthead.jsx";
import {
  ResponsiveContainer, BarChart, Bar, XAxis, YAxis, CartesianGrid,
  Tooltip, ReferenceLine, LabelList, Cell,
} from "recharts";

/* ── All data below is measured, from the repo's own eval harness ──
   README tables + data/e2e_eval_results.json + data/classifier_eval.json.
   Regeneration commands are printed at the foot of the page. */

const EXTRACTION = [
  { type: "Governing Law",   f1: 0.971, grounding: 1.000, success: 100,  n: 35 },
  { type: "Payment",         f1: 0.941, grounding: 1.000, success: 100,  n: 35 },
  { type: "IP",              f1: 0.921, grounding: 0.996, success: 100,  n: 35 },
  { type: "Confidentiality", f1: 0.920, grounding: 0.953, success: 100,  n: 35 },
  { type: "Termination",     f1: 0.881, grounding: 0.973, success: 94.3, n: 35 },
  { type: "Liability",       f1: 0.762, grounding: 0.975, success: 97.6, n: 42 },
];

const CLASSIFIER = [
  { cat: "Privacy / Data",  det: 1.000, sev: 1.000, cv: 0.994 },
  { cat: "Financial",       det: 0.980, sev: 0.984, cv: 0.955 },
  { cat: "Ambiguity",       det: 0.977, sev: 0.980, cv: 0.957 },
  { cat: "Liability",       det: 0.941, sev: 0.830, cv: 0.959 },
  { cat: "Compliance",      det: 0.927, sev: 0.966, cv: 0.979 },
];

const E2E = [
  { id: "warranty_disclaimer", label: "AS-IS warranty disclaimer",  t: 48.67 },
  { id: "minimal",             label: "Minimal liability language", t: 52.2 },
  { id: "mixed_indemnification", label: "Mixed indemnification",    t: 53.4 },
  { id: "no_cap",              label: "Indemnification, no cap",    t: 54.22 },
  { id: "consequential_only",  label: "Consequential exclusion",    t: 57.13 },
  { id: "complex_cap",         label: "Complex multi-formula cap",  t: 58.35 },
  { id: "weak_onesided",       label: "Weak one-sided clause",      t: 59.6 },
  { id: "strong_mutual",       label: "Strong mutual w/ carve-outs", t: 76.22 },
];

const COVERAGE = [
  { type: "Governing Law",   chunks: 874,   extracted: 708, pct: "81.0%" },
  { type: "Liability",       chunks: 1999,  extracted: 981, pct: "49.1%" },
  { type: "Confidentiality", chunks: 2423,  extracted: 990, pct: "40.9%" },
  { type: "IP",              chunks: 656,   extracted: 18,  pct: "2.7%" },
  { type: "Termination",     chunks: 1434,  extracted: 11,  pct: "0.8%" },
  { type: "Payment",         chunks: 2156,  extracted: 15,  pct: "0.7%" },
];

const INK = "#8A2B2B";       /* oxblood — the redline */
const INK_2 = "#A8761B";     /* annotation amber */
const INK_3 = "#3E6B4A";     /* ledger green */
const RULE = "#C5B795";
const FAINT = "#8A7E66";

const axisFont = { fontFamily: "var(--mono)", fontSize: 10.5, fill: FAINT };

function PaperTooltip({ active, payload, label, fmt }) {
  if (!active || !payload?.length) return null;
  return (
    <div className="fig-tip">
      <div className="fig-tip-title">{label}</div>
      {payload.map((p) => (
        <div key={p.dataKey} className="fig-tip-row">
          <span className="fig-tip-swatch" style={{ background: p.color || p.fill }} />
          {p.name}<strong>{fmt ? fmt(p.value) : p.value}</strong>
        </div>
      ))}
    </div>
  );
}

export default function EvalsPage() {
  return (
    <div className="bs">
      <Masthead section="The Statistical Appendix" />
      <div className="bs-page">
        <section className="frontpage section-cover">
          <div className="dateline-row">
            <span>Every figure measured, none asserted</span>
            <span>Eval harness: scripts/ · data/eval/</span>
            <span>Hand-labeled ground truth</span>
          </div>
          <h1 className="headline headline-section">
            <span className="ln"><span>The numbers,</span></span>
            <span className="ln"><span>in <em>full.</em></span></span>
          </h1>
          <div className="ledger section-ledger">
            <div><span className="hs-n">0.965</span><span className="hs-l">Avg detection F1 · 5-fold CV</span></div>
            <div><span className="hs-n">0.917</span><span className="hs-l">Retrieval MRR@5</span></div>
            <div><span className="hs-n">0.987</span><span className="hs-l">Retrieval NDCG@5</span></div>
            <div><span className="hs-n">8/8</span><span className="hs-l">E2E scenarios pass</span></div>
          </div>
        </section>

        {/* ── Table I — Extraction ── */}
        <section className="article">
          <div className="art-head">
            <span className="art-sec">Fig. 1</span>
            <h2 className="art-title">Structured extraction, by clause type</h2>
            <span className="art-kicker">35–42 hand-labeled examples each</span>
          </div>
          <p className="fig-note">
            Core-field F1 against hand labels (bars), with each field's <em>grounding score</em> —
            the fraction of extracted values whose <code>source_text</code> is a verified substring
            of the input clause. Grounding below 1.0 means the model paraphrased where it should
            have quoted.
          </p>
          <div className="fig-frame">
            <ResponsiveContainer width="100%" height={290}>
              <BarChart data={EXTRACTION} layout="vertical" margin={{ left: 28, right: 48, top: 6, bottom: 4 }}>
                <CartesianGrid horizontal={false} stroke={RULE} strokeDasharray="1 3" />
                <XAxis type="number" domain={[0, 1]} tick={axisFont} stroke={RULE} />
                <YAxis type="category" dataKey="type" width={108} tick={{ ...axisFont, fontSize: 11 }} stroke={RULE} />
                <Tooltip content={<PaperTooltip fmt={(v) => Number(v).toFixed(3)} />} cursor={{ fill: "rgba(138,43,43,0.05)" }} />
                <Bar dataKey="f1" name="Core-field F1" fill={INK} barSize={13} radius={[0, 2, 2, 0]}>
                  <LabelList dataKey="f1" position="right" formatter={(v) => v.toFixed(3)} style={{ ...axisFont, fill: INK, fontWeight: 600 }} />
                </Bar>
                <Bar dataKey="grounding" name="Grounding score" fill={INK_2} barSize={6} radius={[0, 2, 2, 0]} />
              </BarChart>
            </ResponsiveContainer>
            <div className="fig-caption">Fig. 1 — Liability is the hardest schema (nested caps and carve-outs); its grounding stays at 0.975 even where F1 drops.</div>
          </div>
        </section>

        {/* ── Fig. 2 — Classifier ── */}
        <section className="article">
          <div className="art-head">
            <span className="art-sec">Fig. 2</span>
            <h2 className="art-title">Risk classifier, per category</h2>
            <span className="art-kicker">5 LogisticRegression models · MiniLM-L6 embeddings · 617 clauses</span>
          </div>
          <div className="fig-frame">
            <ResponsiveContainer width="100%" height={260}>
              <BarChart data={CLASSIFIER} margin={{ left: 4, right: 12, top: 14, bottom: 4 }}>
                <CartesianGrid vertical={false} stroke={RULE} strokeDasharray="1 3" />
                <XAxis dataKey="cat" tick={axisFont} stroke={RULE} interval={0} />
                <YAxis domain={[0.6, 1]} tick={axisFont} stroke={RULE} />
                <Tooltip content={<PaperTooltip fmt={(v) => Number(v).toFixed(3)} />} cursor={{ fill: "rgba(138,43,43,0.05)" }} />
                <ReferenceLine y={0.965} stroke={INK} strokeDasharray="4 3"
                  label={{ value: "avg 0.965", position: "insideTopRight", ...axisFont, fill: INK }} />
                <Bar dataKey="det" name="Detection F1" fill={INK} barSize={18} radius={[2, 2, 0, 0]} />
                <Bar dataKey="sev" name="Severity macro F1" fill={INK_2} barSize={18} radius={[2, 2, 0, 0]} />
                <Bar dataKey="cv" name="CV score" fill={INK_3} barSize={18} radius={[2, 2, 0, 0]} />
              </BarChart>
            </ResponsiveContainer>
            <div className="fig-caption">Fig. 2 — Detection vs. severity vs. cross-validation, per risk category. Trained ensemble, not an LLM call.</div>
          </div>
        </section>

        {/* ── Fig. 3 — Retrieval + E2E ── */}
        <section className="article">
          <div className="art-head">
            <span className="art-sec">Fig. 3</span>
            <h2 className="art-title">Retrieval &amp; the end-to-end run</h2>
            <span className="art-kicker">pgvector · IVFFlat · 18,001 chunks</span>
          </div>
          <div className="fig-cols">
            <div className="fig-side">
              <table className="appendix">
                <caption>Retrieval quality — scripts/eval_retrieval.py</caption>
                <tbody>
                  <tr><td>MRR@5</td><td><span className="fig-strong">0.917</span></td></tr>
                  <tr><td>NDCG@5</td><td><span className="fig-strong">0.987</span></td></tr>
                  <tr><td>Avg query latency</td><td><span className="fig-strong">0.243 s</span></td></tr>
                  <tr><td>Corpus</td><td>18,001 chunks · 116 contracts</td></tr>
                  <tr><td>Embeddings</td><td>MiniLM-L6 · 384-dim · cosine</td></tr>
                </tbody>
              </table>
            </div>
            <div className="fig-frame fig-grow">
              <ResponsiveContainer width="100%" height={250}>
                <BarChart data={E2E} layout="vertical" margin={{ left: 40, right: 44, top: 4, bottom: 4 }}>
                  <CartesianGrid horizontal={false} stroke={RULE} strokeDasharray="1 3" />
                  <XAxis type="number" tick={axisFont} stroke={RULE} unit="s" />
                  <YAxis type="category" dataKey="label" width={150} tick={{ ...axisFont, fontSize: 10 }} stroke={RULE} />
                  <Tooltip content={<PaperTooltip fmt={(v) => v + " s"} />} cursor={{ fill: "rgba(138,43,43,0.05)" }} />
                  <ReferenceLine x={57.5} stroke={FAINT} strokeDasharray="4 3"
                    label={{ value: "avg 57.5s", position: "insideBottomRight", ...axisFont }} />
                  <Bar dataKey="t" name="Benchmark + redline" barSize={11} radius={[0, 2, 2, 0]}>
                    {E2E.map((e) => <Cell key={e.id} fill={e.t > 70 ? INK : INK_3} />)}
                  </Bar>
                </BarChart>
              </ResponsiveContainer>
              <div className="fig-caption">Fig. 3 — Full benchmark + grounded-redline runs over 8 liability scenarios: 8/8 extraction success, every run citing 5 real filings.</div>
            </div>
          </div>
        </section>

        {/* ── Table II — Corpus coverage ── */}
        <section className="article">
          <div className="art-head">
            <span className="art-sec">Table II</span>
            <h2 className="art-title">Corpus extraction coverage</h2>
            <span className="art-kicker">SEC EDGAR EX-10 · 2018–2023</span>
          </div>
          <div className="appendix-wrap">
            <table className="appendix">
              <caption>Structured extractions stored per clause type (coverage grows as extraction jobs run).</caption>
              <thead><tr><th>Clause Type</th><th>Chunks</th><th>Extracted</th><th>Coverage</th></tr></thead>
              <tbody>
                {COVERAGE.map((r) => (
                  <tr key={r.type}>
                    <td>{r.type}</td>
                    <td>{r.chunks.toLocaleString()}</td>
                    <td>{r.extracted.toLocaleString()}</td>
                    <td><span className={parseFloat(r.pct) > 30 ? "fig-strong" : ""}>{r.pct}</span></td>
                  </tr>
                ))}
              </tbody>
            </table>
          </div>
        </section>

        <section className="colophon">
          <div className="colophon-head">Reproduce every figure<br /><em>from the repo.</em></div>
          <div className="colophon-aside">
            <div className="repro-cmds">
              <code>python -m backend.extraction.eval --eval-file data/eval/liability_eval.json</code>
              <code>python -m scripts.eval_retrieval</code>
              <code>python -m scripts.eval_classifier</code>
              <code>python -m scripts.eval_e2e</code>
            </div>
          </div>
        </section>
      </div>

      <footer className="bs-foot">
        <div className="bs-foot-inner">
          <span>ALRM — Statistical Appendix · all figures measured, none asserted.</span>
          <span><a href="https://github.com/SriniV-1/legal-risk-mapper" target="_blank" rel="noopener noreferrer">GitHub</a></span>
        </div>
      </footer>
    </div>
  );
}
