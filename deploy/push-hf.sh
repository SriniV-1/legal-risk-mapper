#!/usr/bin/env bash
# Deploy the backend to the Hugging Face Space.
#
# The Space is a git repo that REQUIRES YAML frontmatter at the top of README.md
# (that is how HF knows sdk: docker). GitHub's README must not carry it. So this
# script builds a throwaway branch = main + frontmatter-prefixed README, and
# force-pushes that as the Space's `main`. GitHub `main` is never touched.
#
#   bash deploy/push-hf.sh            # deploys HEAD of current branch
#
# Prereq: `git remote add hf https://huggingface.co/spaces/SriniV-1/Legal-risk-mapper`
# and HF credentials in the git credential helper (osxkeychain) — a write token
# from https://huggingface.co/settings/tokens used as the password once.
#
# Note: `git fetch hf` fails with a protocol error on this remote; only push works,
# which is why this always force-pushes instead of merging. The Space keeps no
# history of value — it is a deploy target, not a source of truth.
set -euo pipefail
cd "$(dirname "$0")/.."

SRC_BRANCH=$(git rev-parse --abbrev-ref HEAD)
SRC_SHA=$(git rev-parse --short HEAD)
TMP_BRANCH="hf-deploy-tmp"

if [ -n "$(git status --porcelain)" ]; then
  echo "error: working tree not clean — commit or stash first" >&2; exit 1
fi
git remote get-url hf >/dev/null 2>&1 || { echo "error: no 'hf' remote" >&2; exit 1; }

cleanup() { git checkout -q "$SRC_BRANCH" 2>/dev/null || true; git branch -qD "$TMP_BRANCH" 2>/dev/null || true; }
trap cleanup EXIT

git checkout -qB "$TMP_BRANCH" "$SRC_BRANCH"
{ cat deploy/hf-frontmatter.md; cat README.md; } > README.md.hf && mv README.md.hf README.md
git add README.md
git commit -qm "hf: prefix README with Space frontmatter (deploy of $SRC_SHA)"
git push --force hf "$TMP_BRANCH:main"
echo "deployed $SRC_BRANCH@$SRC_SHA -> hf:main. Watch: https://huggingface.co/spaces/SriniV-1/Legal-risk-mapper"
