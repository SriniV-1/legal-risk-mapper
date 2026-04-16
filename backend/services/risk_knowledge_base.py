"""
Canonical Risk Clause Knowledge Base
─────────────────────────────────────
A curated set of "known risky" clauses, one per distinct risk pattern.
These clauses are embedded once at startup and used as reference points
for semantic similarity matching.

Why hand-curated (not ML-trained)?
  • Fully local, no training pipeline, no labeled dataset needed
  • Each entry is auditable — you can trace exactly why the system flagged something
  • Easy to extend: add a new entry and the cache rebuilds on next run

Each entry contributes one 384-dim embedding (~1.5 KB on disk).
Total memory footprint for 40 clauses: ~60 KB.

Fields:
  id       — stable identifier for debugging / traceability
  category — one of the 5 risk categories (matches regex RISK_RULES)
  severity — High | Medium | Low (base severity; may be adjusted by similarity)
  text     — the canonical risky phrasing (used for embedding)
  keywords — representative terms (used for explanation generation)
  rationale — one-line reason WHY this pattern is risky (used in explanations)
"""

CANONICAL_CLAUSES = [

    # ───────────────────────────────────────────────────────────────
    #  LIABILITY RISK
    # ───────────────────────────────────────────────────────────────
    {
        "id": "LIAB_01",
        "category": "Liability Risk",
        "severity": "High",
        "text": "The Customer shall defend, indemnify, and hold harmless the Provider from any and all claims, damages, losses, and expenses arising from use of the services.",
        "keywords": ["indemnify", "hold harmless", "defend"],
        "rationale": "broad indemnification shifts legal defense costs and damages to the customer",
    },
    {
        "id": "LIAB_02",
        "category": "Liability Risk",
        "severity": "High",
        "text": "The receiving party agrees to make the disclosing party whole for any losses, damages, or costs incurred as a result of breach.",
        "keywords": ["make whole", "losses", "damages"],
        "rationale": "'make whole' language functionally equals indemnification without using the word",
    },
    {
        "id": "LIAB_03",
        "category": "Liability Risk",
        "severity": "High",
        "text": "Services are provided on an as-is and as-available basis without warranties of any kind, whether express or implied.",
        "keywords": ["as-is", "as-available", "warranties"],
        "rationale": "disclaims all warranties — you accept the service in whatever state it arrives",
    },
    {
        "id": "LIAB_04",
        "category": "Liability Risk",
        "severity": "High",
        "text": "The Provider's aggregate liability shall not exceed the fees paid during the three months preceding the claim.",
        "keywords": ["aggregate liability", "fees paid"],
        "rationale": "liability cap tied to recent fees can leave you with minimal recovery for major harm",
    },
    {
        "id": "LIAB_05",
        "category": "Liability Risk",
        "severity": "High",
        "text": "In no event shall either party be liable for lost profits, lost revenue, loss of business, or any indirect, consequential, or punitive damages.",
        "keywords": ["lost profits", "consequential", "indirect damages"],
        "rationale": "excludes the damage categories that typically make up the real cost of a breach",
    },
    {
        "id": "LIAB_06",
        "category": "Liability Risk",
        "severity": "Medium",
        "text": "Neither party shall be responsible for delays or failures caused by events beyond its reasonable control, including acts of God, government action, or labor disputes.",
        "keywords": ["force majeure", "beyond control"],
        "rationale": "broad force majeure wording can excuse non-performance in foreseeable situations",
    },
    {
        "id": "LIAB_07",
        "category": "Liability Risk",
        "severity": "High",
        "text": "The Customer assumes full responsibility for any consequences arising from use of the platform and waives all rights to pursue legal action.",
        "keywords": ["assumes responsibility", "waives rights"],
        "rationale": "waiver of the right to sue eliminates legal recourse even for serious harm",
    },
    {
        "id": "LIAB_08",
        "category": "Liability Risk",
        "severity": "Medium",
        "text": "The Provider makes no guarantees regarding uptime, accuracy, or fitness of the service for the Customer's intended purpose.",
        "keywords": ["no guarantees", "fitness", "uptime"],
        "rationale": "implicit warranty disclaimer — you cannot rely on service availability or suitability",
    },

    # ───────────────────────────────────────────────────────────────
    #  COMPLIANCE RISK
    # ───────────────────────────────────────────────────────────────
    {
        "id": "COMP_01",
        "category": "Compliance Risk",
        "severity": "High",
        "text": "The Customer is solely responsible for ensuring compliance with all applicable data protection laws including GDPR, CCPA, and similar regulations.",
        "keywords": ["compliance", "GDPR", "data protection"],
        "rationale": "shifts 100% of regulatory compliance burden onto the customer",
    },
    {
        "id": "COMP_02",
        "category": "Compliance Risk",
        "severity": "High",
        "text": "The parties shall observe all laws, regulations, and administrative requirements applicable to the performance of this agreement.",
        "keywords": ["laws", "regulations", "applicable"],
        "rationale": "broad, unspecified compliance obligation creates open-ended legal exposure",
    },
    {
        "id": "COMP_03",
        "category": "Compliance Risk",
        "severity": "High",
        "text": "The Customer must obtain and maintain any licenses, permits, or regulatory approvals necessary for lawful use of the services in its jurisdiction.",
        "keywords": ["licenses", "permits", "regulatory approval"],
        "rationale": "customer bears full cost and risk of obtaining regulatory approvals",
    },
    {
        "id": "COMP_04",
        "category": "Compliance Risk",
        "severity": "High",
        "text": "Each party shall comply with all anti-bribery, anti-corruption, and economic sanctions laws including the FCPA, UK Bribery Act, and OFAC regulations.",
        "keywords": ["anti-bribery", "FCPA", "sanctions"],
        "rationale": "anti-corruption and sanctions violations carry severe criminal penalties",
    },
    {
        "id": "COMP_05",
        "category": "Compliance Risk",
        "severity": "Medium",
        "text": "The Customer agrees to follow industry-standard practices and recognized codes of conduct applicable to its business.",
        "keywords": ["industry-standard", "codes of conduct"],
        "rationale": "'industry-standard' is an undefined and disputed legal standard",
    },
    {
        "id": "COMP_06",
        "category": "Compliance Risk",
        "severity": "High",
        "text": "Services involving transfer of technology or data across borders are subject to export control restrictions including EAR and ITAR.",
        "keywords": ["export control", "EAR", "ITAR", "cross-border"],
        "rationale": "export control violations carry criminal liability regardless of intent",
    },
    {
        "id": "COMP_07",
        "category": "Compliance Risk",
        "severity": "High",
        "text": "The Customer represents that its use of the service will not violate any laws concerning protected health information or financial records.",
        "keywords": ["protected health", "HIPAA", "financial records"],
        "rationale": "implicates HIPAA, GLBA, and similar sector-specific compliance regimes",
    },

    # ───────────────────────────────────────────────────────────────
    #  PRIVACY / DATA RISK
    # ───────────────────────────────────────────────────────────────
    {
        "id": "PRIV_01",
        "category": "Privacy/Data Risk",
        "severity": "High",
        "text": "We may collect, store, and process information about you including your identity, location, device, and behavior across our services.",
        "keywords": ["collect", "store", "process", "behavior"],
        "rationale": "broad data collection triggers GDPR/CCPA obligations and consent requirements",
    },
    {
        "id": "PRIV_02",
        "category": "Privacy/Data Risk",
        "severity": "High",
        "text": "Your information may be shared with affiliated companies, business partners, advertising networks, and service providers for marketing purposes.",
        "keywords": ["share", "third parties", "marketing", "advertising"],
        "rationale": "third-party sharing for marketing typically requires explicit opt-in consent",
    },
    {
        "id": "PRIV_03",
        "category": "Privacy/Data Risk",
        "severity": "High",
        "text": "We monetize user data through sale or licensing arrangements with data brokers and analytics partners.",
        "keywords": ["sell", "monetize", "data brokers"],
        "rationale": "selling personal data is restricted in many jurisdictions and triggers CCPA opt-out rights",
    },
    {
        "id": "PRIV_04",
        "category": "Privacy/Data Risk",
        "severity": "High",
        "text": "Personal data may be transferred to and stored on servers located in countries outside your country of residence.",
        "keywords": ["transfer", "cross-border", "international"],
        "rationale": "cross-border data transfers require adequacy decisions or standard contractual clauses under GDPR",
    },
    {
        "id": "PRIV_05",
        "category": "Privacy/Data Risk",
        "severity": "High",
        "text": "The service collects biometric identifiers including facial geometry, fingerprints, or voice patterns for authentication and personalization.",
        "keywords": ["biometric", "facial", "fingerprint"],
        "rationale": "biometric data is subject to heightened protection under BIPA and similar laws",
    },
    {
        "id": "PRIV_06",
        "category": "Privacy/Data Risk",
        "severity": "Medium",
        "text": "We use cookies, pixels, and similar tracking technologies to monitor your activity on our website and across the web.",
        "keywords": ["cookies", "tracking", "pixels"],
        "rationale": "tracking tech typically requires informed consent under ePrivacy / GDPR",
    },
    {
        "id": "PRIV_07",
        "category": "Privacy/Data Risk",
        "severity": "Medium",
        "text": "User records and personal information are retained indefinitely unless the user actively requests deletion.",
        "keywords": ["retain", "indefinitely", "deletion"],
        "rationale": "indefinite retention conflicts with GDPR data minimization principles",
    },
    {
        "id": "PRIV_08",
        "category": "Privacy/Data Risk",
        "severity": "High",
        "text": "In the event of a security incident affecting user data, we will notify affected parties as required by law.",
        "keywords": ["breach", "incident", "notify"],
        "rationale": "breach notification obligations vary by jurisdiction — vague language invites delayed notice",
    },

    # ───────────────────────────────────────────────────────────────
    #  FINANCIAL RISK
    # ───────────────────────────────────────────────────────────────
    {
        "id": "FIN_01",
        "category": "Financial Risk",
        "severity": "High",
        "text": "This agreement shall automatically renew for successive terms of equal length unless either party provides written notice of non-renewal.",
        "keywords": ["automatic renewal", "successive terms"],
        "rationale": "auto-renewal can create unintended long-term financial commitments",
    },
    {
        "id": "FIN_02",
        "category": "Financial Risk",
        "severity": "High",
        "text": "All payments made under this agreement are final and non-refundable under any circumstances, including early termination or dissatisfaction.",
        "keywords": ["non-refundable", "final"],
        "rationale": "non-refundable payments eliminate recourse even when service fails",
    },
    {
        "id": "FIN_03",
        "category": "Financial Risk",
        "severity": "High",
        "text": "The Provider may adjust pricing, fees, and billing terms from time to time upon notice to the Customer.",
        "keywords": ["adjust pricing", "change fees"],
        "rationale": "unilateral price changes create budget uncertainty and lock-in risk",
    },
    {
        "id": "FIN_04",
        "category": "Financial Risk",
        "severity": "High",
        "text": "Termination prior to the end of the initial term incurs a penalty equal to the remaining contract value.",
        "keywords": ["early termination", "penalty"],
        "rationale": "full-value termination penalties eliminate flexibility to exit a failing relationship",
    },
    {
        "id": "FIN_05",
        "category": "Financial Risk",
        "severity": "Medium",
        "text": "Overdue balances shall accrue interest at the maximum rate permitted by applicable law.",
        "keywords": ["interest", "overdue", "late payment"],
        "rationale": "maximum-rate interest clauses are punitive; some may be unenforceable",
    },
    {
        "id": "FIN_06",
        "category": "Financial Risk",
        "severity": "Medium",
        "text": "The Customer commits to a minimum annual purchase volume, regardless of actual usage or need.",
        "keywords": ["minimum commitment", "minimum purchase"],
        "rationale": "minimum commitments create fixed obligations disconnected from actual consumption",
    },
    {
        "id": "FIN_07",
        "category": "Financial Risk",
        "severity": "Medium",
        "text": "The Provider reserves the right to withhold payment or offset amounts owed to the Customer against any disputed claims.",
        "keywords": ["setoff", "withhold", "offset"],
        "rationale": "unilateral setoff rights give the provider leverage in disputes",
    },

    # ───────────────────────────────────────────────────────────────
    #  CONTRACTUAL AMBIGUITY
    # ───────────────────────────────────────────────────────────────
    {
        "id": "AMB_01",
        "category": "Contractual Ambiguity",
        "severity": "High",
        "text": "The Provider may modify, update, or discontinue these terms at any time, with changes becoming effective upon posting.",
        "keywords": ["modify", "update", "at any time"],
        "rationale": "unilateral modification rights undermine the certainty of the original agreement",
    },
    {
        "id": "AMB_02",
        "category": "Contractual Ambiguity",
        "severity": "High",
        "text": "The company may take such actions as it deems necessary or appropriate to protect its interests and the interests of its users.",
        "keywords": ["deems necessary", "sole discretion"],
        "rationale": "subjective standards give one party unreviewable discretion",
    },
    {
        "id": "AMB_03",
        "category": "Contractual Ambiguity",
        "severity": "Medium",
        "text": "Services will be delivered on a commercially reasonable basis within a reasonable timeframe.",
        "keywords": ["commercially reasonable", "reasonable timeframe"],
        "rationale": "'commercially reasonable' and 'reasonable timeframe' lack measurable standards",
    },
    {
        "id": "AMB_04",
        "category": "Contractual Ambiguity",
        "severity": "Medium",
        "text": "Obligations are subject to such conditions and limitations as the Provider may establish from time to time.",
        "keywords": ["subject to", "from time to time"],
        "rationale": "open-ended condition-setting power makes obligations unpredictable",
    },
    {
        "id": "AMB_05",
        "category": "Contractual Ambiguity",
        "severity": "Medium",
        "text": "The scope of services includes, without limitation, such activities as the parties may mutually determine to be appropriate.",
        "keywords": ["without limitation", "as appropriate"],
        "rationale": "non-exhaustive scope and subjective appropriateness standard invite scope disputes",
    },
    {
        "id": "AMB_06",
        "category": "Contractual Ambiguity",
        "severity": "High",
        "text": "Continued use of the service after changes are made constitutes acceptance of the modified terms.",
        "keywords": ["continued use", "acceptance"],
        "rationale": "'constructive acceptance' via continued use may not meet enforceability standards in some jurisdictions",
    },
    {
        "id": "AMB_07",
        "category": "Contractual Ambiguity",
        "severity": "Medium",
        "text": "Material breaches must be addressed within a reasonable period, where materiality shall be determined in good faith by the non-breaching party.",
        "keywords": ["material breach", "good faith"],
        "rationale": "undefined materiality plus unilateral determination creates asymmetric power",
    },
]


def get_canonical_texts():
    """Return just the text fields — used for embedding."""
    return [c["text"] for c in CANONICAL_CLAUSES]


def get_canonical_by_index(idx: int) -> dict:
    return CANONICAL_CLAUSES[idx]


def count_by_category() -> dict:
    """Diagnostic helper."""
    from collections import Counter
    return dict(Counter(c["category"] for c in CANONICAL_CLAUSES))
