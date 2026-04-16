"""
AI-Like Explanation Engine
──────────────────────────
Generates human-readable explanations for detected risks WITHOUT calling
any external LLM. Uses a template system keyed on:
  • risk category
  • detected keywords
  • detection sources (regex / semantic / both)
  • severity

The output is intentionally richer than a static rule-defined string:
it adapts to which specific pattern triggered, whether multiple layers
confirmed the finding, and the severity level.

Design:
  1. Category-level template bank — one per (category, pattern-key) pair,
     plus a "_default" fallback for each category.
  2. A prefix based on severity ("⚠ HIGH SEVERITY — ", etc.)
  3. A suffix that reflects WHICH layer detected the risk:
       • regex only   → no suffix
       • semantic only → "Detected via similarity to: <rationale>"
       • both layers  → "Confirmed by both pattern matching and semantic analysis"

This keeps explanations informative and auditable without any ML generation.
"""
from __future__ import annotations

from typing import Dict, List


# ── Templates ─────────────────────────────────────────────────────────────────
#
# Keyed by risk category. Each category has a dict mapping a substring
# of the matched keyword to the explanation template. First match wins.
# "_default" is the fallback when no keyword-specific template applies.

EXPLANATION_TEMPLATES: Dict[str, Dict[str, str]] = {

    "Liability Risk": {
        "indemnif": (
            "This clause introduces significant liability exposure through "
            "indemnification. You may be required to cover legal costs, "
            "settlements, and damages arising from third-party claims — "
            "potentially without an upper limit."
        ),
        "hold harmless": (
            "This clause contains 'hold harmless' language, which waives "
            "your right to seek compensation for certain harms and effectively "
            "shifts legal risk onto your side."
        ),
        "make whole": (
            "This clause uses 'make whole' language, which functions like "
            "indemnification even without using the word. You may be liable "
            "for the full losses of the other party following a breach."
        ),
        "unlimited": (
            "This clause exposes you to unlimited liability. There is no "
            "ceiling on potential damages, meaning your exposure could "
            "exceed the value of the entire agreement."
        ),
        "as-is": (
            "This clause provides services 'as-is' with no warranties. "
            "You accept the services in their current state regardless "
            "of defects, unfitness, or lack of reliability."
        ),
        "as is": (
            "This clause provides services 'as is' with no warranties. "
            "You accept the services in their current state regardless "
            "of defects, unfitness, or lack of reliability."
        ),
        "liquidated damages": (
            "This clause pre-sets penalty amounts that may apply even if "
            "the actual harm is smaller. Liquidated damages clauses can be "
            "enforceable even when disproportionate to real losses."
        ),
        "force majeure": (
            "This clause excuses performance during force majeure events. "
            "Overly broad triggers may allow the counterparty to avoid "
            "obligations in situations you wouldn't normally expect."
        ),
        "consequential": (
            "This clause excludes consequential, indirect, or punitive "
            "damages — the damage categories that typically make up the "
            "real cost of a major breach. Even if you win a dispute, "
            "recovery may be minimal."
        ),
        "warranty": (
            "This clause limits or disclaims warranties, reducing your "
            "ability to recover when the service fails to meet expectations."
        ),
        "waive": (
            "This clause contains a waiver of rights. You give up specific "
            "legal protections or remedies that would otherwise be available."
        ),
        "aggregate liability": (
            "This clause caps total liability at a specific amount. "
            "Verify whether the cap adequately covers your worst-case "
            "exposure from a service failure or breach."
        ),
        "_default": (
            "This clause shifts liability or limits legal recourse in ways "
            "that could expose you to significant financial or legal risk."
        ),
    },

    "Compliance Risk": {
        "gdpr": (
            "This clause implicates GDPR obligations. Non-compliance with "
            "EU data protection law can trigger fines of up to 4% of global "
            "annual turnover or €20 million, whichever is higher."
        ),
        "hipaa": (
            "This clause implicates HIPAA obligations around protected "
            "health information. Violations carry civil penalties and, for "
            "willful neglect, criminal liability."
        ),
        "ccpa": (
            "This clause references CCPA obligations. California residents "
            "have specific opt-out, disclosure, and deletion rights that "
            "must be honored under penalty of regulatory action."
        ),
        "sox": (
            "This clause references Sarbanes-Oxley obligations. SOX violations "
            "by public-company officers can result in criminal liability."
        ),
        "pci": (
            "This clause implicates PCI-DSS obligations for handling payment "
            "card data. Non-compliance can result in loss of processing "
            "privileges and significant fines."
        ),
        "anti-bribery": (
            "This clause references anti-bribery or anti-corruption laws. "
            "FCPA and UK Bribery Act violations carry severe criminal "
            "penalties including imprisonment of individuals."
        ),
        "fcpa": (
            "This clause references the Foreign Corrupt Practices Act. "
            "FCPA violations can result in criminal prosecution of "
            "individuals and massive corporate fines."
        ),
        "sanction": (
            "This clause references economic sanctions compliance. OFAC "
            "and EU sanctions violations carry strict-liability penalties "
            "regardless of intent."
        ),
        "export control": (
            "This clause references export control laws (EAR / ITAR). "
            "Violations carry criminal liability — and liability can arise "
            "from technology transfers or cloud data access, not just "
            "physical shipments."
        ),
        "must comply": (
            "This clause creates a broad compliance obligation covering "
            "unspecified 'applicable' laws. Because the scope is open-ended, "
            "it effectively shifts regulatory risk onto you."
        ),
        "applicable law": (
            "This clause references 'applicable law' without specifying "
            "which jurisdiction's laws govern. Ambiguous governing law "
            "can lead to jurisdiction disputes and conflict of laws issues."
        ),
        "regulatory": (
            "This clause creates regulatory obligations without clearly "
            "defining their scope. Ambiguous regulatory requirements can "
            "create unexpected compliance burdens."
        ),
        "license": (
            "This clause requires you to obtain and maintain licenses "
            "or permits. Verify which licenses apply in your jurisdiction "
            "and the cost of obtaining them."
        ),
        "industry standard": (
            "This clause references 'industry standards' — a vague and "
            "disputed legal standard. Expectations can shift over time "
            "and may be difficult to enforce objectively."
        ),
        "_default": (
            "This clause creates compliance obligations whose scope is "
            "either broad or undefined, potentially exposing you to "
            "regulatory risk from multiple legal frameworks."
        ),
    },

    "Privacy/Data Risk": {
        "personal data": (
            "This clause involves personal data processing, which triggers "
            "obligations under GDPR, CCPA, and similar frameworks including "
            "consent, lawful basis, data minimization, and subject rights."
        ),
        "pii": (
            "This clause involves personally identifiable information (PII), "
            "which triggers privacy law obligations including consent, "
            "secure storage, and breach notification requirements."
        ),
        "sell": (
            "This clause involves the sale of user data. CCPA requires an "
            "opt-out mechanism; other jurisdictions may prohibit data sales "
            "entirely without explicit opt-in."
        ),
        "monetize": (
            "This clause involves monetizing user data. Such practices "
            "typically require informed consent and may conflict with "
            "user expectations about privacy."
        ),
        "share": (
            "This clause involves sharing data with third parties. Third-"
            "party sharing typically requires data processing agreements, "
            "due diligence, and user disclosure under GDPR / CCPA."
        ),
        "third part": (
            "This clause involves third-party data sharing, which requires "
            "contractual safeguards and transparent disclosure to data subjects."
        ),
        "data breach": (
            "This clause references data breach handling. Verify notification "
            "timelines (e.g., 72 hours under GDPR) and whether your obligations "
            "are clearly defined."
        ),
        "breach": (
            "This clause references breach/incident handling. Most privacy "
            "regimes impose strict notification timelines following discovery."
        ),
        "biometric": (
            "This clause involves biometric data, which receives heightened "
            "protection under BIPA (Illinois) and similar laws. Misuse "
            "can result in statutory damages per individual."
        ),
        "track": (
            "This clause involves tracking user activity. Behavioral tracking "
            "typically requires informed consent and clear disclosure."
        ),
        "cookie": (
            "This clause references cookies or tracking technologies. Under "
            "GDPR / ePrivacy, non-essential cookies require informed consent "
            "before being set."
        ),
        "collect": (
            "This clause involves data collection. Privacy laws require a "
            "lawful basis, stated purpose, and user notice before collecting "
            "personal data."
        ),
        "retain": (
            "This clause defines (or fails to define) data retention periods. "
            "Indefinite retention conflicts with GDPR data minimization principles."
        ),
        "transfer": (
            "This clause involves cross-border data transfers. Under GDPR, "
            "international transfers require adequacy decisions or standard "
            "contractual clauses."
        ),
        "encrypt": (
            "This clause references encryption. Verify whether specific "
            "standards are mandated (e.g., AES-256, TLS 1.3) and at which "
            "layer encryption is applied."
        ),
        "opt-out": (
            "This clause offers an opt-out mechanism. Verify it is accessible, "
            "effective, and meets the specific requirements of applicable "
            "privacy laws (e.g., CCPA's 'Do Not Sell' link)."
        ),
        "_default": (
            "This clause involves handling personal information in ways "
            "that implicate privacy obligations and may require user consent, "
            "disclosure, or specific safeguards."
        ),
    },

    "Financial Risk": {
        "automatic renew": (
            "This clause provides for automatic renewal. You may be locked "
            "into additional terms unless you actively cancel within a specific "
            "window — creating unintended long-term financial commitments."
        ),
        "auto-renew": (
            "This clause contains auto-renewal language. Missing the "
            "cancellation window will bind you to another full term."
        ),
        "non-refundable": (
            "This clause makes payments non-refundable. You lose the ability "
            "to recover funds even if the service fails to perform."
        ),
        "early termination": (
            "This clause imposes an early termination fee. Exiting the "
            "agreement before the end of the term will trigger significant "
            "financial penalties."
        ),
        "penalty": (
            "This clause creates a financial penalty. Depending on "
            "jurisdiction and drafting, some penalty clauses may be "
            "unenforceable but most are not."
        ),
        "interest": (
            "This clause imposes interest on overdue amounts. Verify the "
            "rate is lawful in your jurisdiction — some states cap the "
            "maximum rate on commercial debt."
        ),
        "unilateral": (
            "This clause allows unilateral changes to pricing or fees. The "
            "counterparty can increase your costs without negotiation or "
            "your consent."
        ),
        "change": (
            "This clause allows pricing changes over time. Budget planning "
            "is difficult when the counterparty can raise fees unilaterally."
        ),
        "minimum": (
            "This clause imposes minimum purchase or commitment obligations. "
            "You must pay regardless of actual usage, creating fixed overhead "
            "disconnected from value received."
        ),
        "cancellation fee": (
            "This clause imposes cancellation fees. Review the conditions "
            "that trigger the fee and whether they apply even when the "
            "counterparty is at fault."
        ),
        "setoff": (
            "This clause grants setoff rights. The counterparty can deduct "
            "disputed amounts from what they owe you, giving them leverage "
            "in payment disputes."
        ),
        "escrow": (
            "This clause involves escrow. Review the release conditions "
            "and any delays they may introduce to your cash flow."
        ),
        "currency": (
            "This clause involves foreign currency exposure. Exchange rate "
            "movement can significantly affect the economic terms of the "
            "agreement over time."
        ),
        "_default": (
            "This clause creates financial obligations or penalties that "
            "could have material cost implications. Review the specific "
            "amounts, triggers, and caps."
        ),
    },

    "Contractual Ambiguity": {
        "sole discretion": (
            "This clause grants 'sole discretion' to one party. Unilateral "
            "discretion clauses give one side unchecked decision-making power "
            "with no objective standard for review."
        ),
        "absolute discretion": (
            "This clause grants absolute discretion to one party. This "
            "effectively means the counterparty decides the outcome of "
            "disputed matters, with minimal oversight."
        ),
        "discretion": (
            "This clause grants discretion to one party. Verify whether "
            "the discretion is bounded by any objective standard or "
            "reasonableness requirement."
        ),
        "at any time": (
            "This clause allows changes 'at any time'. This undermines "
            "contractual certainty — the terms you agreed to today may "
            "not be the terms you're bound by tomorrow."
        ),
        "deem": (
            "This clause uses subjective 'deemed' language. When one party "
            "decides what counts as appropriate or necessary, the standard "
            "becomes effectively unreviewable."
        ),
        "reasonable": (
            "This clause uses a 'reasonable' standard. Reasonableness is "
            "subjective and interpreted differently by courts, creating "
            "uncertainty about required performance levels."
        ),
        "including but not limited to": (
            "This clause uses a non-exhaustive list ('including but not "
            "limited to'). Scope can expand beyond what either party "
            "contemplated at signing."
        ),
        "without limitation": (
            "This clause uses 'without limitation' language. Open-ended "
            "lists may expand in scope unpredictably over the life of "
            "the agreement."
        ),
        "material": (
            "This clause uses a 'material' standard without defining it. "
            "Disputes about what counts as 'material' are one of the most "
            "common sources of contract litigation."
        ),
        "from time to time": (
            "This clause uses 'from time to time' to describe when changes "
            "may occur. This vague temporal language makes it hard to "
            "predict when obligations will shift."
        ),
        "good faith": (
            "This clause references a 'good faith' obligation. Good faith "
            "is context-dependent and may create implied duties not "
            "explicitly stated in the contract."
        ),
        "continued use": (
            "This clause treats 'continued use' as acceptance of future "
            "changes. Constructive acceptance via use may not meet "
            "enforceability standards in all jurisdictions."
        ),
        "customary": (
            "This clause references 'customary' terms or practices. "
            "Customary standards introduce external, undefined requirements "
            "into the agreement."
        ),
        "generally accepted": (
            "This clause references 'generally accepted' practices. "
            "Vague industry practice standards may be difficult to "
            "establish or enforce objectively."
        ),
        "_default": (
            "This clause contains ambiguous or open-ended language that "
            "weakens contractual certainty and gives one party room to "
            "interpret obligations in its favor."
        ),
    },
}


