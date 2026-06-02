"""
Regex-based risk rule engine — FALLBACK layer.

Contains all regex risk patterns organized by category, and provides
a clean `scan()` interface for detecting risks in clause text.

Used when the ML classifier is unavailable.
"""
import re
from typing import Dict, List, Tuple

from backend.utils.text_utils import compute_tfidf_boost


# ─────────────────────────────────────────────
#  RISK RULE DEFINITIONS
#  Each rule: (pattern, severity, explanation, corpus_freq)
#  corpus_freq: estimated frequency in general text (used for TF-IDF boost)
# ─────────────────────────────────────────────

RISK_RULES: Dict[str, List[Tuple]] = {

    "Compliance Risk": [
        # (regex_pattern, base_severity, explanation, corpus_freq)
        (r'\b(GDPR|General Data Protection Regulation)\b', "High",
         "Reference to GDPR indicates obligations under EU data protection law. Non-compliance carries fines up to 4% of global turnover.", 0.01),

        (r'\b(HIPAA|Health Insurance Portability)\b', "High",
         "HIPAA reference signals healthcare data obligations. Violations can result in criminal penalties and civil fines.", 0.01),

        (r'\b(CCPA|California Consumer Privacy Act)\b', "High",
         "CCPA imposes consumer data rights obligations for California residents. Non-compliance may trigger regulatory action.", 0.01),

        (r'\b(SOX|Sarbanes.Oxley)\b', "High",
         "SOX reference indicates financial reporting obligations for public companies. Violations may result in criminal liability.", 0.01),

        (r'\b(PCI.DSS|Payment Card Industry)\b', "High",
         "PCI-DSS compliance required for payment card data processing. Non-compliance can result in card processing suspension.", 0.01),

        (r'\bmust comply with\s+(?:all\s+)?(?:applicable\s+)?(?:laws?|regulations?|rules?|requirements?)\b', "High",
         "Broad compliance obligation with unspecified laws creates open-ended legal exposure.", 0.05),

        (r'\bregulatory\s+(?:approval|requirement|compliance|obligation)\b', "Medium",
         "Regulatory requirements mentioned without specificity may create ambiguous obligations.", 0.08),

        (r'\bexport\s+(?:control|restriction|law|regulation|compliance)\b', "High",
         "Export control laws (EAR, ITAR) carry severe penalties including criminal prosecution.", 0.02),

        (r'\b(anti.?bribery|anti.?corruption|FCPA|Bribery Act)\b', "High",
         "Anti-bribery law reference. FCPA and UK Bribery Act violations carry criminal penalties.", 0.01),

        (r'\bsanction[s]?\b(?!\s+(?:from|by|against))', "High",
         "Sanctions compliance (OFAC, EU) is critical — violations can result in severe financial and criminal penalties.", 0.03),

        (r'\bindustry\s+standard[s]?\b', "Low",
         "Vague reference to 'industry standards' may be difficult to enforce or verify objectively.", 0.15),
    ],

    "Liability Risk": [
        (r'\bindemnif(?:y|ied|ication|ies)\b', "High",
         "Indemnification clause requires one party to compensate the other for losses. Scope and caps are critical to review.", 0.02),

        (r'\bhold\s+harmless\b', "High",
         "'Hold harmless' clauses waive rights to sue. Broad versions can eliminate remedies for serious harm.", 0.02),

        (r'\bunlimited\s+liability\b', "High",
         "Unlimited liability exposure creates catastrophic financial risk with no ceiling on damages.", 0.005),

        (r'\bliquidated\s+damages?\b', "High",
         "Liquidated damages clauses pre-set penalty amounts. May be enforceable even if actual harm is lower.", 0.02),

        (r'\blimitation\s+of\s+liability\b', "Medium",
         "Liability cap present — verify the cap amount is adequate and note exclusions from the cap.", 0.05),

        (r'\bexclusiv(?:e|ity)\s+(?:remedy|remedies)\b', "Medium",
         "Exclusive remedy clauses restrict available legal recourse to specific remedies only.", 0.03),

        (r'\bwithout\s+(?:any\s+)?(?:liability|recourse|warranty)\b', "High",
         "Express disclaimer of liability. May eliminate legal recourse for significant harms.", 0.04),

        (r'\bno\s+warrant(?:y|ies|ee)\b|AS.IS\b|without\s+warranty\b', "Medium",
         "As-is warranty disclaimer — no guarantees of fitness or quality. Buyer assumes condition risk.", 0.06),

        (r'\b(?:consequential|incidental|punitive|indirect)\s+damages?\b', "Medium",
         "Damages categories referenced — check whether these are excluded or capped in the agreement.", 0.04),

        (r'\bforce\s+majeure\b', "Medium",
         "Force majeure clause — review triggers and notice requirements. Overly broad clauses can excuse non-performance.", 0.04),

        (r'\bnegligence\b', "Medium",
         "Negligence referenced — determine whether liability for negligence is limited, excluded, or retained.", 0.06),

        (r'\bwarrant(?:y|ies|ee)\b', "Low",
         "Warranty terms present — review scope, duration, and exclusions carefully.", 0.10),
    ],

    "Privacy/Data Risk": [
        (r'\bpersonal(?:ly)?\s+(?:identifiable\s+)?(?:information|data)\b|PII\b', "High",
         "Personal/PII data processing triggers privacy obligations under GDPR, CCPA, and other frameworks.", 0.04),

        (r'\bsell(?:ing|s)?\s+(?:your\s+)?(?:data|information|profile)\b', "High",
         "Explicit sale of user data raises significant privacy concerns and may violate consumer protection laws.", 0.01),

        (r'\bshare\s+(?:your\s+)?(?:data|information)\s+with\s+third.part(?:y|ies)\b', "High",
         "Third-party data sharing requires informed consent under most privacy regulations.", 0.02),

        (r'\bdata\s+breach\b', "High",
         "Data breach reference — verify incident response obligations, notification timelines, and liability caps.", 0.03),

        (r'\bbiometric(?:\s+data)?\b', "High",
         "Biometric data is subject to heightened protection under BIPA (Illinois) and similar state laws.", 0.01),

        (r'\btrack(?:ing|ed|s)?\s+(?:your\s+)?(?:location|activity|behavior|browsing)\b', "High",
         "Behavioral or location tracking may require explicit consent and disclosure under privacy laws.", 0.03),

        (r'\bcollect(?:ing|s|ed)?\s+(?:your\s+)?(?:data|information|cookies)\b', "Medium",
         "Data collection requires purpose limitation and legal basis under privacy regulations.", 0.06),

        (r'\bcookie[s]?\b', "Low",
         "Cookie use requires disclosure and, under GDPR/ePrivacy, informed consent for non-essential cookies.", 0.12),

        (r'\bencrypt(?:ion|ed|s)?\b', "Low",
         "Encryption referenced — verify whether specific standards (AES-256, TLS 1.3) are mandated.", 0.08),

        (r'\bdata\s+retent(?:ion|ion period)\b', "Medium",
         "Data retention policies must align with regulatory minimums and stated collection purposes.", 0.05),

        (r'\bthird.part(?:y|ies)\s+(?:service|provider|partner|vendor)\b', "Medium",
         "Third-party data processor relationships require data processing agreements and due diligence.", 0.06),

        (r'\bopt.out\b', "Low",
         "Opt-out mechanism mentioned — verify it is accessible and effective per regulatory requirements.", 0.08),
    ],

    "Financial Risk": [
        (r'\bautomatic(?:ally)?\s+renew(?:al|s|ed)?\b|auto.renew', "High",
         "Automatic renewal clauses can create unexpected long-term financial commitments without active consent.", 0.02),

        (r'\bearly\s+termination\s+(?:fee|penalty|charge)\b', "High",
         "Early termination fees can impose significant costs. Verify fee calculation method and caps.", 0.02),

        (r'\bpenalt(?:y|ies)\b', "High",
         "Penalty clauses create financial exposure. Distinguish from liquidated damages — some penalties are unenforceable.", 0.05),

        (r'\binterest\s+(?:rate|charges?)\s+of\s+[\d\.]+\s*%', "High",
         "Specific interest rate on unpaid amounts — verify this rate is legally permissible in applicable jurisdiction.", 0.02),

        (r'\bunilateral(?:ly)?\s+(?:change|modify|adjust|increase)\s+(?:price|fee|rate|cost)\b', "High",
         "Unilateral price change rights allow the counterparty to increase costs without negotiation or consent.", 0.02),

        (r'\bnon.refundable\b', "Medium",
         "Non-refundable payments eliminate recourse for service failures. Assess against value and risk.", 0.04),

        (r'\bcancellation\s+(?:fee|charge|penalty)\b', "Medium",
         "Cancellation fees may apply even for non-performance by the other party. Review trigger conditions.", 0.03),

        (r'\bpayment\s+within\s+\d+\s+days?\b|net\s+\d+\b', "Low",
         "Payment terms defined — review for late payment penalties and dispute resolution provisions.", 0.10),

        (r'\bescrow\b', "Low",
         "Escrow arrangements affect cash flow and access to funds. Review release conditions carefully.", 0.05),

        (r'\bmin(?:imum)?\s+(?:purchase|order|commitment|spend)\b', "Medium",
         "Minimum purchase/spend commitments create fixed financial obligations regardless of actual need.", 0.04),

        (r'\bsetoff\b|right\s+of\s+offset\b', "Medium",
         "Setoff rights allow the counterparty to deduct amounts owed to them from payments due to you.", 0.03),

        (r'\bcurrency\s+(?:risk|fluctuation|conversion)\b', "Medium",
         "Foreign currency exposure can cause significant financial losses in cross-border agreements.", 0.03),
    ],

    "Contractual Ambiguity": [
        (r'\bat\s+(?:our|its|their|(?:the\s+)?company\'?s?)\s+(?:sole\s+)?discretion\b', "High",
         "Unilateral discretion clauses give one party unchecked decision-making power without criteria or standards.", 0.03),

        (r'\bmay\s+change\s+(?:at\s+any\s+time|without\s+notice|from\s+time\s+to\s+time)\b', "High",
         "Right to change terms at any time without notice undermines contractual certainty and predictability.", 0.03),

        (r'\bas\s+(?:we\s+)?deem(?:ed)?\s+(?:appropriate|necessary|fit|reasonable)\b', "High",
         "Subjective 'deemed appropriate' standard gives one party broad, unreviewable authority.", 0.02),

        (r'\breasonable\s+(?:efforts?|endeavours?|notice|time)\b', "Medium",
         "'Reasonable' is a subjective standard that creates ambiguity about required performance level.", 0.08),

        (r'\bincluding\s+but\s+not\s+limited\s+to\b|including\s+without\s+limitation\b', "Low",
         "Non-exhaustive lists expand scope unpredictably. May include items not contemplated at signing.", 0.12),

        (r'\bmaterial(?:ly)?\s+(?:adverse|change|breach)\b', "Medium",
         "'Material' is an undefined standard. Disputes about what constitutes materiality are common.", 0.06),

        (r'\bfrom\s+time\s+to\s+time\b', "Low",
         "Vague temporal reference creates uncertainty about when changes or obligations take effect.", 0.10),

        (r'\bsubject\s+to\s+change\b', "Medium",
         "Terms subject to change without clear notice requirements create instability in the agreement.", 0.06),

        (r'\bgood\s+faith\b', "Low",
         "Good faith obligation is context-dependent and may create implied duties not explicitly stated.", 0.09),

        (r'\bin\s+its\s+(?:sole\s+)?(?:and\s+absolute\s+)?discretion\b', "High",
         "Absolute discretion clauses effectively give one party uncapped authority over key decisions.", 0.02),

        (r'\bcustomary\s+(?:terms?|practice|standard)\b', "Medium",
         "Reference to 'customary' terms introduces external, undefined standards into the agreement.", 0.04),

        (r'\bgenerally\s+accepted\b|(?:common|normal|standard)\s+practice\b', "Low",
         "Vague industry practice references may be disputed or difficult to establish objectively.", 0.08),
    ],
}


