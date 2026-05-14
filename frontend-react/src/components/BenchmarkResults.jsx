const EXTRACTION_FIELDS = {
  liability: [
    { l: "Liability Cap",        get: (e) => e.liability_cap?.has_cap },
    { l: "Cap Type",             get: (e) => e.liability_cap?.cap_type || "—" },
    { l: "Mutual",               get: (e) => e.is_mutual },
    { l: "Carve-Outs",           get: (e) => e.has_carve_outs },
    { l: "Consequential Excl.",  get: (e) => e.consequential_damages?.excluded },
    { l: "Indemnification",      get: (e) => e.has_indemnification },
    { l: "Warranty Disclaimer",  get: (e) => e.has_warranty_disclaimer },
  ],
  termination: [
    { l: "For Cause",            get: (e) => e.has_termination_for_cause },
    { l: "For Convenience",      get: (e) => e.has_termination_for_convenience },
    { l: "Cure Period",          get: (e) => e.cure_period?.has_cure_period },
    { l: "Cure Days",            get: (e) => e.cure_period?.cure_days ?? "—" },
    { l: "Notice Period",        get: (e) => e.notice_period?.has_notice_period },
    { l: "Auto-Renewal",         get: (e) => e.has_auto_renewal },
    { l: "Survival",             get: (e) => e.has_survival_clause },
    { l: "Term. Fee",            get: (e) => e.has_termination_fee },
  ],
  payment: [
    { l: "Payment Terms",        get: (e) => e.has_payment_terms },
    { l: "Payment Days",         get: (e) => e.payment_days ?? "—" },
    { l: "Late Fee",             get: (e) => e.late_fee?.has_late_fee },
    { l: "Price Escalation",     get: (e) => e.has_price_escalation },
    { l: "Non-Refundable",       get: (e) => e.has_non_refundable },
    { l: "Min. Commitment",      get: (e) => e.has_minimum_commitment },
    { l: "Dispute Process",      get: (e) => e.has_dispute_process },
  ],
  confidentiality: [
    { l: "Broad Definition",     get: (e) => e.has_broad_definition },
    { l: "Std. Exclusions",      get: (e) => e.has_standard_exclusions },
    { l: "Duration",             get: (e) => e.has_duration },
    { l: "Permitted Discl.",     get: (e) => e.has_permitted_disclosures },
    { l: "Return/Destroy",       get: (e) => e.has_return_or_destroy },
    { l: "Residuals",            get: (e) => e.has_residuals_clause },
    { l: "Injunctive Relief",    get: (e) => e.has_injunctive_relief },
    { l: "Mutual",               get: (e) => e.is_mutual },
  ],
  ip: [
    { l: "Customer Owns",        get: (e) => e.has_customer_owns_deliverables },
    { l: "Provider Owns",        get: (e) => e.has_provider_owns_deliverables },
    { l: "Pre-Existing IP",      get: (e) => e.has_pre_existing_ip_carveout },
    { l: "Work for Hire",        get: (e) => e.has_work_for_hire },
    { l: "IP Assignment",        get: (e) => e.has_ip_assignment },
    { l: "License Grant",        get: (e) => e.has_license_grant },
    { l: "Feedback Clause",      get: (e) => e.has_feedback_clause },
    { l: "Source Escrow",        get: (e) => e.has_source_code_escrow },
    { l: "Non-Compete",          get: (e) => e.has_non_compete },
  ],
  governing_law: [
    { l: "Governing Law",        get: (e) => e.has_governing_law },
    { l: "Jurisdiction",         get: (e) => e.governing_law_jurisdiction || "—" },
    { l: "Venue",                get: (e) => e.has_venue_selection },
    { l: "Arbitration",          get: (e) => e.has_arbitration },
    { l: "Jury Waiver",          get: (e) => e.has_jury_waiver },
    { l: "Class Action Wvr.",    get: (e) => e.has_class_action_waiver },
    { l: "Prevailing Fees",      get: (e) => e.has_prevailing_party_fees },
  ],
};

