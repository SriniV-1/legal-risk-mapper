import { Link } from "react-router-dom";
import Masthead from "../components/Masthead.jsx";
import Dossier from "../components/Dossier.jsx";

/* The Prospectus — the 60-second read for someone evaluating the
   engineering. Problem, scale, hard parts, measured results, stack. */

const RESULTS = [
  { challenge: "Classify risk without leaning on an LLM's mood",
    solution: "Ensemble of 5 independent LogisticRegression models over MiniLM-L6 embeddings",
    figure: "0.965 avg detection F1" },
  { challenge: "Ground every extracted field in the contract's actual words",
    solution: "Pydantic schemas force a verbatim source_text per field, validated as a substring",
    figure: "grounding 0.95–1.00" },
  { challenge: "Benchmark a clause against the market, not opinion",
    solution: "pgvector retrieval over 18,001 chunks from 116 real SEC EDGAR EX-10 filings",
    figure: "MRR@5 0.917 · NDCG@5 0.987" },
  { challenge: "Make redlines defensible",
    solution: "Every suggested edit must cite a market statistic computed from structured extractions",
    figure: "5 cited filings per run · 8/8 e2e" },
  { challenge: "Survive provider outages and hostile uploads",
    solution: "3-provider LLM router with circuit breaker; allowlist + magic-byte + size validation; prompt-injection test suite",
    figure: "49 pytest suites in CI" },
];

const STACK = [
  "FastAPI · Gunicorn/Uvicorn", "sklearn · sentence-transformers", "Supabase · pgvector (IVFFlat)",
  "Anthropic / Groq / Ollama router", "React 18 · Vite · Recharts", "Docker · HF Spaces · Vercel", "GitHub Actions CI",
];

export default function OverviewPage() {
  return (
    <div className="bs">
      <Masthead section="The Prospectus" />
      <div className="bs-page">
        <section className="frontpage section-cover">
          <div className="dateline-row">
            <span>For the evaluating engineer</span>
            <span>Reading time — under a minute</span>
            <span>Figures from the Statistical Appendix</span>
          </div>
          <h1 className="headline headline-section">
            <span className="ln"><span>The sixty-second</span></span>
            <span className="ln"><span><em>due diligence.</em></span></span>
          </h1>
          <p className="standfirst standfirst-section">
            ALRM is an ML + IR system that analyzes contract clauses: a trained risk
            classifier, schema-enforced extraction with verbatim grounding, market
            benchmarking against real SEC filings, and redlines that must cite their
            sources. It is measured at every stage — the interesting part is not that
            it calls a model, but that it can prove what the model did.
          </p>
          <div className="ledger section-ledger">
            <div><span className="hs-n">18,001</span><span className="hs-l">EDGAR clause chunks</span></div>
            <div><span className="hs-n">116</span><span className="hs-l">real filed contracts</span></div>
            <div><span className="hs-n">0.965</span><span className="hs-l">avg detection F1</span></div>
            <div><span className="hs-n">49</span><span className="hs-l">pytest suites in CI</span></div>
          </div>
        </section>

        <section className="article">
          <div className="art-head">
            <span className="art-sec">§ I</span>
            <h2 className="art-title">Hard problems, measured answers</h2>
            <span className="art-kicker">Challenge → approach → figure</span>
          </div>
          <div className="prospectus-rows">
            {RESULTS.map((r) => (
              <div className="pros-row" key={r.figure}>
                <div className="pros-challenge">{r.challenge}</div>
                <div className="pros-solution">{r.solution}</div>
                <div className="pros-figure">{r.figure}</div>
              </div>
            ))}
          </div>
        </section>

        <section className="article">
          <div className="art-head">
            <span className="art-sec">§ II</span>
            <h2 className="art-title">Composition</h2>
            <span className="art-kicker">The stack</span>
          </div>
          <div className="pros-stack">
            {STACK.map((s) => <span key={s} className="fac-measure">{s}</span>)}
          </div>
          <div className="pros-links">
            <a className="btn-stamp" href="https://github.com/SriniV-1/legal-risk-mapper" target="_blank" rel="noopener noreferrer">Read the source</a>
            <Link className="btn-stamp" to="/evals">Inspect the appendix</Link>
            <Link className="btn-stamp" to="/app">Try the Monitor</Link>
          </div>
        </section>

        <Dossier current="prospectus" />
      </div>

      <footer className="bs-foot">
        <div className="bs-foot-inner">
          <span>ALRM — The Prospectus · portfolio project · not legal advice.</span>
          <span><a href="https://github.com/SriniV-1/legal-risk-mapper" target="_blank" rel="noopener noreferrer">GitHub</a></span>
        </div>
      </footer>
    </div>
  );
}
