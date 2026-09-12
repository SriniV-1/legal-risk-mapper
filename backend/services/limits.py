"""
Input size limits, derived from the free-tier quotas of the models we run on.

Two very different budgets live here, because the two pipelines have two
different bottlenecks:

  • LOCAL pipeline (/analyze, /analyze/upload) — spaCy + MiniLM +
    LogisticRegression, all on our own CPU. No third-party quota applies. The
    ceiling is latency and request timeout, not somebody's rate limit.

  • LLM pipeline (/benchmark, /redline) — Groq, openai/gpt-oss-120b.
    Bounded by Groq's published free-plan quota:

        30 requests/minute      1,000 requests/day
        8,000 tokens/minute     200,000 tokens/day

    (https://console.groq.com/docs/rate-limits — Free plan, per organization.)

The binding constraint for a SINGLE request is the 8,000 tokens/minute figure,
because TPM counts prompt + completion together. Budget for one call:

        8,000  TPM ceiling
       -2,000  max_tokens reserved for the completion (see extractor._call_groq)
         -900  schema + instruction overhead in the extraction/redline prompt
       ───────
        5,100  tokens left for the user's clause text

gpt-oss-120b is a reasoning model: it spends completion tokens on hidden
reasoning before emitting content. Those tokens are billed and counted toward
TPM, but they are drawn from the same max_tokens budget, so the 2,000 reserved
above is still a true ceiling rather than a floor. (It does mean max_tokens must
stay generous — at a very small budget reasoning consumes the whole allowance
and `content` comes back empty.)

Legal prose tokenizes at roughly 1.4 tokens/word (denser than ordinary English —
defined terms, section numbers, and long hyphenates all split). That gives
5,100 / 1.4 ≈ 3,600 words of headroom, so the hard cap is set at 3,000 words to
leave room for prompt drift and for the fact that TPM is a *rolling* window
shared with any other in-flight request.

Exceeding TPM does not fail gracefully — Groq returns 429 with a retry-after,
which surfaces to the user as a failed analysis. Rejecting oversized input up
front with a clear message is a better experience than a 429 halfway through.
"""
from __future__ import annotations

from typing import Literal, Optional, TypedDict

# ── Groq free-plan quota (openai/gpt-oss-120b) ───────────────────────────────
GROQ_FREE_TIER = {
    "model": "openai/gpt-oss-120b",
    "requests_per_minute": 30,
    "requests_per_day": 1_000,
    "tokens_per_minute": 8_000,
    "tokens_per_day": 200_000,
}

# Tokens/word for contract text. Measured against our EDGAR sample; plain
# English is closer to 1.3, legal text runs denser.
TOKENS_PER_WORD = 1.4

# ── Per-request word budgets ─────────────────────────────────────────────────
# LLM-backed routes: benchmarking, redlines, structured extraction.
LLM_WARN_WORDS = 2_000    # still works, but eats most of a minute's TPM
LLM_MAX_WORDS = 3_000     # hard reject — would blow the 8k TPM window

# Local-only route: risk classification. No external quota; the limit is how
# long a user will sit waiting for CPU embedding of every clause.
LOCAL_WARN_WORDS = 10_000
LOCAL_MAX_WORDS = 50_000

Mode = Literal["llm", "local"]

_BUDGETS: dict[str, tuple[int, int]] = {
    "llm": (LLM_WARN_WORDS, LLM_MAX_WORDS),
    "local": (LOCAL_WARN_WORDS, LOCAL_MAX_WORDS),
}


class LimitCheck(TypedDict):
    ok: bool                 # False → reject the request
    level: str               # "ok" | "warn" | "over"
    words: int
    estimated_tokens: int
    warn_words: int
    max_words: int
    message: Optional[str]


def count_words(text: str) -> int:
    """Whitespace word count — matches what the UI counter shows the user."""
    return len(text.split())


def estimate_tokens(text: str) -> int:
    """Approximate token count for contract prose. Deliberately conservative."""
    return int(count_words(text) * TOKENS_PER_WORD)


def check_size(text: str, mode: Mode = "llm") -> LimitCheck:
    """
    Classify an input as ok / warn / over for the given pipeline.

    "warn" is advisory — the request still runs. "over" means the caller should
    reject it (HTTP 413) rather than let it fail downstream as a 429.
    """
    warn_words, max_words = _BUDGETS[mode]
    words = count_words(text)
    tokens = estimate_tokens(text)

    if words > max_words:
        if mode == "llm":
            message = (
                f"Input is {words:,} words — over the {max_words:,}-word limit for "
                f"market benchmarking and redlines. These run on Groq's free tier "
                f"({GROQ_FREE_TIER['tokens_per_minute']:,} tokens/minute), and this "
                f"request would need about {tokens:,} tokens. Analyze one clause or "
                f"section at a time."
            )
        else:
            message = (
                f"Input is {words:,} words — over the {max_words:,}-word limit for "
                f"risk analysis. Split the document and analyze it in parts."
            )
        return LimitCheck(ok=False, level="over", words=words, estimated_tokens=tokens,
                          warn_words=warn_words, max_words=max_words, message=message)

    if words > warn_words:
        if mode == "llm":
            message = (
                f"{words:,} words (~{tokens:,} tokens) uses most of the free-tier "
                f"per-minute token budget. If this fails with a rate-limit error, "
                f"wait a minute or analyze a shorter section."
            )
        else:
            message = (
                f"{words:,} words is a large document — analysis may take a while."
            )
        return LimitCheck(ok=True, level="warn", words=words, estimated_tokens=tokens,
                          warn_words=warn_words, max_words=max_words, message=message)

    return LimitCheck(ok=True, level="ok", words=words, estimated_tokens=tokens,
                      warn_words=warn_words, max_words=max_words, message=None)


def enforce(text: str, mode: Mode = "llm") -> None:
    """Raise HTTP 413 if `text` is over the hard cap for `mode`. Else no-op."""
    result = check_size(text, mode)
    if not result["ok"]:
        from fastapi import HTTPException
        raise HTTPException(status_code=413, detail=result["message"])


def public_limits() -> dict:
    """Limit config for the frontend, so the UI never hardcodes a stale number."""
    return {
        "llm": {"warn_words": LLM_WARN_WORDS, "max_words": LLM_MAX_WORDS},
        "local": {"warn_words": LOCAL_WARN_WORDS, "max_words": LOCAL_MAX_WORDS},
        "tokens_per_word": TOKENS_PER_WORD,
        "free_tier": GROQ_FREE_TIER,
    }
