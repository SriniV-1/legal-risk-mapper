# Contributing to ALRM (Legal Risk Mapper)

Thanks for your interest in contributing! ALRM is an AI-powered contract clause
analysis platform (FastAPI · scikit-learn · sentence-transformers · RAG with
pgvector · LLM extraction). Bug reports, fixes, docs improvements, and
well-scoped features are all welcome.

## Ways to contribute

- **Report a bug** — open an issue with steps to reproduce and your environment.
- **Fix a bug** — small, focused PRs are easiest to review and merge.
- **Improve docs** — README, architecture notes, and docstrings.
- **Propose a feature** — open a feature request issue first to discuss scope.

## Development setup

```bash
# Backend (Python 3.11+)
pip install -r requirements.txt
python -m spacy download en_core_web_sm
cp .env.example .env          # add your credentials
set -a; source .env; set +a
python -m uvicorn backend.main:app --reload    # http://localhost:8000

# Frontend (React + Vite)
cd frontend-react && npm install && npm run dev # http://localhost:5173
```

The LLM router tries Anthropic, then Groq, then Ollama — set whichever API key
you have in `.env`. The system degrades gracefully if a backend is unavailable.

## Before you open a pull request

1. **Branch** from `main` (`git checkout -b fix/short-description`).
2. **Run the tests** locally:
   ```bash
   pytest
   ```
3. **Keep it scoped** — one logical change per PR.
4. **Match the surrounding style** — type hints, Pydantic schemas for structured
   data, and docstrings on public functions. Run `ruff` if available.
5. **Never commit secrets** — `.env` is gitignored; use `.env.example` for new
   config keys.
6. **Describe the change** clearly: what, why, and how you verified it.

## Reporting security issues

Please do **not** open public issues for security vulnerabilities. See
[SECURITY.md](SECURITY.md) for responsible disclosure.

## Code of Conduct

By participating, you agree to uphold our [Code of Conduct](CODE_OF_CONDUCT.md).
