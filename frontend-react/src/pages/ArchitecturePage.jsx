import { useState } from "react";
import Masthead from "../components/Masthead.jsx";
import Dossier from "../components/Dossier.jsx";

/* The pipeline, told as the publication's production process. Each stage is
   inspectable; file paths and measured numbers are real. */

const STAGES = [
  {
    n: "I", title: "Intake", kicker: "upload, hardened",
    summary: "A clause arrives as text or a file and is treated as hostile until proven otherwise.",
    detail: "Extension allowlist, 10 MB cap, and PDF magic-byte validation run before any parsing; OCR-aware PyMuPDF handles scanned documents. A dedicated prompt-injection test suite attacks this path in CI.",
    files: "backend/api/upload.py · tests/",
    stats: ["allowlist + magic bytes", "10 MB cap", "OCR-aware"],
  },
  {
    n: "II", title: "Classification", kicker: "five trained editors",
    summary: "Five independent LogisticRegression models — one per risk category — read the clause over MiniLM-L6 embeddings.",
    detail: "An ensemble of five binary classifiers over 384-dim sentence embeddings, not a general-purpose LLM call. Each returns detection, severity, and confidence with the exact flagged text. Regex fallback keeps the product alive if the model file is missing.",
    files: "backend/ml/classifier.py",
    stats: ["0.965 avg detection F1", "5-fold CV", "graceful regex fallback"],
  },
  {
    n: "III", title: "Retrieval", kicker: "the morgue file",
    summary: "pgvector pulls the most similar clauses from 18,001 chunks of real SEC EDGAR EX-10 filings.",
    detail: "Embeddings live in Supabase next to the relational data, so one match_clauses() RPC does cosine similarity over IVFFlat and joins extraction results in a single query — no separate vector service.",
    files: "backend/corpus/retrieval.py",
    stats: ["MRR@5 0.917", "NDCG@5 0.987", "0.243 s avg query"],
  },
  {
    n: "IV", title: "Extraction", kicker: "verbatim or nothing",
    summary: "Six clause-type schemas force every extracted field to carry a verbatim source quote.",
    detail: "Pydantic schemas enforce a source_text on every field, validated as a substring of the input. Per-field F1 (0.76–0.97) and grounding (0.95–1.00) are measured against hand-labeled sets — drift from the contract's actual words is a tracked metric, not a vibe.",
    files: "backend/extraction/ · backend/extraction/eval.py",
    stats: ["6 schemas", "grounding 0.95–1.00", "per-field F1 tracked"],
  },
  {
    n: "V", title: "Benchmarking", kicker: "against the market, not opinion",
    summary: "The clause is placed against field distributions computed from real filings.",
    detail: "For a boolean field present in 73% of similar contracts, a clause that has it sits at the 73rd percentile. The market sample is whatever retrieval returned — typically 6–17 real contracts per run in the e2e eval.",
    files: "backend/benchmark/",
    stats: ["percentiles from filings", "8/8 e2e success"],
  },
  {
    n: "VI", title: "Redline", kicker: "the editor's pen",
    summary: "Suggested edits must cite a concrete market statistic; exact original and proposed text, no hand-waving.",
    detail: "The LLM (Anthropic → Groq → Ollama router with identical prompts and schemas, circuit-breaker guarded) is constrained to justify every suggestion with a statistic derived from structured extractions — \"appears in 81% of similar contracts\" — never its own opinion.",
    files: "backend/llm/router.py · backend/redline/",
    stats: ["3-provider router", "every edit cites the corpus", "5 cited filings per run"],
  },
];

export default function ArchitecturePage() {
  const [open, setOpen] = useState("II");

  return (
    <div className="bs">
      <Masthead section="The Pipeline" />
      <div className="bs-page">
        <section className="frontpage section-cover">
          <div className="dateline-row">
            <span>How the Monitor is made</span>
            <span>FastAPI · Supabase/pgvector · React</span>
            <span>49 pytest suites in CI</span>
          </div>
          <h1 className="headline headline-section">
            <span className="ln"><span>From raw clause</span></span>
            <span className="ln"><span>to cited <em>redline.</em></span></span>
          </h1>
          <p className="standfirst standfirst-section">
            Six stages, each measured. Select a stage to read how it works, where it
            lives, and what the eval harness says about it.
          </p>
        </section>

        <section className="article">
          <ol className="pipeline" role="list">
            {STAGES.map((s) => {
              const isOpen = open === s.n;
              return (
                <li key={s.n} className={`pipe-stage${isOpen ? " open" : ""}`}>
                  <button className="pipe-head" onClick={() => setOpen(isOpen ? null : s.n)}
                          aria-expanded={isOpen}>
                    <span className="step-no">{s.n} —</span>
                    <span className="pipe-title">{s.title}</span>
                    <span className="pipe-kicker">{s.kicker}</span>
                    <span className="pipe-toggle" aria-hidden="true">{isOpen ? "–" : "+"}</span>
                  </button>
                  <p className="pipe-summary">{s.summary}</p>
                  {isOpen && (
                    <div className="pipe-detail">
                      <p>{s.detail}</p>
                      <div className="pipe-files"><span>Filed under</span><code>{s.files}</code></div>
                      <div className="pipe-stats">
                        {s.stats.map((st) => <span key={st} className="fac-measure">{st}</span>)}
                      </div>
                    </div>
                  )}
                </li>
              );
            })}
          </ol>
        </section>

        <section className="article">
          <div className="art-head">
            <span className="art-sec">Margins</span>
            <h2 className="art-title">Production notes</h2>
            <span className="art-kicker">Ops &amp; hardening</span>
          </div>
          <div className="faculties">
            <article className="faculty">
              <div className="fac-no">a</div>
              <div>
                <div className="fac-kicker">Serving</div>
                <h3 className="fac-title">FastAPI behind Gunicorn</h3>
                <p className="fac-body">Uvicorn workers, JWT auth with a role hierarchy, per-route rate limiting, response caching, and structured request tracing. JWT secret fails closed in production.</p>
              </div>
            </article>
            <article className="faculty">
              <div className="fac-no">b</div>
              <div>
                <div className="fac-kicker">Resilience</div>
                <h3 className="fac-title">Degrade, don't die</h3>
                <p className="fac-body">LLM-provider circuit breaker; regex fallback when the model file is missing; the semantic layer auto-disables on load failure. The product answers even when its smartest parts are unavailable.</p>
              </div>
            </article>
            <article className="faculty">
              <div className="fac-no">c</div>
              <div>
                <div className="fac-kicker">Delivery</div>
                <h3 className="fac-title">Vercel + Hugging Face</h3>
                <p className="fac-body">React 18 + Vite on Vercel; Dockerized backend on HF Spaces. CI runs 49 pytest suites including the prompt-injection battery on every push.</p>
              </div>
            </article>
          </div>
        </section>

        <Dossier current="pipeline" />
      </div>

      <footer className="bs-foot">
        <div className="bs-foot-inner">
          <span>ALRM — The Pipeline · every stage measured by the appendix.</span>
          <span><a href="https://github.com/SriniV-1/legal-risk-mapper" target="_blank" rel="noopener noreferrer">GitHub</a></span>
        </div>
      </footer>
    </div>
  );
}
