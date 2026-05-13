"""
LLM-Based Clause Extractor
───────────────────────────
Extracts structured fields from contract clauses using a pluggable LLM backend.

LLM routing (priority order):
  1. ANTHROPIC_API_KEY + claude-* model  → Anthropic API
  2. GROQ_API_KEY set                    → Groq free API (llama-3.1-8b-instant)
  3. fallback                            → Ollama local (llama3.1:8b)

Each extractor call:
  1. Takes raw clause text + clause type
  2. Sends a structured extraction prompt to the LLM
  3. Parses the JSON response into the appropriate Pydantic schema
  4. Validates all source_text fields exist in the original clause

Retry logic handles malformed JSON and validation failures.
"""
from __future__ import annotations

import json
import logging
import re
import time
from typing import Optional, Type

import requests
from pydantic import BaseModel, ValidationError

from backend.extraction.schemas import (
    EXTRACTION_SCHEMAS, LiabilityExtraction, TerminationExtraction,
    PaymentExtraction, ConfidentialityExtraction, IPExtraction, GoverningLawExtraction,
)

log = logging.getLogger(__name__)

import os

OLLAMA_BASE_URL = "http://localhost:11434"
DEFAULT_MODEL = os.environ.get("LRM_EXTRACTION_MODEL", "llama3.1:8b")

# Set LRM_EXTRACTION_MODEL=claude-haiku-4-5-20251001 (or any claude-* model)
# to use Anthropic API instead of Ollama. Requires ANTHROPIC_API_KEY env var.
_USE_ANTHROPIC = DEFAULT_MODEL.startswith("claude-")

# ── Extraction prompts ───────────────────────────────────────────────────────

_LIABILITY_PROMPT = """\
You are a precise legal contract analyst. Extract ONLY information that is EXPLICITLY stated in the clause below.

CRITICAL RULES — read each one carefully:
1. Default EVERY boolean to false. Only set to true when the clause contains EXPLICIT language matching the rules below.

2. "has_cap" = true ONLY if the clause states a LIABILITY CAP — a maximum dollar amount, formula, or limit on a party's total liability (e.g. "shall not exceed $X", "liability limited to [amount]", "maximum liability"). Insurance coverage amounts are NOT liability caps. Mentions of "liable" or "liability" alone without a cap amount do NOT count.

3. "consequential_damages.excluded" = true ONLY if the clause explicitly EXCLUDES or WAIVES consequential, indirect, incidental, or special damages. The clause must say something like "shall not be liable for any consequential damages" or "no liability for indirect damages". Merely mentioning "damages" or "losses" is NOT enough. A warranty disclaimer is NOT a consequential damages exclusion.

4. "is_mutual" — THIS IS THE HARDEST FIELD. Set to true ONLY when a LIABILITY CAP or DAMAGES EXCLUSION explicitly applies to BOTH parties using language like "either party's liability", "neither party shall be liable", "each party's aggregate liability", or "both parties". IMPORTANT: is_mutual is about WHO THE LIABILITY LIMITATION APPLIES TO, not whether the clause mentions multiple parties. These are FALSE: "The parties agree to cooperate" (cooperation, not liability limit), "FAST shall indemnify Company" (one-sided), "Company shall not be liable" (one party only), "Indemnified Party / Indemnifying Party" (roles, not mutual limitation).

5. "has_indemnification" = true ONLY if the exact words "indemnify", "indemnification", "indemnified", "indemnifying", or "hold harmless" appear.

6. "has_warranty_disclaimer" = true ONLY if the clause DISCLAIMS warranties. Must use "as is", "without warranty", "no warranty", "disclaim warranty", or "provided as-is". FALSE for: "represents and warrants" (making a warranty, not disclaiming), "warranty period" (warranty terms), table of contents entries, integration clauses.

7. "has_carve_outs" = true ONLY if there are explicit exceptions to a LIABILITY CAP or DAMAGES EXCLUSION. The clause must FIRST contain a cap or exclusion, AND THEN list exceptions to it (e.g. "the foregoing limitation shall not apply to willful misconduct", "except for gross negligence", "excluding IP infringement claims"). Exceptions to indemnification obligations alone do NOT count. If the clause has no cap or damages exclusion, has_carve_outs must be false.

8. source_text fields MUST be EXACT word-for-word quotes from the clause. If no quote supports the field, set source_text to null.
9. Respond with ONLY valid JSON. No markdown, no explanation, no text outside the JSON.

SCHEMA:
{{
  "liability_cap": {{
    "has_cap": bool,
    "cap_amount": string or null (e.g. "2x annual fees", "$1,000,000"),
    "cap_source_text": string or null (exact quote),
    "cap_type": "fixed_amount" | "multiple_of_fees" | "fees_paid_period" | "per_incident" | "other" | null
  }},
  "is_mutual": bool or null,
  "mutuality_source_text": string or null,
  "has_carve_outs": bool or null,
  "carve_outs": [list of carve-out categories as strings],
  "carve_outs_source_text": string or null,
  "consequential_damages": {{
    "excluded": bool or null,
    "exclusion_source_text": string or null,
    "exclusion_is_mutual": bool or null
  }},
  "has_indemnification": bool or null,
  "indemnification_source_text": string or null,
  "has_warranty_disclaimer": bool or null,
  "warranty_disclaimer_source_text": string or null,
  "extraction_confidence": float 0.0-1.0
}}

CLAUSE TEXT:
{clause_text}

JSON:"""


