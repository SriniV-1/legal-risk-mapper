"""
LLM-Based Clause Extractor
───────────────────────────
Uses Ollama (Llama 3.1 8B) to extract structured fields from contract clauses.

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

from backend.extraction.schemas import EXTRACTION_SCHEMAS, LiabilityExtraction, TerminationExtraction, PaymentExtraction

log = logging.getLogger(__name__)

OLLAMA_BASE_URL = "http://localhost:11434"
DEFAULT_MODEL = "llama3.1:8b"

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


_PROMPTS = {
    "liability": _LIABILITY_PROMPT,
    "termination": _TERMINATION_PROMPT,
    "payment": _PAYMENT_PROMPT,
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
        model: Ollama model to use.
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
            raw_response = _call_ollama(prompt, model=model)
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
