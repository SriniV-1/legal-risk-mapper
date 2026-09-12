/**
 * Input size limits, mirrored from backend/services/limits.py.
 *
 * These are fallbacks only — AppPage fetches GET /limits on load and overrides
 * them, so the disclaimer the user reads and the cap the server enforces can
 * never drift apart. The numbers come from Groq's free plan for
 * openai/gpt-oss-120b: 8,000 tokens/minute is the binding constraint, since TPM
 * counts prompt + completion together.
 */
export const DEFAULT_LIMITS = {
  llm: { warn_words: 2000, max_words: 3000 },
  local: { warn_words: 10000, max_words: 50000 },
  tokens_per_word: 1.4,
  free_tier: {
    model: "openai/gpt-oss-120b",
    requests_per_minute: 30,
    requests_per_day: 1000,
    tokens_per_minute: 8000,
    tokens_per_day: 200000,
  },
};

export function countWords(text) {
  const trimmed = (text || "").trim();
  return trimmed ? trimmed.split(/\s+/).length : 0;
}

export function estimateTokens(text, limits = DEFAULT_LIMITS) {
  return Math.round(countWords(text) * (limits.tokens_per_word ?? 1.4));
}

/**
 * Classify input size for a pipeline: "ok" | "warn" | "over".
 * `over` means Analyze/Benchmark should be blocked client-side rather than
 * letting the request fail downstream as a rate-limit error.
 */
export function checkSize(text, mode = "llm", limits = DEFAULT_LIMITS) {
  const budget = limits[mode] ?? DEFAULT_LIMITS[mode];
  const words = countWords(text);
  const tokens = estimateTokens(text, limits);
  const { warn_words: warnWords, max_words: maxWords } = budget;

  if (words > maxWords) {
    return {
      ok: false,
      level: "over",
      words,
      tokens,
      warnWords,
      maxWords,
      message:
        mode === "llm"
          ? `${words.toLocaleString()} words is over the ${maxWords.toLocaleString()}-word limit for benchmarking and redlines (free-tier cap is ${(limits.free_tier?.tokens_per_minute ?? 8000).toLocaleString()} tokens/minute; this needs ~${tokens.toLocaleString()}). Analyze one clause or section at a time.`
          : `${words.toLocaleString()} words is over the ${maxWords.toLocaleString()}-word limit for risk analysis. Split the document and analyze it in parts.`,
    };
  }

  if (words > warnWords) {
    return {
      ok: true,
      level: "warn",
      words,
      tokens,
      warnWords,
      maxWords,
      message:
        mode === "llm"
          ? `${words.toLocaleString()} words (~${tokens.toLocaleString()} tokens) uses most of the free-tier per-minute budget. A rate-limit error here just means waiting a minute.`
          : `${words.toLocaleString()} words is a large document — analysis may take a while.`,
    };
  }

  return { ok: true, level: "ok", words, tokens, warnWords, maxWords, message: null };
}
