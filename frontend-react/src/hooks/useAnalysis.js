import { useState, useRef } from "react";
import { analyzeText } from "../api/client.js";

export default function useAnalysis() {
  const [loading, setLoading] = useState(false);
  const [loadingMsg, setLoadingMsg] = useState("");
  const [error, setError] = useState(null);
  const [riskData, setRiskData] = useState(null);
  const [contractText, setContractText] = useState("");
  const [sevFilter, setSevFilter] = useState("all");
  const [view, setView] = useState("placeholder");
  const mainRef = useRef(null);

  async function analyze(getResolvedText) {
    setError(null);
    try {
      setLoading(true);
      setLoadingMsg("Running ML risk classifier…");
      const resolvedText = await getResolvedText(setLoadingMsg);
      setLoadingMsg("Running ML risk classifier…");
      const data = await analyzeText(resolvedText);
      setContractText(resolvedText);
      setRiskData(data);
      setSevFilter("all");
      setView("risk");
      mainRef.current?.scrollTo({ top: 0, behavior: "smooth" });
    } catch (e) {
      setError(`Analysis failed: ${e.message}`);
    } finally {
      setLoading(false);
    }
  }

  async function analyzeSample(text) {
    setError(null);
    try {
      setLoading(true);
      setLoadingMsg("Running ML risk classifier…");
      const data = await analyzeText(text);
      setContractText(text);
      setRiskData(data);
      setSevFilter("all");
      setView("risk");
      mainRef.current?.scrollTo({ top: 0, behavior: "smooth" });
    } catch (e) {
      setError(`Analysis failed: ${e.message}`);
    } finally {
      setLoading(false);
    }
  }

  function clearAnalysis() {
    setError(null);
    setRiskData(null);
    setContractText("");
    setSevFilter("all");
    setView("placeholder");
  }

  return {
    loading,
    setLoading,
    loadingMsg,
    setLoadingMsg,
    error,
    setError,
    riskData,
    setRiskData,
    contractText,
    sevFilter,
    setSevFilter,
    view,
    setView,
    mainRef,
    analyze,
    analyzeSample,
    clearAnalysis,
  };
}
