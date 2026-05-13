# Deployment Guide

**Stack (100% free, no credit card required anywhere):**

| Component | Platform | Cost |
|-----------|----------|------|
| Backend (FastAPI + ML) | Hugging Face Spaces (Docker) | Free |
| Frontend (static HTML/JS) | Vercel | Free |
| LLM inference | Groq free API | Free (14,400 req/day) |
| Vector database | Supabase free tier | Free (500MB) |

---

## Part 1 — Get a Free Groq API Key

Groq runs Llama 3.1 8B for free. This replaces Ollama (local) and Anthropic (paid).

1. Go to https://console.groq.com
2. Sign up with email (no credit card asked)
3. Go to **API Keys** → **Create API Key**
4. Copy the key (starts with `gsk_...`) — you'll need it in the next steps

---

## Part 2 — Backend on Hugging Face Spaces

Hugging Face Spaces runs Docker containers for free with 16GB RAM — the right home for
an app that loads sentence-transformers and spaCy models. Always-on, no spin-down.

### Step 1: Create a Hugging Face account

1. Go to https://huggingface.co/join
2. Sign up with email (free, no credit card)

### Step 2: Create a new Space

1. Go to https://huggingface.co/new-space
2. Settings:
   - **Owner**: your username
   - **Space name**: `legal-risk-mapper`
   - **License**: MIT
   - **SDK**: Docker
   - **Visibility**: Public (required for free tier)
3. Click **Create Space**

This creates a git repository at `https://huggingface.co/spaces/YOUR_USERNAME/legal-risk-mapper`.

### Step 3: Push your code

The Space is a git repo. You'll push your project there.

```bash
cd "/Users/srini/Downloads/CS Projects/legal-risk-mapper"

# Add HF Spaces as a remote (replace YOUR_USERNAME)
git remote add hf https://huggingface.co/spaces/YOUR_USERNAME/legal-risk-mapper

# HF needs a README.md with frontmatter — overwrite it for the Space
cp deploy/hf-space-readme.md README.md
git add README.md
git commit -m "add HF Spaces config"

# Push to HF Spaces (authenticate with HF token when prompted)
git push hf main
```

HF will build the Docker image automatically. Build takes ~5 minutes on first push.
Watch progress at: `https://huggingface.co/spaces/YOUR_USERNAME/legal-risk-mapper`

After the build, restore your README:
```bash
git checkout origin/main -- README.md
git commit -m "restore README"
git push hf main
```

Or maintain separate branches: `main` for GitHub, `hf-deploy` for Hugging Face.

### Step 4: Set environment variables in the Space

In the HF Space dashboard → **Settings** → **Variables and secrets**:

| Name | Value | Type |
|------|-------|------|
| `SUPABASE_URL` | your Supabase project URL | Secret |
| `SUPABASE_KEY` | your Supabase service role key | Secret |
| `GROQ_API_KEY` | your Groq API key (`gsk_...`) | Secret |
| `ALRM_EXTRACTION_MODEL` | `llama-3.1-8b-instant` | Variable |
| `ALRM_API_KEY` | a password you make up | Secret |

`ALRM_API_KEY` is optional but recommended — it gates `/benchmark` and `/redline` so
only you can trigger LLM calls. Without it, anyone who finds the URL can use your Groq quota.

### Step 5: Verify

Your backend URL is: `https://YOUR_USERNAME-legal-risk-mapper.hf.space`

```bash
curl https://YOUR_USERNAME-legal-risk-mapper.hf.space/health
# {"status": "ok", ...}
```

Swagger docs: `https://YOUR_USERNAME-legal-risk-mapper.hf.space/docs`

---

## Part 3 — Frontend on Vercel

### Step 1: Set your backend URL

Open `frontend/config.js` and update the URL:

```js
window.LRM_API_BASE = "https://YOUR_USERNAME-legal-risk-mapper.hf.space";
```

Commit and push this to GitHub.

### Step 2: Deploy to Vercel

1. Go to https://vercel.com and sign up with GitHub (free, no credit card)
2. Click **Add New Project** → select `legal-risk-mapper`
3. Vercel auto-detects `vercel.json` → `outputDirectory: frontend`
4. Click **Deploy**

Your frontend URL will be something like `https://legal-risk-mapper.vercel.app`.

### Step 3: Lock CORS to your Vercel URL (optional hardening)

In HF Spaces → Settings → Variables, add:

| Name | Value |
|------|-------|
| `CORS_ORIGINS` | `https://legal-risk-mapper.vercel.app` |

This prevents other sites from calling your backend. Fine to skip for a portfolio project.

---

## Updating the App

```bash
# Make your changes, then push to GitHub
git push origin main

# Also push to HF Spaces (backend changes only)
git push hf main

# Vercel redeploys automatically on GitHub push (frontend)
# HF Spaces rebuilds automatically on push (backend)
```

---

## Cost Summary

Everything above is genuinely free with no hidden limits that would surprise you:

- **Vercel Hobby**: free forever for personal projects, no credit card required
- **Hugging Face Spaces (CPU free)**: free forever, 16GB RAM, 2 vCPU
- **Groq free tier**: 14,400 requests/day, no credit card required
- **Supabase free tier**: 500MB database, 2GB bandwidth/month

The only way you'd get charged is if you intentionally upgrade to paid tiers.
