import { useState, useRef, useEffect } from "react";
import { warmup as warmupApi } from "../api/client.js";

/**
 * Warms the backend models in the background as soon as the app opens.
 *
 * The expensive part of ALRM's first request is loading sentence-transformers,
 * spaCy, and the classifier pickle — 10-30s on a cold container. This fires
 * that load the moment the page mounts, so it overlaps with the user reading
 * the page and pasting a contract instead of landing on their Analyze click.
 *
 * Nothing is rendered while this runs. `wait()` exists for the one case that
 * still needs a visible wait: the user clicks Analyze before warmup finishes,
 * and the caller shows the normal loading overlay until this resolves.
 */
export default function useWarmup() {
  const [status, setStatus] = useState("warming"); // "warming" | "ready" | "failed"
  const promiseRef = useRef(null);

  useEffect(() => {
    promiseRef.current = warmupApi()
      .then(() => {
        setStatus("ready");
        return true;
      })
      .catch(() => {
        // A failed warmup is not fatal — the request path still works, it just
        // pays the cold cost itself. Don't block Analyze on it.
        setStatus("failed");
        return false;
      });
  }, []);

  /** Resolves once warmup has settled (successfully or not). Never rejects. */
  async function wait() {
    if (promiseRef.current) {
      try {
        await promiseRef.current;
      } catch {
        // already handled above
      }
    }
  }

  return { status, wait, isWarming: status === "warming" };
}