const DIST_CFG = {
  liability: {
    L: { has_cap: "Liability Cap", is_mutual: "Mutual", has_carve_outs: "Carve-Outs", consequential_excluded: "Consequential Excl.", has_indemnification: "Indemnification", has_warranty_disclaimer: "Warranty Disclaimer" },
    G: (e, f) => f === "has_cap" ? e?.liability_cap?.has_cap : f === "consequential_excluded" ? e?.consequential_damages?.excluded : e?.[f],
  },
  termination: {
    L: { has_termination_for_cause: "For Cause", has_termination_for_convenience: "For Convenience", has_cure_period: "Cure Period", has_notice_period: "Notice Period", has_auto_renewal: "Auto-Renewal", has_survival_clause: "Survival", has_termination_fee: "Term. Fee" },
    G: (e, f) => f === "has_cure_period" ? e?.cure_period?.has_cure_period : f === "has_notice_period" ? e?.notice_period?.has_notice_period : e?.[f],
  },
  payment: {
    L: { has_payment_terms: "Payment Terms", has_late_fee: "Late Fee", has_price_escalation: "Price Escalation", has_non_refundable: "Non-Refundable", has_minimum_commitment: "Min. Commitment", has_dispute_process: "Dispute Process", has_right_of_setoff: "Right of Setoff" },
    G: (e, f) => f === "has_late_fee" ? e?.late_fee?.has_late_fee : e?.[f],
  },
  confidentiality: {
    L: { has_broad_definition: "Broad Definition", has_standard_exclusions: "Std. Exclusions", has_duration: "Duration", has_permitted_disclosures: "Permitted Discl.", has_return_or_destroy: "Return/Destroy", has_residuals_clause: "Residuals", has_injunctive_relief: "Injunctive Relief", is_mutual: "Mutual" },
    G: (e, f) => e?.[f],
  },
  ip: {
    L: { has_customer_owns_deliverables: "Customer Owns", has_provider_owns_deliverables: "Provider Owns", has_pre_existing_ip_carveout: "Pre-Existing IP", has_work_for_hire: "Work for Hire", has_ip_assignment: "IP Assignment", has_license_grant: "License Grant", has_feedback_clause: "Feedback Clause", has_source_code_escrow: "Source Escrow", has_non_compete: "Non-Compete" },
    G: (e, f) => e?.[f],
  },
  governing_law: {
    L: { has_governing_law: "Governing Law", has_venue_selection: "Venue", has_arbitration: "Arbitration", has_jury_waiver: "Jury Waiver", has_class_action_waiver: "Class Action Wvr.", has_prevailing_party_fees: "Prevailing Fees" },
    G: (e, f) => e?.[f],
  },
};

function ExternalLinkIcon() {
  return (
    <svg width="11" height="11" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2" strokeLinecap="round" strokeLinejoin="round">
      <path d="M18 13v6a2 2 0 0 1-2 2H5a2 2 0 0 1-2-2V8a2 2 0 0 1 2-2h6"/>
      <polyline points="15 3 21 3 21 9"/>
      <line x1="10" y1="14" x2="21" y2="3"/>
    </svg>
  );
}

function BarChartIcon() {
  return (
    <svg width="15" height="15" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2" strokeLinecap="round" strokeLinejoin="round">
      <line x1="18" y1="20" x2="18" y2="10"/>
      <line x1="12" y1="20" x2="12" y2="4"/>
      <line x1="6" y1="20" x2="6" y2="14"/>
    </svg>
  );
}

