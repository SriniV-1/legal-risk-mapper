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

## Redesign (what replaced it)

- **Dark-first infrastructure design system** in CSS custom properties
  (`src/styles/`): slate/graphite surfaces, single accent, severity colors
  preserved, accessible contrast, light theme retained as a toggle.
- **New routes**: `/evals` (interactive evaluation dashboard over real
  measured data), `/architecture` (inspectable pipeline diagram),
  `/overview` (60-second recruiter summary). Existing `/app` and `/compare`
  re-skinned, functionality untouched.
- **Command palette (⌘K)** with route + action navigation.
- Eval metrics promoted to the landing hero with animated counters.