_TERMINATION_PROMPT = """\
You are a precise legal contract analyst. Extract ONLY information that is EXPLICITLY stated in the clause below.

CRITICAL RULES — read each one carefully:
1. Default EVERY boolean to false. Only set to true when the clause contains EXPLICIT language matching the rules below.

2. "has_termination_for_cause" = true ONLY if the clause allows termination due to a material breach, default, insolvency, or other fault-based trigger. Look for: "terminate for cause", "material breach", "default", "failure to perform", "insolvency", "bankruptcy". A general right to terminate or cancel without specifying a reason does NOT count as termination for cause.

3. "has_termination_for_convenience" = true ONLY if the clause allows termination WITHOUT cause or reason. Look for: "terminate for convenience", "terminate at any time", "terminate without cause", "terminate for any reason or no reason", "upon [X] days written notice" (when no breach is required). If the clause ONLY allows termination for cause/breach, this must be false.

4. "convenience_termination_who" — set ONLY if has_termination_for_convenience is true. Values:
   - "either_party" if both parties can terminate for convenience
   - "provider_only" if only the provider/vendor/supplier can terminate for convenience
   - "customer_only" if only the customer/client/subscriber can terminate for convenience

5. "cure_period.has_cure_period" = true ONLY if the clause provides a window to fix/cure/remedy a breach before termination takes effect. Look for: "cure", "remedy", "rectify", "[X] days to cure", "opportunity to cure". Extract the number of days into "cure_days" as an integer.

6. "notice_period.has_notice_period" = true ONLY if the clause requires advance written notice before termination. Look for: "[X] days prior written notice", "[X] days notice", "upon notice". Extract the number of days into "notice_days" as an integer.

7. "has_auto_renewal" = true ONLY if the clause states the agreement automatically renews or extends for successive terms. Look for: "automatically renew", "auto-renew", "successive terms", "renewal term", "shall renew". A clause stating the agreement has a fixed term WITHOUT auto-renewal language is false.

8. "has_survival_clause" = true ONLY if specific provisions are stated to survive termination or expiration. Look for: "shall survive", "survive termination", "survive expiration". List the named sections/provisions in "surviving_sections" (e.g. "confidentiality", "limitation of liability", "indemnification").

9. "has_post_termination_obligations" = true ONLY if there are specific obligations that must be performed AFTER termination. Look for: "upon termination", "following termination", "return all", "delete all data", "transition assistance", "final payment due", "wind-down". List the obligations in "post_termination_obligations".

10. "has_termination_fee" = true ONLY if early termination triggers a fee, penalty, or payment obligation. Look for: "early termination fee", "termination penalty", "remaining contract value", "cancellation fee". Merely owing accrued fees is NOT a termination fee.

11. source_text fields MUST be EXACT word-for-word quotes from the clause. If no quote supports the field, set source_text to null.
12. Respond with ONLY valid JSON. No markdown, no explanation, no text outside the JSON.

SCHEMA:
{{
  "has_termination_for_cause": bool or null,
  "termination_for_cause_source_text": string or null,
  "has_termination_for_convenience": bool or null,
  "convenience_termination_who": "either_party" | "provider_only" | "customer_only" | null,
  "termination_for_convenience_source_text": string or null,
  "cure_period": {{
    "has_cure_period": bool,
    "cure_days": int or null,
    "cure_source_text": string or null
  }},
  "notice_period": {{
    "has_notice_period": bool,
    "notice_days": int or null,
    "notice_source_text": string or null
  }},
  "has_auto_renewal": bool or null,
  "auto_renewal_source_text": string or null,
  "has_survival_clause": bool or null,
  "surviving_sections": [list of section names as strings],
  "survival_source_text": string or null,
  "has_post_termination_obligations": bool or null,
  "post_termination_obligations": [list of obligation descriptions as strings],
  "post_termination_source_text": string or null,
  "has_termination_fee": bool or null,
  "termination_fee_amount": string or null,
  "termination_fee_source_text": string or null,
  "extraction_confidence": float 0.0-1.0
}}

CLAUSE TEXT:
{clause_text}

JSON:"""