export default function BenchmarkResults({ data }) {
  const type = data.clause_type || "liability";
  const typeLabel = type.replace(/_/g, " ");
  const ext = data.user_extraction;
  const dists = data.field_distributions || {};
  const cited = data.cited_examples || [];

  const extFields = [
    ...(EXTRACTION_FIELDS[type] || EXTRACTION_FIELDS.liability),
    {
      l: "Confidence",
      get: (e) =>
        e.extraction_confidence != null
          ? (e.extraction_confidence * 100).toFixed(0) + "%"
          : "—",
    },
  ];

  const cfg = DIST_CFG[type] || DIST_CFG.liability;
  const distRows = Object.entries(dists)
    .filter(([k, v]) => v.total > 0 && !v.value_counts?.length && cfg.L[k])
    .map(([field, dist]) => {
      const uv = cfg.G(ext, field);
      const pct = Math.max(dist.true_pct, 2);
      return { field, dist, uv, pct, label: cfg.L[field] };
    });

  return (
    <div className="card">
      <div className="card-header">
        <BarChartIcon />
        <span className="card-title">Benchmark</span>
        <span style={{ fontSize: "12px", color: "var(--text-3)", marginLeft: "4px" }}>
          {typeLabel} · {data.sample_size} similar clauses
        </span>
      </div>

      {/* Stats */}
      <div className="bench-meta">
        <div className="bench-stat">
          <span className="bench-stat-num">{data.sample_size}</span>
          <span className="bench-stat-label">Sample Size</span>
        </div>
        <div className="bench-stat">
          <span className="bench-stat-num">{cited.length}</span>
          <span className="bench-stat-label">Cited Examples</span>
        </div>
      </div>

      {/* Extraction grid */}
      {ext && (
        <>
          <div className="section-title">Extracted Fields</div>
          <div className="extraction-grid">
            {extFields.map((f) => {
              const v = f.get(ext);
              const isB = typeof v === "boolean";
              const cls = isB ? (v ? "is-true" : "is-false") : "";
              return (
                <div className="ext-item" key={f.l}>
                  <div className="ext-label">{f.l}</div>
                  <div className={`ext-value ${cls}`}>
                    {isB ? (v ? "Yes" : "No") : String(v ?? "—")}
                  </div>
                </div>
              );
            })}
          </div>
        </>
      )}

      {/* Distributions */}
      {distRows.length > 0 && (
        <>
          <div className="section-title">Market Distributions</div>
          <div className="dist-rows">
            {distRows.map(({ field, dist, uv, pct, label }) => (
              <div className="dist-row" key={field}>
                <div className="dist-row-top">
                  <span className="dist-name">{label}</span>
                  <span className="dist-meta">
                    {dist.true_count}/{dist.total} · {dist.true_pct.toFixed(0)}%
                  </span>
                </div>
                <div className="dist-track">
                  <div className="dist-fill" style={{ width: `${pct}%` }} />
                </div>
                {uv === true && (
                  <span className="dist-user-tag has">You have this</span>
                )}
                {uv === false && (
                  <span className="dist-user-tag lacks">You lack this</span>
                )}
              </div>
            ))}
          </div>
        </>
      )}

      {/* Cited examples */}
      {cited.length > 0 && (
        <>
          <div className="section-title">Cited SEC Examples</div>
          <div className="cited-list">
            {cited.map((ex, i) => (
              <div className="cited-card" key={i}>
                <div className="cited-card-header">
                  <span className="cited-company">{ex.company || ex.contract_id}</span>
                  <span className="cited-match">
                    {(ex.similarity * 100).toFixed(1)}% match
                  </span>
                </div>
                <div className="cited-card-body">
                  <div className="cited-snippet">"{ex.text_snippet}"</div>
                  {ex.exhibit_url && (
                    <a
                      className="cited-link"
                      href={ex.exhibit_url}
                      target="_blank"
                      rel="noopener noreferrer"
                    >
                      <ExternalLinkIcon />
                      View SEC Filing
                    </a>
                  )}
                </div>
              </div>
            ))}
          </div>
        </>
      )}

      {cited.length === 0 && (
        <div className="empty-state">No cited examples found.</div>
      )}
    </div>
  );
}