# ── Severity prefix ───────────────────────────────────────────────────────────
_SEVERITY_PREFIX = {
    "High":   "⚠ HIGH SEVERITY — ",
    "Medium": "⚡ CAUTION — ",
    "Low":    "ℹ Note — ",
}


# ── Main generator ───────────────────────────────────────────────────────────

def generate_explanation(risk: dict) -> str:
    """
    Dynamically build an explanation for a detected risk.

    Uses:
      • risk_type         → selects template bank
      • keywords_matched  → picks specific template within the bank
      • severity          → prefix
      • sources           → suffix (regex / semantic / both)
      • canonical_rationale (semantic only) → added to suffix

    The goal is an explanation that feels generated, not hardcoded —
    because the combination of inputs varies per-clause.
    """
    category = risk.get("risk_type", "")
    keywords: List[str] = risk.get("keywords_matched", []) or []
    severity = risk.get("severity", "Medium")
    sources = risk.get("sources", [])
    clause_text = (risk.get("text_snippet") or "").lower()

    # ── 1. Select template from category bank ───────────────────────────────
    bank = EXPLANATION_TEMPLATES.get(category, {})
    body = None

    # Match template keys against the ACTUAL CLAUSE TEXT — not the keyword
    # list (which may contain canonical KB keywords that never appeared in
    # the user's document, causing hallucinated explanations like HIPAA
    # warnings on non-healthcare text).
    for template_key, template_text in bank.items():
        if template_key == "_default":
            continue
        if template_key in clause_text:
            body = template_text
            break

    if not body:
        body = bank.get(
            "_default",
            f"This clause raises {category.lower()} concerns.",
        )

    # ── 1b. Evidence phrase — makes each explanation unique per clause ──────
    evidence = [k for k in keywords if k.lower() in clause_text]
    if evidence:
        evidence_str = ", ".join(f'"{e}"' for e in evidence[:3])
        body += f" (Evidence: {evidence_str})"

    # ── 2. Severity prefix ──────────────────────────────────────────────────
    prefix = _SEVERITY_PREFIX.get(severity, "")

    # ── 3. Detection source suffix ──────────────────────────────────────────
    has_regex = "regex" in sources
    has_semantic = "semantic" in sources

    if has_regex and has_semantic:
        suffix = (
            " [Confirmed by both pattern matching and semantic similarity.]"
        )
    elif has_semantic:
        sim = risk.get("semantic_similarity")
        if sim is not None and sim < 0.55:
            prefix = "ℹ Low-confidence signal — "
            suffix = ""
        else:
            suffix = " [Detected by semantic similarity analysis.]"
    elif has_regex:
        suffix = ""
    else:
        suffix = ""

    return prefix + body + suffix
