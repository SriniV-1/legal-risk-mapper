/**
 * ComparisonTable — field-by-field comparison table with color coding.
 *
 * Green = favorable (has protection), Red = unfavorable, Gray = null/unknown.
 * Fields that differ across contracts are highlighted with a left border.
 */

const UNFAVORABLE_TRUE_FIELDS = new Set([
  "has_price_escalation",
  "has_non_refundable",
  "has_termination_fee",
  "has_auto_renewal",
  "has_provider_owns_deliverables",
  "has_non_compete",
  "has_residuals_clause",
]);

function formatValue(val) {
  if (val === null || val === undefined) return "\u2014";
  if (typeof val === "boolean") return val ? "Yes" : "No";
  return String(val);
}

function cellColor(fieldName, val) {
  if (val === null || val === undefined) return "#6b7280";
  if (typeof val !== "boolean") return "#e5e7eb";
  const favorable = UNFAVORABLE_TRUE_FIELDS.has(fieldName) ? !val : val;
  return favorable ? "#22c55e" : "#ef4444";
}

function cellBg(fieldName, val) {
  if (val === null || val === undefined) return "rgba(107,114,128,0.08)";
  if (typeof val !== "boolean") return "transparent";
  const favorable = UNFAVORABLE_TRUE_FIELDS.has(fieldName) ? !val : val;
  return favorable ? "rgba(34,197,94,0.10)" : "rgba(239,68,68,0.10)";
}

function humanFieldName(name) {
  return name
    .replace(/^has_/, "")
    .replace(/_/g, " ")
    .replace(/\b\w/g, (c) => c.toUpperCase());
}

export default function ComparisonTable({ fieldComparison, contractNames }) {
  if (!fieldComparison || Object.keys(fieldComparison).length === 0) {
    return <p style={{ color: "#9ca3af", textAlign: "center" }}>No comparison data available.</p>;
  }

  const fields = Object.keys(fieldComparison);

  return (
    <div style={{ overflowX: "auto" }}>
      <table style={{
        width: "100%",
        borderCollapse: "collapse",
        fontSize: "0.9rem",
        background: "#1e1e2e",
        borderRadius: "8px",
        overflow: "hidden",
      }}>
        <thead>
          <tr style={{ borderBottom: "2px solid #374151" }}>
            <th style={thStyle}>Field</th>
            {contractNames.map((name) => (
              <th key={name} style={thStyle}>{name}</th>
            ))}
            <th style={thStyle}>Differs</th>
          </tr>
        </thead>
        <tbody>
          {fields.map((fieldName) => {
            const entry = fieldComparison[fieldName];
            const differs = entry.differs;
            return (
              <tr
                key={fieldName}
                style={{
                  borderBottom: "1px solid #2d2d3f",
                  borderLeft: differs ? "3px solid #f59e0b" : "3px solid transparent",
                }}
              >
                <td style={{ ...tdStyle, fontWeight: 500, color: "#d1d5db" }}>
                  {humanFieldName(fieldName)}
                </td>
                {contractNames.map((name) => {
                  const val = entry[name];
                  return (
                    <td
                      key={name}
                      style={{
                        ...tdStyle,
                        color: cellColor(fieldName, val),
                        background: cellBg(fieldName, val),
                        fontWeight: typeof val === "boolean" ? 600 : 400,
                      }}
                    >
                      {formatValue(val)}
                    </td>
                  );
                })}
                <td style={{ ...tdStyle, textAlign: "center" }}>
                  {differs ? (
                    <span style={{ color: "#f59e0b", fontWeight: 600 }}>Yes</span>
                  ) : (
                    <span style={{ color: "#6b7280" }}>No</span>
                  )}
                </td>
              </tr>
            );
          })}
        </tbody>
      </table>
    </div>
  );
}

const thStyle = {
  padding: "10px 14px",
  textAlign: "left",
  color: "#9ca3af",
  fontWeight: 600,
  fontSize: "0.8rem",
  textTransform: "uppercase",
  letterSpacing: "0.05em",
};

const tdStyle = {
  padding: "8px 14px",
  textAlign: "left",
};
