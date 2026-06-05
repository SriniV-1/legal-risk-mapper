import { useState } from "react";
import { Link } from "react-router-dom";
import { compareContracts } from "../api/client.js";
import ComparisonTable from "../components/ComparisonTable.jsx";

const CLAUSE_TYPES = [
  { value: "liability", label: "Liability" },
  { value: "termination", label: "Termination" },
  { value: "payment", label: "Payment" },
  { value: "confidentiality", label: "Confidentiality" },
  { value: "ip", label: "Intellectual Property" },
  { value: "governing_law", label: "Governing Law" },
];

const MIN_CONTRACTS = 2;
const MAX_CONTRACTS = 5;

function emptyContract(index) {
  return { name: `Contract ${index + 1}`, text: "" };
}

export default function ComparePage() {
  const [contracts, setContracts] = useState([emptyContract(0), emptyContract(1)]);
  const [clauseType, setClauseType] = useState("liability");
  const [loading, setLoading] = useState(false);
  const [error, setError] = useState(null);
  const [result, setResult] = useState(null);

  const canAdd = contracts.length < MAX_CONTRACTS;
  const canRemove = contracts.length > MIN_CONTRACTS;

  function updateContract(index, field, value) {
    setContracts((prev) =>
      prev.map((c, i) => (i === index ? { ...c, [field]: value } : c))
    );
  }

  function addContract() {
    if (canAdd) {
      setContracts((prev) => [...prev, emptyContract(prev.length)]);
    }
  }

  function removeContract(index) {
    if (canRemove) {
      setContracts((prev) => prev.filter((_, i) => i !== index));
    }
  }

  async function handleCompare() {
    setError(null);
    setResult(null);

    const filled = contracts.filter((c) => c.text.trim().length >= 30);
    if (filled.length < MIN_CONTRACTS) {
      setError("Please provide at least 2 contracts with 30+ characters each.");
      return;
    }

    setLoading(true);
    try {
      const data = await compareContracts(
        filled.map((c) => ({ name: c.name, text: c.text })),
        clauseType
      );
      setResult(data);
    } catch (err) {
      setError(err.message || "Comparison failed.");
    } finally {
      setLoading(false);
    }
  }

  const contractNames = result ? result.contracts.map((c) => c.name) : [];

  return (
    <div style={{ minHeight: "100vh", background: "#0f0f1a", color: "#e5e7eb" }}>
      {/* Header */}
      <header style={{
        display: "flex", alignItems: "center", justifyContent: "space-between",
        padding: "16px 32px", borderBottom: "1px solid #1e1e2e",
      }}>
        <div style={{ display: "flex", alignItems: "center", gap: "12px" }}>
          <Link to="/app" style={{ color: "#818cf8", textDecoration: "none", fontSize: "0.9rem" }}>
            &larr; Back to Analyzer
          </Link>
          <h1 style={{ margin: 0, fontSize: "1.3rem", color: "#f1f5f9" }}>
            Contract Comparison
          </h1>
        </div>
      </header>

      <main style={{ maxWidth: "1200px", margin: "0 auto", padding: "24px 32px" }}>
        {/* Clause Type Selector */}
        <div style={{ marginBottom: "20px" }}>
          <label style={{ display: "block", marginBottom: "6px", color: "#9ca3af", fontSize: "0.85rem" }}>
            Clause Type
          </label>
          <select
            value={clauseType}
            onChange={(e) => setClauseType(e.target.value)}
            style={{
              background: "#1e1e2e", color: "#e5e7eb", border: "1px solid #374151",
              borderRadius: "6px", padding: "8px 12px", fontSize: "0.9rem", minWidth: "200px",
            }}
          >
            {CLAUSE_TYPES.map((ct) => (
              <option key={ct.value} value={ct.value}>{ct.label}</option>
            ))}
          </select>
        </div>

        {/* Contract Inputs */}
        <div style={{
          display: "grid",
          gridTemplateColumns: `repeat(${Math.min(contracts.length, 3)}, 1fr)`,
          gap: "16px",
          marginBottom: "20px",
        }}>
          {contracts.map((contract, i) => (
            <div key={i} style={{
              background: "#1e1e2e", borderRadius: "8px", padding: "14px",
              border: "1px solid #2d2d3f",
            }}>
              <div style={{ display: "flex", alignItems: "center", justifyContent: "space-between", marginBottom: "8px" }}>
                <input
                  type="text"
                  value={contract.name}
                  onChange={(e) => updateContract(i, "name", e.target.value)}
                  style={{
                    background: "transparent", border: "none", borderBottom: "1px solid #374151",
                    color: "#f1f5f9", fontSize: "0.95rem", fontWeight: 600, padding: "4px 0", width: "70%",
                  }}
                  placeholder="Contract name"
                />
                {canRemove && (
                  <button
                    onClick={() => removeContract(i)}
                    style={{
                      background: "transparent", border: "none", color: "#ef4444",
                      cursor: "pointer", fontSize: "1.1rem", padding: "4px 8px",
                    }}
                    title="Remove contract"
                  >
                    &times;
                  </button>
                )}
              </div>
              <textarea
                value={contract.text}
                onChange={(e) => updateContract(i, "text", e.target.value)}
                placeholder="Paste clause text here (min 30 characters)..."
                style={{
                  width: "100%", minHeight: "160px", background: "#141422",
                  color: "#d1d5db", border: "1px solid #2d2d3f", borderRadius: "6px",
                  padding: "10px", fontSize: "0.85rem", resize: "vertical",
                  fontFamily: "inherit",
                }}
              />
              <div style={{ color: "#6b7280", fontSize: "0.75rem", marginTop: "4px" }}>
                {contract.text.length} characters
              </div>
            </div>
          ))}
        </div>

        {/* Add / Compare Buttons */}
        <div style={{ display: "flex", gap: "12px", marginBottom: "24px" }}>
          {canAdd && (
            <button
              onClick={addContract}
              style={{
                background: "transparent", border: "1px dashed #4b5563",
                color: "#9ca3af", padding: "8px 16px", borderRadius: "6px",
                cursor: "pointer", fontSize: "0.85rem",
              }}
            >
              + Add Contract
            </button>
          )}
          <button
            onClick={handleCompare}
            disabled={loading}
            style={{
              background: loading ? "#374151" : "#6366f1", color: "#fff",
              border: "none", padding: "10px 24px", borderRadius: "6px",
              cursor: loading ? "not-allowed" : "pointer", fontSize: "0.9rem",
              fontWeight: 600,
            }}
          >
            {loading ? "Comparing..." : "Compare Contracts"}
          </button>
        </div>

        {/* Error */}
        {error && (
          <div style={{
            background: "rgba(239,68,68,0.12)", border: "1px solid #ef4444",
            borderRadius: "6px", padding: "12px 16px", color: "#fca5a5",
            marginBottom: "20px", fontSize: "0.9rem",
          }}>
            {error}
          </div>
        )}

        {/* Results */}
        {result && (
          <div>
            {/* Recommendation */}
            <div style={{
              background: "rgba(99,102,241,0.10)", border: "1px solid #6366f1",
              borderRadius: "8px", padding: "14px 18px", marginBottom: "20px",
            }}>
              <div style={{ color: "#818cf8", fontSize: "0.8rem", fontWeight: 600, marginBottom: "4px", textTransform: "uppercase" }}>
                Recommendation
              </div>
              <div style={{ color: "#e5e7eb", fontSize: "0.95rem" }}>
                {result.recommendation}
              </div>
            </div>

            {/* Comparison Table */}
            <h2 style={{ fontSize: "1.1rem", color: "#f1f5f9", marginBottom: "12px" }}>
              Field-by-Field Comparison
            </h2>
            <ComparisonTable
              fieldComparison={result.field_comparison}
              contractNames={contractNames}
            />
          </div>
        )}
      </main>
    </div>
  );
}
