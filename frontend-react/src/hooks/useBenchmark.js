import { useState } from "react";
import { benchmarkText, generateRedlines } from "../api/client.js";

export default function useBenchmark({ setLoading, setLoadingMsg, setError, setView, setRiskData, mainRef }) {
  const [benchmarkLoading, setBenchmarkLoading] = useState(false);
  const [redlineLoading, setRedlineLoading] = useState(false);
  const [benchmarkData, setBenchmarkData] = useState(null);
  const [redlineData, setRedlineData] = useState(null);

  async function runBenchmark(getResolvedText) {
    setError(null);
    let text = "";
    try {
      setLoading(true);
      setLoadingMsg("Preparing text…");
      text = await getResolvedText(setLoadingMsg);
      setLoading(false);

      if (text.trim().length < 30) {
        setError("Please enter at least 30 characters to benchmark.");
        return;
      }

      setBenchmarkData(null);
      setRedlineData(null);
      setRiskData(null);
      setView("benchmark");
      mainRef.current?.scrollTo({ top: 0, behavior: "smooth" });

      setBenchmarkLoading(true);
      const bench = await benchmarkText(text, "auto");
      setBenchmarkData(bench);
      setBenchmarkLoading(false);

      setRedlineLoading(true);
      const redlines = await generateRedlines(text, bench.clause_type);
      setRedlineData(redlines);
      setRedlineLoading(false);
    } catch (e) {
      setLoading(false);
      setBenchmarkLoading(false);
      setRedlineLoading(false);
      setError(`Benchmark failed: ${e.message}`);
      setBenchmarkData((prev) => {
        if (!prev) setView("placeholder");
        return prev;
      });
    }
  }

  function clearBenchmark() {
    setBenchmarkData(null);
    setRedlineData(null);
    setBenchmarkLoading(false);
    setRedlineLoading(false);
  }

  return {
    benchmarkLoading,
    redlineLoading,
    benchmarkData,
    redlineData,
    runBenchmark,
    clearBenchmark,
  };
}
