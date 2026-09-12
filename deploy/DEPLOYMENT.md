# Deployment Guide

**Live stack (all free tiers):**

| Component | Platform | Notes |
|-----------|----------|-------|
| Backend (FastAPI + ML) | Hugging Face Spaces, Docker, `cpu-basic` | `https://sriniv-1-legal-risk-mapper.hf.space` |
| Frontend (`frontend-react/`, Vite) | Vercel | `https://legal-risk-mapper.vercel.app` |
| LLM inference | Groq free API, `openai/gpt-oss-120b` | 8,000 tokens/min, ~1,000 req/day — see `backend/services/limits.py` |
| Vector database | Supabase free tier | pgvector, 18,001 chunks |

`deploy/ec2-bootstrap.sh` and `start-app.sh` describe an **alternative** self-hosted EC2 path.
They are not part of the live deployment. `railway.json` is likewise an unused alternative.

---

## Part 1 — Groq API key

1. https://console.groq.com → sign up (no card) → **API Keys** → **Create API Key** (`gsk_...`)
2. The model defaults to `openai/gpt-oss-120b`. Override with `LRM_GROQ_MODEL` if Groq retires it
   (they retired the whole Llama 3.3 line in 2026; that is why this knob exists). Current
   alternatives: `openai/gpt-oss-20b`, `qwen/qwen3.6-27b`.

---

## Part 2 — Backend on Hugging Face Spaces

### One-time setup

1. https://huggingface.co/new-space → SDK **Docker**, visibility **Public**, name `legal-risk-mapper`.
2. Add the Space as a git remote and put a **write** token in the git credential helper once:
   ```bash
   git remote add hf https://huggingface.co/spaces/SriniV-1/Legal-risk-mapper
   # first push prompts for a password: paste a token from https://huggingface.co/settings/tokens
   ```
3. **Settings → Variables and secrets:**

   | Name | Value | Type |
   |------|-------|------|
   | `SUPABASE_URL` | project URL | Secret |
   | `SUPABASE_KEY` | service-role key | Secret |
   | `GROQ_API_KEY` | `gsk_...` | Secret |
   | `LRM_GROQ_MODEL` | `openai/gpt-oss-120b` (optional, this is the default) | Variable |
   | `LRM_REQUIRE_AUTH` | leave unset — the demo serves anonymous visitors | Variable |
   | `JWT_SECRET` | only if you turn auth on or use `/auth/*` | Secret |
   | `CORS_ORIGINS` | `https://legal-risk-mapper.vercel.app` (optional hardening) | Variable |

### Deploying

HF reads the Space config from **YAML frontmatter at the top of `README.md`**. GitHub's
README must not carry that block, so never push `main` straight to the Space. Use the script:

```bash
bash deploy/push-hf.sh
```

It builds a throwaway branch = `main` + `deploy/hf-frontmatter.md` prepended to the README,
force-pushes it as the Space's `main`, and returns you to your branch. The Space rebuilds
in ~1–2 minutes; watch https://huggingface.co/spaces/SriniV-1/Legal-risk-mapper.

Why force-push: `git fetch hf` fails on this remote with a protocol error (`expected
'acknowledgments'`), so merging is impossible. The Space holds no history of value — it is a
deploy target, not a source of truth.

### Verify

```bash
B=https://sriniv-1-legal-risk-mapper.hf.space
curl -s $B/health | python3 -m json.tool     # expect "ml_classifier": true and a "groq_model"
curl -s $B/ready  | python3 -m json.tool     # semantic, spacy, risk_classifier all "ok"
```

If `ml_classifier` is `false`, `data/models/risk_classifier.pkl` did not ship — the app is
silently on regex fallback. The file is tracked in git (an explicit `!` exception to the
`*.pkl` ignore rule); make sure it is committed.

---

## Part 3 — Frontend on Vercel

1. https://vercel.com → **Add New Project** → import `SriniV-1/legal-risk-mapper`.
2. `vercel.json` already configures the build: `cd frontend-react && npm run build`, output
   `frontend-react/dist`, SPA rewrite to `index.html`.
3. **Environment variable:** `VITE_API_BASE_URL` = `https://sriniv-1-legal-risk-mapper.hf.space`.
   (Local dev reads the same name from `frontend-react/.env`.)
4. Deploy. Vercel redeploys on every push to `main`.

---

## Updating

```bash
git push origin main       # Vercel redeploys the frontend automatically
bash deploy/push-hf.sh     # backend — required for any change under backend/, data/, requirements.txt
```

A frontend-only change needs only the first line; a backend change needs both.

---

## Cost

Vercel Hobby, HF Spaces `cpu-basic`, Groq free tier, and Supabase free tier are all free
without a card. The free Space may sleep after inactivity; the frontend calls `/warmup` on
open so the cold start overlaps with the user pasting text.