_PAYMENT_PROMPT = """\
You are a precise legal contract analyst. Extract ONLY information that is EXPLICITLY stated in the clause below.

CRITICAL RULES — read each one carefully:
1. Default EVERY boolean to false. Only set to true when the clause contains EXPLICIT language matching the rules below.

2. "has_payment_terms" = true ONLY if the clause specifies a deadline for payment after invoice. Look for: "net 30", "net 60", "within [X] days", "due upon receipt", "payable within". Extract the number of days into "payment_days" as an integer. "Due upon receipt" = 0 days.

3. "late_fee.has_late_fee" = true ONLY if the clause states a penalty, fee, or interest charge for overdue/late payments. Look for: "late fee", "interest on overdue", "past due amounts shall bear interest", "late payment charge". Set "late_fee_type" to one of: "flat_fee" (fixed dollar amount), "percentage" (% of invoice), "interest_rate" (% per month/year), or "other". Extract the amount into "late_fee_amount".

4. "has_price_escalation" = true ONLY if the clause allows the provider to increase prices, fees, or rates. Look for: "may increase", "adjust pricing", "price increase", "rate adjustment", "CPI adjustment", "upon renewal". A clause that merely states the current price does NOT count. Initial pricing schedules are NOT escalation.

5. "has_non_refundable" = true ONLY if payments are explicitly stated as non-refundable, non-cancellable, or final. Look for: "non-refundable", "no refunds", "fees are non-cancellable", "payments are final". A clause that simply does not mention refunds is NOT non-refundable.

6. "has_minimum_commitment" = true ONLY if there is a minimum purchase obligation, minimum spend, minimum volume, or minimum term commitment with financial consequences. Look for: "minimum commitment", "minimum purchase", "minimum spend", "minimum order", "committed volume". A fixed subscription fee alone is NOT a minimum commitment.

7. "invoice_frequency" — set ONLY if the clause specifies when invoices are issued. Values: "monthly", "quarterly", "annually", "upfront", "upon_delivery". Look for: "invoiced monthly", "billed quarterly", "annual fee", "payment in advance", "upon completion".

8. "has_dispute_process" = true ONLY if the clause provides a mechanism for disputing invoices or charges. Look for: "dispute", "contest", "good faith dispute", "written objection", "right to dispute". A general dispute resolution clause (arbitration, mediation) about the agreement itself does NOT count — it must be about payment disputes specifically.

9. "has_right_of_setoff" = true ONLY if a party can offset, deduct, or withhold amounts owed against payments due. Look for: "setoff", "offset", "deduct", "withhold", "net against". A right to suspend services for non-payment is NOT a setoff right.

10. source_text fields MUST be EXACT word-for-word quotes from the clause. If no quote supports the field, set source_text to null.
11. Respond with ONLY valid JSON. No markdown, no explanation, no text outside the JSON.

SCHEMA:
{{
  "has_payment_terms": bool or null,
  "payment_days": int or null,
  "payment_terms_source_text": string or null,
  "late_fee": {{
    "has_late_fee": bool,
    "late_fee_type": "flat_fee" | "percentage" | "interest_rate" | "other" | null,
    "late_fee_amount": string or null,
    "late_fee_source_text": string or null
  }},
  "has_price_escalation": bool or null,
  "price_escalation_source_text": string or null,
  "has_non_refundable": bool or null,
  "non_refundable_source_text": string or null,
  "has_minimum_commitment": bool or null,
  "minimum_commitment_amount": string or null,
  "minimum_commitment_source_text": string or null,
  "invoice_frequency": "monthly" | "quarterly" | "annually" | "upfront" | "upon_delivery" | null,
  "invoice_frequency_source_text": string or null,
  "has_dispute_process": bool or null,
  "dispute_process_source_text": string or null,
  "has_right_of_setoff": bool or null,
  "setoff_source_text": string or null,
  "extraction_confidence": float 0.0-1.0
}}

CLAUSE TEXT:
{clause_text}

JSON:"""


