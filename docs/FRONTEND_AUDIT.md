# Frontend Audit — ALRM (frontend-react)

*Audit performed before the 2026-06 frontend modernization.*

## State before redesign

- React 18 + Vite + Tailwind + Recharts; 3 routes (`/`, `/app`, `/compare`)
  with route-level code splitting.
- Visual identity: "editorial broadsheet" — warm ivory newsprint palette,
  serif display type (Fraunces/Newsreader), wax-seal monogram, dropcaps,
  "Vol. I · No. 01" masthead.
- 1,847-line `index.css` of bespoke classes; Tailwind installed but largely
  unused.

## Findings

### 1. Identity vs. audience
The broadsheet concept is distinctive but reads literary rather than
technical. Recruiters and engineers evaluating the project expect an
infrastructure-product surface (Linear, Vercel, Datadog) — dark-first, dense,
metric-forward. The system's strongest credibility signals (0.965 detection
F1, MRR@5 0.917, NDCG@5 0.987, 18,001-chunk EDGAR corpus, per-field grounding
0.95–1.00) were presented as a static table at the bottom of a long scroll.

### 2. Two design systems, neither authoritative
Tailwind shipped in the bundle while ~1,850 lines of handwritten CSS did the
real work. Tokens existed but only for the paper palette; no dark mode at all.

### 3. Missing surfaces
- No dedicated evaluation/benchmark dashboard despite a genuinely measured
  eval harness (per-field F1, MRR/NDCG, grounding scores, latency).
- No architecture visualization of the pipeline (upload → classify →
  pgvector retrieval → benchmark → grounded redlines).
- No recruiter-oriented overview.
- Recharts installed but barely used.

### 4. Interaction depth
No command palette, no keyboard shortcuts, minimal loading skeletons.

## Outcome (what was actually built)

The editorial-broadsheet identity was deliberately **kept** — it is
distinctive, fits the legal subject matter, and per design direction the
visual identity should reflect the project's purpose rather than chase a
generic dark "infra dashboard" look. The gaps were closed *within* the
publication concept:

- **`/evals` — The Statistical Appendix**: interactive Recharts figures
  styled as print plates (ink colors on paper, ruled captions) over the
  real measured data — extraction F1 + grounding per clause type,
  classifier per-category F1, retrieval MRR/NDCG/latency, 8/8 e2e runs,
  corpus coverage — with reproduction commands.
- **`/architecture` — The Pipeline**: six inspectable stages from intake
  to cited redline, each with file paths and measured stats.
- **`/overview` — The Prospectus**: the sixty-second recruiter read.
- Shared inner-section masthead; landing masthead links all sections.
- Existing `/app` and `/compare` untouched.
