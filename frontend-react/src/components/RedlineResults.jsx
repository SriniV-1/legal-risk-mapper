import { useState } from "react";

function CopyIcon() {
  return (
    <svg width="11" height="11" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2" strokeLinecap="round" strokeLinejoin="round">
      <rect x="9" y="9" width="13" height="13" rx="2" ry="2"/>
      <path d="M5 15H4a2 2 0 0 1-2-2V4a2 2 0 0 1 2-2h9a2 2 0 0 1 2 2v1"/>
    </svg>
  );
}

function CheckIcon() {
  return (
    <svg width="11" height="11" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2" strokeLinecap="round" strokeLinejoin="round">
      <polyline points="20 6 9 17 4 12"/>
    </svg>
  );
}

function TrendingUpIcon() {
  return (
    <svg width="12" height="12" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2" strokeLinecap="round" strokeLinejoin="round">
      <polyline points="23 6 13.5 15.5 8.5 10.5 1 18"/>
      <polyline points="17 6 23 6 23 12"/>
    </svg>
  );
}

function GitIcon() {
  return (
    <svg width="15" height="15" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2" strokeLinecap="round" strokeLinejoin="round">
      <circle cx="18" cy="18" r="3"/><circle cx="6" cy="6" r="3"/>
      <path d="M13 6h3a2 2 0 0 1 2 2v7"/>
      <line x1="6" y1="9" x2="6" y2="21"/>
    </svg>
  );
}

function RedlineItem({ suggestion, index }) {
  const [copied, setCopied] = useState(false);
  const priority = (suggestion.priority || "medium").toLowerCase();

  function handleCopy() {
    navigator.clipboard
      .writeText(suggestion.proposed_text || "")
      .then(() => {
        setCopied(true);
        setTimeout(() => setCopied(false), 1500);
      })
      .catch(() => {});
  }

  return (
    <div className={`redline-item ${priority}`}>
      <div className="redline-item-header">
        <span className={`redline-priority ${priority}`}>{priority}</span>
        <span className="redline-risk-label">{suggestion.risk_addressed}</span>
        <button className="btn-copy" onClick={handleCopy}>
          {copied ? <CheckIcon /> : <CopyIcon />}
          {copied ? "Copied" : "Copy"}
        </button>
      </div>

      <div className="redline-diff">
        <div className="diff-label">Original</div>
        <div className="diff-original">{suggestion.original_text}</div>
        <div className="diff-label" style={{ marginTop: "10px" }}>Proposed</div>
        <div className="diff-proposed">{suggestion.proposed_text}</div>
      </div>

      {suggestion.justification && (
        <div className="redline-justification">{suggestion.justification}</div>
      )}

      {suggestion.market_citation && (
        <div className="redline-citation">
          <TrendingUpIcon />
          {suggestion.market_citation}
        </div>
      )}
    </div>
  );
}

export default function RedlineResults({ data }) {
  const suggestions = data.suggestions || [];

  return (
    <div className="card">
      <div className="card-header">
        <GitIcon />
        <span className="card-title">Redline Suggestions</span>
      </div>

      {data.summary && (
        <div className="redline-summary">{data.summary}</div>
      )}

      {suggestions.length === 0 ? (
        <div className="empty-state">
          No redline suggestions — your clause aligns with market norms.
        </div>
      ) : (
        <div className="redline-list">
          {suggestions.map((s, i) => (
            <RedlineItem key={i} suggestion={s} index={i} />
          ))}
        </div>
      )}
    </div>
  );
}