_CONFIDENTIALITY_PROMPT = """\
You are a precise legal contract analyst. Extract ONLY information that is EXPLICITLY stated in the clause below.

CRITICAL RULES — read each one carefully:
1. Default EVERY boolean to false. Only set to true when the clause contains EXPLICIT language matching the rules below.

2. "has_broad_definition" = true ONLY if the definition of "Confidential Information" is expansive or catch-all. Look for: "all information", "any and all information", "any information disclosed", "all data, documents, and materials", "including but not limited to". A clause that narrowly lists specific categories (e.g. only "trade secrets") without broad catch-all language is NOT broad.

3. "has_standard_exclusions" = true ONLY if the clause carves out standard exceptions from the confidentiality obligation. Look for at least ONE of: "publicly available", "public domain", "independently developed", "already known", "prior knowledge", "received from a third party", "compelled by law", "legally required to disclose". List each exclusion category found in "exclusions".

4. "has_duration" = true ONLY if the clause specifies how long confidentiality obligations last. Look for: "[X] years", "period of [X] years", "shall survive for", "in perpetuity", "indefinitely", "perpetual". If perpetual, set "is_perpetual" to true and "duration_years" to null. If a specific number of years, set "duration_years" to that integer and "is_perpetual" to false. If NO duration is mentioned, set has_duration to false.

5. "has_permitted_disclosures" = true ONLY if the clause permits sharing Confidential Information with specific categories of people. Look for: "employees", "advisors", "legal counsel", "accountants", "affiliates", "subcontractors", "representatives", "agents", "officers", "directors", "need to know". List each permitted recipient category in "permitted_recipients".

6. "has_return_or_destroy" = true ONLY if the clause requires return or destruction of Confidential Information upon termination, expiration, or request. Look for: "return or destroy", "return all", "destroy all copies", "certify destruction", "upon termination... return", "upon request... destroy".

7. "has_residuals_clause" = true ONLY if the clause permits use of general ideas, concepts, or know-how retained in unaided memory. Look for: "residuals", "retained in unaided memory", "general knowledge", "ideas retained in memory", "mental impressions". This is an uncommon clause — most confidentiality clauses do NOT have it.

8. "has_injunctive_relief" = true ONLY if the clause states that breach entitles the discloser to seek injunctive or equitable relief. Look for: "injunctive relief", "equitable relief", "specific performance", "irreparable harm", "irreparable injury", "restraining order". A general remedies clause without these specific terms does NOT count.

9. "is_mutual" = true ONLY if confidentiality obligations apply equally to BOTH parties. Look for: "each party", "both parties", "mutual", "the parties agree", "receiving party" / "disclosing party" used symmetrically. FALSE if obligations are one-sided: "Company shall keep Provider's information confidential" with no reciprocal obligation, or only one party is bound.

10. source_text fields MUST be EXACT word-for-word quotes from the clause. If no quote supports the field, set source_text to null.
11. Respond with ONLY valid JSON. No markdown, no explanation, no text outside the JSON.

SCHEMA:
{{
  "has_broad_definition": bool or null,
  "definition_source_text": string or null,
  "has_standard_exclusions": bool or null,
  "exclusions": [list of exclusion categories as strings],
  "exclusions_source_text": string or null,
  "has_duration": bool or null,
  "duration_years": int or null,
  "is_perpetual": bool or null,
  "duration_source_text": string or null,
  "has_permitted_disclosures": bool or null,
  "permitted_recipients": [list of recipient categories as strings],
  "permitted_disclosures_source_text": string or null,
  "has_return_or_destroy": bool or null,
  "return_destroy_source_text": string or null,
  "has_residuals_clause": bool or null,
  "residuals_source_text": string or null,
  "has_injunctive_relief": bool or null,
  "injunctive_relief_source_text": string or null,
  "is_mutual": bool or null,
  "mutuality_source_text": string or null,
  "extraction_confidence": float 0.0-1.0
}}

CLAUSE TEXT:
{clause_text}

JSON:"""