def _find_matches_in_clause(
    clause_text: str, clause_idx: int, rules: List[Tuple], risk_type: str
) -> List[Dict]:
    """
    Apply all regex rules for one risk category against a single clause.
    Returns one risk dict per regex hit, tagged with the clause index so
    later stages can merge with semantic hits on the same clause.
    """
    results = []
    for pattern, base_severity, explanation, corpus_freq in rules:
        for match in re.finditer(pattern, clause_text, re.IGNORECASE):
            matched_text = match.group(0)

            # Use the whole clause as the snippet
            snippet = clause_text if len(clause_text) <= 300 else clause_text[:297] + "..."

            # TF-IDF boost: frequent-in-clause terms get a confidence bump
            tfidf_boost = compute_tfidf_boost(matched_text, clause_text, corpus_freq)
            base_score = {"Low": 0.45, "Medium": 0.65, "High": 0.85}[base_severity]
            regex_score = min(1.0, base_score + tfidf_boost * 0.15)

            results.append({
                "clause_idx": clause_idx,
                "risk_type": risk_type,
                "severity": base_severity,
                "text_snippet": snippet,
                "explanation": explanation,
                "score": round(regex_score, 3),
                "keywords_matched": [matched_text],
                "sources": ["regex"],
                "_pattern_explanation": explanation,
            })
    return results


def scan(clauses: List[str]) -> List[Dict]:
    """
    Run all regex risk rules across a list of clauses.

    Args:
        clauses: List of clause texts (from segmentation).

    Returns:
        List of risk dicts, one per regex match, with clause_idx,
        risk_type, severity, score, etc.
    """
    results: List[Dict] = []
    for idx, clause in enumerate(clauses):
        for risk_type, rules in RISK_RULES.items():
            results.extend(
                _find_matches_in_clause(clause, idx, rules, risk_type)
            )
    return results
