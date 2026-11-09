# ALRM (legal-risk-mapper) — agent context

Read this first. Root `../CLAUDE.md` and `../HANDOFF.md` hold cross-project state.

## Prod rules (never break prod)
- Frontend: `frontend-react/` on Vercel (`legal-risk-mapper` and `legal-risk-mapper-buix`, both live, don't delete either). `frontend/` is gone.
- Backend: HF Space `sriniv-1-legal-risk-mapper.hf.space`, deployed only via `bash deploy/push-hf.sh` (force-push; `git fetch hf` is protocol-broken). Ask the user before deploying.
- Public mode: `LRM_REQUIRE_AUTH` unset → anonymous OK. The frontend sends no token; don't add auth to public routes.
- No `Co-Authored-By` trailer on commits. Commit or push only when the user asks.

## Commands
- Tests: `python -m pytest tests/ -q` with `SUPABASE_URL=https://stub.supabase.co SUPABASE_KEY=stub-key-for-ci`.
  No system Python has the deps. Use a scratch venv: `pip install -r requirements.txt && python -m spacy download en_core_web_sm`.
  Baseline: 292 passed / 4 skipped.
- Frontend: `cd frontend-react && npm install && npm run build` (no pnpm).

## Architecture facts
- `/analyze`: trained `data/models/risk_classifier.pkl` (5 LogisticRegression) + semantic. Zero LLM. Sources show `ml_classifier`.
- Groq (`openai/gpt-oss-120b`, via `LRM_GROQ_MODEL`) powers extraction / benchmark / redline.
- Word caps live in `backend/services/limits.py`: `LOCAL_MAX_WORDS = 50_000` (per-section ceiling and warn threshold) and `LOCAL_HARD_MAX_WORDS = 100_000` (analyze/upload hard cap; analysis runs section by section via `sectioned_analysis.py`), `LLM_MAX_WORDS = 3_000` (Groq routes). Over cap → 413.
- scikit-learn pinned `>=1.8,<1.9` to match the pickle. Don't bump.
- README/.env.example may drift from code. Code wins.

## Working loop
Opus orchestrates: plan → `builder` agent implements a task → `reviewer` agent checks it →
on FAIL, send the reviewer's findings back to `builder` (max 3 rounds, then escalate to the user) →
Opus runs the full suite before claiming done. Update `../HANDOFF.md` ALRM section at the end.