_IP_PROMPT = """\
You are a precise legal contract analyst. Extract ONLY information that is EXPLICITLY stated in the clause below.

CRITICAL RULES — read each one carefully:
1. Default EVERY boolean to false. Only set to true when the clause contains EXPLICIT language matching the rules below.

2. "has_customer_owns_deliverables" = true ONLY if the clause states that the customer/client OWNS work product, deliverables, or custom developments. Look for: "Customer shall own", "all deliverables shall be the property of Client", "work product shall belong to", "Customer owns all right, title, and interest". A license grant alone is NOT ownership. If the provider owns deliverables and merely licenses them, this is false.

3. "has_provider_owns_deliverables" = true ONLY if the clause states that the provider/vendor RETAINS ownership of deliverables, work product, the platform, or custom developments. Look for: "Provider retains all rights", "all intellectual property developed... shall remain the property of Provider", "Company owns all right, title, and interest in the Software". If the clause only discusses pre-existing IP ownership (not deliverables), this is false.

4. "has_pre_existing_ip_carveout" = true ONLY if the clause explicitly preserves each party's ownership of their pre-existing IP. Look for: "pre-existing intellectual property", "background IP", "prior inventions", "each party retains ownership of its pre-existing", "nothing in this Agreement transfers ownership of either party's pre-existing IP".

5. "has_work_for_hire" = true ONLY if the clause designates work product as "work made for hire" or "work for hire" under copyright law. This is a specific legal term. Look for: "work made for hire", "work for hire", "deemed a work made for hire". General ownership language without the "work for hire" term does NOT count.

6. "has_ip_assignment" = true ONLY if one party ASSIGNS (transfers) IP rights to the other. Look for: "hereby assigns", "shall assign", "assignment of all right, title, and interest", "irrevocably assigns". A license is NOT an assignment. Set "assignment_direction" to "provider_to_customer" or "customer_to_provider" based on who receives the assignment.

7. "has_license_grant" = true ONLY if the clause grants a license to use IP. Look for: "grants a license", "hereby licenses", "non-exclusive license", "exclusive license", "right to use", "license to access". Set "license_scope" to "exclusive" or "non_exclusive".

8. "has_feedback_clause" = true ONLY if the clause addresses ownership of feedback, suggestions, ideas, or enhancement requests provided by the customer. Look for: "feedback", "suggestions", "enhancement requests", "ideas submitted by Customer shall become the property of Provider", "feedback license".

9. "has_source_code_escrow" = true ONLY if source code is placed in escrow. Look for: "source code escrow", "escrow agent", "escrow arrangement", "source code deposit".

10. "has_non_compete" = true ONLY if the clause restricts a party from developing or selling competing products or services. Look for: "non-compete", "shall not develop competing", "covenant not to compete", "refrain from developing similar". A non-solicitation clause alone is NOT a non-compete.

11. source_text fields MUST be EXACT word-for-word quotes from the clause. If no quote supports the field, set source_text to null.
12. Respond with ONLY valid JSON. No markdown, no explanation, no text outside the JSON.

SCHEMA:
{{
  "has_customer_owns_deliverables": bool or null,
  "has_provider_owns_deliverables": bool or null,
  "ownership_source_text": string or null,
  "has_pre_existing_ip_carveout": bool or null,
  "pre_existing_ip_source_text": string or null,
  "has_work_for_hire": bool or null,
  "work_for_hire_source_text": string or null,
  "has_ip_assignment": bool or null,
  "assignment_direction": "provider_to_customer" | "customer_to_provider" | "mutual" | null,
  "ip_assignment_source_text": string or null,
  "has_license_grant": bool or null,
  "license_scope": "exclusive" | "non_exclusive" | null,
  "license_source_text": string or null,
  "has_feedback_clause": bool or null,
  "feedback_source_text": string or null,
  "has_source_code_escrow": bool or null,
  "escrow_source_text": string or null,
  "has_non_compete": bool or null,
  "non_compete_source_text": string or null,
  "extraction_confidence": float 0.0-1.0
}}

CLAUSE TEXT:
{clause_text}

JSON:"""


_GOVERNING_LAW_PROMPT = """\
You are a precise legal contract analyst. Extract ONLY information that is EXPLICITLY stated in the clause below.

CRITICAL RULES — read each one carefully:
1. Default EVERY boolean to false. Only set to true when the clause contains EXPLICIT language matching the rules below.

2. "has_governing_law" = true ONLY if the clause specifies which jurisdiction's law governs the agreement. Look for: "governed by the laws of", "construed in accordance with the laws of", "shall be governed by", "subject to the laws of". Extract the jurisdiction into "governing_law_jurisdiction" (e.g. "State of Delaware", "State of New York", "England and Wales").

3. "has_venue_selection" = true ONLY if the clause specifies WHERE disputes must or may be brought. Look for: "exclusive jurisdiction of the courts of", "venue shall be in", "submit to the jurisdiction of", "courts located in". Extract the location into "venue_location". Set "is_exclusive_venue" to true if the clause uses "exclusive jurisdiction" or "sole venue"; false if "non-exclusive" or merely "submit to jurisdiction".

4. "has_arbitration" = true ONLY if the clause requires disputes to be resolved by arbitration instead of courts. Look for: "shall be resolved by arbitration", "binding arbitration", "submitted to arbitration", "arbitrated under the rules of". Extract the arbitration body into "arbitration_body" (e.g. "AAA", "JAMS", "ICC"). A mediation clause alone is NOT arbitration.

5. "has_jury_waiver" = true ONLY if the parties waive the right to a jury trial. Look for: "waive the right to a jury trial", "jury trial waiver", "EACH PARTY HEREBY WAIVES... JURY TRIAL", "waive any right to trial by jury".

6. "has_class_action_waiver" = true ONLY if the parties waive the right to participate in class actions. Look for: "class action waiver", "waive the right to participate in a class action", "no class proceedings", "individual basis only".

7. "has_prevailing_party_fees" = true ONLY if the prevailing/winning party in a dispute can recover attorneys' fees. Look for: "prevailing party shall be entitled to... attorneys' fees", "reasonable attorneys' fees", "costs and fees to the prevailing party", "successful party shall recover".

8. source_text fields MUST be EXACT word-for-word quotes from the clause. If no quote supports the field, set source_text to null.
9. Respond with ONLY valid JSON. No markdown, no explanation, no text outside the JSON.

SCHEMA:
{{
  "has_governing_law": bool or null,
  "governing_law_jurisdiction": string or null,
  "governing_law_source_text": string or null,
  "has_venue_selection": bool or null,
  "venue_location": string or null,
  "is_exclusive_venue": bool or null,
  "venue_source_text": string or null,
  "has_arbitration": bool or null,
  "arbitration_body": string or null,
  "arbitration_source_text": string or null,
  "has_jury_waiver": bool or null,
  "jury_waiver_source_text": string or null,
  "has_class_action_waiver": bool or null,
  "class_action_waiver_source_text": string or null,
  "has_prevailing_party_fees": bool or null,
  "prevailing_party_source_text": string or null,
  "extraction_confidence": float 0.0-1.0
}}

CLAUSE TEXT:
{clause_text}

JSON:"""


_PROMPTS = {
    "liability": _LIABILITY_PROMPT,
    "termination": _TERMINATION_PROMPT,
    "payment": _PAYMENT_PROMPT,
    "confidentiality": _CONFIDENTIALITY_PROMPT,
    "ip": _IP_PROMPT,
    "governing_law": _GOVERNING_LAW_PROMPT,
}

# ── Ollama client ────────────────────────────────────────────────────────────

def _call_ollama(
    prompt: str,
    model: str = DEFAULT_MODEL,
    temperature: float = 0.1,
    max_tokens: int = 2000,
) -> str:
    """Call Ollama API and return the response text."""
    resp = requests.post(
        f"{OLLAMA_BASE_URL}/api/generate",
        json={
            "model": model,
            "prompt": prompt,
            "stream": False,
            "options": {
                "temperature": temperature,
                "num_predict": max_tokens,
            },
        },
        timeout=120,
    )
    resp.raise_for_status()
    return resp.json()["response"]


def _call_anthropic(
    prompt: str,
    model: str = "claude-haiku-4-5-20251001",
    max_tokens: int = 2000,
) -> str:
    """Call Anthropic API and return the response text. Requires ANTHROPIC_API_KEY."""
    try:
        import anthropic
    except ImportError:
        raise RuntimeError(
            "anthropic package not installed. Run: pip install anthropic"
        )
    api_key = os.environ.get("ANTHROPIC_API_KEY")
    if not api_key:
        raise RuntimeError("ANTHROPIC_API_KEY environment variable not set")

    client = anthropic.Anthropic(api_key=api_key)
    message = client.messages.create(
        model=model,
        max_tokens=max_tokens,
        messages=[{"role": "user", "content": prompt}],
    )
    return message.content[0].text


def _call_groq(
    prompt: str,
    model: str = "llama-3.1-8b-instant",
    max_tokens: int = 2000,
) -> str:
    """Call Groq API and return the response text. Requires GROQ_API_KEY.

    Free tier: 14,400 req/day. Sign up at https://console.groq.com (no credit card).
    """
    try:
        from groq import Groq
    except ImportError:
        raise RuntimeError(
            "groq package not installed. Run: pip install groq"
        )
    api_key = os.environ.get("GROQ_API_KEY")
    if not api_key:
        raise RuntimeError("GROQ_API_KEY environment variable not set")

    client = Groq(api_key=api_key)
    response = client.chat.completions.create(
        model=model,
        messages=[{"role": "user", "content": prompt}],
        max_tokens=max_tokens,
        temperature=0,
    )
    return response.choices[0].message.content


def _call_llm(
    prompt: str,
    model: str = DEFAULT_MODEL,
    max_tokens: int = 2000,
) -> str:
    """Route to the appropriate LLM backend based on model name and available keys.

    Priority:
      1. claude-*  → Anthropic API (requires ANTHROPIC_API_KEY)
      2. GROQ_API_KEY set → Groq API (free, no credit card)
      3. fallback  → Ollama local (requires Ollama running)
    """
    if model.startswith("claude-"):
        return _call_anthropic(prompt, model=model, max_tokens=max_tokens)
    if os.environ.get("GROQ_API_KEY"):
        groq_model = "llama-3.1-8b-instant" if model == DEFAULT_MODEL else model
        return _call_groq(prompt, model=groq_model, max_tokens=max_tokens)
    return _call_ollama(prompt, model=model, max_tokens=max_tokens)


def _extract_json(text: str) -> dict:
    """Extract JSON from LLM response, handling common formatting issues."""
    text = text.strip()

    # Try direct parse
    try:
        return json.loads(text)
    except json.JSONDecodeError:
        pass

    # Try extracting from markdown code block
    match = re.search(r"```(?:json)?\s*(\{.*?\})\s*```", text, re.DOTALL)
    if match:
        try:
            return json.loads(match.group(1))
        except json.JSONDecodeError:
            pass

    # Try finding the first { ... } block
    brace_start = text.find("{")
    if brace_start >= 0:
        depth = 0
        for i, ch in enumerate(text[brace_start:], brace_start):
            if ch == "{":
                depth += 1
            elif ch == "}":
                depth -= 1
                if depth == 0:
                    try:
                        return json.loads(text[brace_start : i + 1])
                    except json.JSONDecodeError:
                        break

    raise ValueError(f"Could not extract valid JSON from response: {text[:200]}...")


# ── Extraction ───────────────────────────────────────────────────────────────

def extract_clause(
    clause_text: str,
    clause_type: str = "liability",
    model: str = DEFAULT_MODEL,
    max_retries: int = 3,
) -> Optional[BaseModel]:
    """
    Extract structured fields from a clause using the LLM.

    Args:
        clause_text: Raw clause text to extract from.
        clause_type: Category of clause (determines schema + prompt).
        model: Ollama model name (llama3.1:8b) or Anthropic model (claude-*).
               Defaults to LRM_EXTRACTION_MODEL env var, or llama3.1:8b.
        max_retries: Number of retry attempts on failure.

    Returns:
        Pydantic model instance with extracted fields, or None on failure.
    """
    if clause_type not in _PROMPTS:
        raise ValueError(f"No extraction prompt for clause type: {clause_type}")

    schema_cls = EXTRACTION_SCHEMAS[clause_type]
    prompt_template = _PROMPTS[clause_type]
    prompt = prompt_template.format(clause_text=clause_text)

    for attempt in range(max_retries):
        try:
            start = time.monotonic()
            raw_response = _call_llm(prompt, model=model)
            elapsed = time.monotonic() - start

            data = _extract_json(raw_response)
            result = schema_cls.model_validate(data)

            log.debug(
                "Extraction succeeded (attempt %d, %.1fs): %s",
                attempt + 1, elapsed, clause_type,
            )
            return result

        except (requests.RequestException, ValueError, ValidationError) as e:
            log.warning(
                "Extraction attempt %d/%d failed for %s: %s",
                attempt + 1, max_retries, clause_type, e,
            )
            if attempt < max_retries - 1:
                time.sleep(1)

    log.error("Extraction failed after %d attempts for %s", max_retries, clause_type)
    return None


def extract_liability(clause_text: str, model: str = DEFAULT_MODEL) -> Optional[LiabilityExtraction]:
    """Convenience wrapper for liability extraction."""
    return extract_clause(clause_text, clause_type="liability", model=model)


def extract_termination(clause_text: str, model: str = DEFAULT_MODEL) -> Optional[TerminationExtraction]:
    """Convenience wrapper for termination extraction."""
    return extract_clause(clause_text, clause_type="termination", model=model)


def extract_payment(clause_text: str, model: str = DEFAULT_MODEL) -> Optional[PaymentExtraction]:
    """Convenience wrapper for payment extraction."""
    return extract_clause(clause_text, clause_type="payment", model=model)


def extract_confidentiality(clause_text: str, model: str = DEFAULT_MODEL) -> Optional[ConfidentialityExtraction]:
    """Convenience wrapper for confidentiality extraction."""
    return extract_clause(clause_text, clause_type="confidentiality", model=model)


def extract_ip(clause_text: str, model: str = DEFAULT_MODEL) -> Optional[IPExtraction]:
    """Convenience wrapper for IP extraction."""
    return extract_clause(clause_text, clause_type="ip", model=model)


def extract_governing_law(clause_text: str, model: str = DEFAULT_MODEL) -> Optional[GoverningLawExtraction]:
    """Convenience wrapper for governing law extraction."""
    return extract_clause(clause_text, clause_type="governing_law", model=model)


# ── Batch extraction ─────────────────────────────────────────────────────────

def batch_extract(
    clauses: list[dict],
    clause_type: str = "liability",
    model: str = DEFAULT_MODEL,
) -> list[dict]:
    """
    Extract structured data from a list of clause dicts.
    Each dict must have 'text' and optionally 'contract_id', 'chunk_id'.

    Returns list of dicts with extraction results.
    """
    results = []
    total = len(clauses)

    for i, clause in enumerate(clauses):
        text = clause["text"]
        extraction = extract_clause(text, clause_type=clause_type, model=model)

        result = {
            "contract_id": clause.get("contract_id", ""),
            "chunk_id": clause.get("id", clause.get("chunk_id")),
            "clause_type": clause_type,
            "success": extraction is not None,
            "extracted_data": extraction.model_dump() if extraction else None,
        }
        results.append(result)

        if (i + 1) % 10 == 0 or i == total - 1:
            success_count = sum(1 for r in results if r["success"])
            log.info(
                "Batch extraction: %d/%d done (%d succeeded)",
                i + 1, total, success_count,
            )

    return results
