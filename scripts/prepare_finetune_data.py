#!/usr/bin/env python3
"""
Prepare Fine-Tuning Data for ALRM Clause Extractor
────────────────────────────────────────────────────
Generates instruction-tuning JSONL data from:
  1. Existing eval datasets in data/eval/ (liability, termination, governing_law)
  2. Hardcoded example clauses for remaining types (payment, confidentiality, ip)

Output format (one JSON object per line):
  {"instruction": "<system+user prompt>", "input": "<clause_text>", "output": "<json extraction>"}

Usage:
  python scripts/prepare_finetune_data.py [--output-dir data/finetune] [--val-split 0.1]

The script can run without any API keys, GPU, or external services.
"""
from __future__ import annotations

import argparse
import json
import os
import random
import sys

# Allow running as a standalone script from the repo root
_REPO_ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
sys.path.insert(0, _REPO_ROOT)

from backend.extraction.prompt_registry import get_prompt, list_clause_types
from backend.extraction.schemas import EXTRACTION_SCHEMAS


# ── Hardcoded examples for clause types without eval data ──────────────────

HARDCODED_EXAMPLES: dict[str, list[dict]] = {
    "payment": [
        {
            "text": (
                "All invoices shall be due and payable within thirty (30) days of "
                "the invoice date. Any amount not paid when due shall bear interest "
                "at the rate of 1.5% per month or the maximum rate permitted by law, "
                "whichever is less. Provider reserves the right to increase fees by "
                "up to 5% annually upon thirty (30) days prior written notice."
            ),
            "ground_truth": {
                "has_payment_terms": True,
                "payment_days": 30,
                "payment_terms_source_text": "All invoices shall be due and payable within thirty (30) days of the invoice date",
                "late_fee": {
                    "has_late_fee": True,
                    "late_fee_type": "interest_rate",
                    "late_fee_amount": "1.5% per month or the maximum rate permitted by law, whichever is less",
                    "late_fee_source_text": "Any amount not paid when due shall bear interest at the rate of 1.5% per month or the maximum rate permitted by law, whichever is less",
                },
                "has_price_escalation": True,
                "price_escalation_source_text": "Provider reserves the right to increase fees by up to 5% annually upon thirty (30) days prior written notice",
                "has_non_refundable": False,
                "has_minimum_commitment": False,
                "invoice_frequency": None,
                "has_dispute_process": False,
                "has_right_of_setoff": False,
                "extraction_confidence": 0.95,
            },
        },
        {
            "text": (
                "Customer shall pay all fees set forth in the applicable Order Form. "
                "All fees are non-refundable. Invoices shall be issued quarterly in "
                "advance and are due within forty-five (45) days of receipt. Customer "
                "commits to a minimum annual spend of $100,000. If Customer disputes "
                "any portion of an invoice in good faith, Customer shall provide "
                "written notice within fifteen (15) days of receipt and shall pay "
                "the undisputed portion."
            ),
            "ground_truth": {
                "has_payment_terms": True,
                "payment_days": 45,
                "payment_terms_source_text": "Invoices shall be issued quarterly in advance and are due within forty-five (45) days of receipt",
                "late_fee": {"has_late_fee": False},
                "has_price_escalation": False,
                "has_non_refundable": True,
                "non_refundable_source_text": "All fees are non-refundable",
                "has_minimum_commitment": True,
                "minimum_commitment_amount": "$100,000 annually",
                "minimum_commitment_source_text": "Customer commits to a minimum annual spend of $100,000",
                "invoice_frequency": "quarterly",
                "invoice_frequency_source_text": "Invoices shall be issued quarterly in advance",
                "has_dispute_process": True,
                "dispute_process_source_text": "If Customer disputes any portion of an invoice in good faith, Customer shall provide written notice within fifteen (15) days of receipt and shall pay the undisputed portion",
                "has_right_of_setoff": False,
                "extraction_confidence": 0.92,
            },
        },
        {
            "text": (
                "Payment is due upon delivery. All amounts paid under this Agreement "
                "are final and non-refundable under any circumstances. Either party "
                "may offset amounts owed against any amounts due from the other party "
                "under this or any other agreement between the parties."
            ),
            "ground_truth": {
                "has_payment_terms": True,
                "payment_days": None,
                "payment_terms_source_text": "Payment is due upon delivery",
                "late_fee": {"has_late_fee": False},
                "has_price_escalation": False,
                "has_non_refundable": True,
                "non_refundable_source_text": "All amounts paid under this Agreement are final and non-refundable under any circumstances",
                "has_minimum_commitment": False,
                "invoice_frequency": None,
                "has_dispute_process": False,
                "has_right_of_setoff": True,
                "setoff_source_text": "Either party may offset amounts owed against any amounts due from the other party under this or any other agreement between the parties",
                "extraction_confidence": 0.90,
            },
        },
    ],
    "confidentiality": [
        {
            "text": (
                'As used herein, "Confidential Information" means any and all '
                "information disclosed by one party to the other, whether orally, "
                "in writing, or electronically, that is designated as confidential "
                "or that reasonably should be understood to be confidential. "
                "Confidential Information shall not include information that: "
                "(a) is or becomes publicly available through no fault of the "
                "receiving party; (b) was rightfully in the receiving party's "
                "possession prior to disclosure; (c) is independently developed "
                "by the receiving party; or (d) is required to be disclosed by law. "
                "The receiving party may disclose Confidential Information to its "
                "employees, advisors, and legal counsel who have a need to know. "
                "Confidentiality obligations shall survive for three (3) years "
                "after termination. Upon termination, each party shall return or "
                "destroy all Confidential Information of the other party."
            ),
            "ground_truth": {
                "has_broad_definition": True,
                "definition_source_text": "any and all information disclosed by one party to the other, whether orally, in writing, or electronically, that is designated as confidential or that reasonably should be understood to be confidential",
                "has_standard_exclusions": True,
                "exclusions": ["public domain", "prior knowledge", "independent development", "compelled disclosure"],
                "exclusions_source_text": "(a) is or becomes publicly available through no fault of the receiving party; (b) was rightfully in the receiving party's possession prior to disclosure; (c) is independently developed by the receiving party; or (d) is required to be disclosed by law",
                "has_duration": True,
                "duration_years": 3,
                "is_perpetual": False,
                "duration_source_text": "Confidentiality obligations shall survive for three (3) years after termination",
                "has_permitted_disclosures": True,
                "permitted_recipients": ["employees", "advisors", "legal counsel"],
                "permitted_disclosures_source_text": "The receiving party may disclose Confidential Information to its employees, advisors, and legal counsel who have a need to know",
                "has_return_or_destroy": True,
                "return_destroy_source_text": "Upon termination, each party shall return or destroy all Confidential Information of the other party",
                "has_residuals_clause": False,
                "has_injunctive_relief": False,
                "is_mutual": True,
                "mutuality_source_text": "one party to the other",
                "extraction_confidence": 0.95,
            },
        },
        {
            "text": (
                "Provider agrees to keep all Client Data strictly confidential in "
                "perpetuity. Provider shall not disclose Client Data to any third "
                "party without Client's prior written consent. In the event of any "
                "breach of this Section, Client shall be entitled to seek injunctive "
                "or other equitable relief without the necessity of proving actual "
                "damages. Provider acknowledges that any personnel who receive "
                "Confidential Information may retain residual knowledge of such "
                "information in unaided memory, and such retention shall not "
                "constitute a breach of this Agreement."
            ),
            "ground_truth": {
                "has_broad_definition": False,
                "has_standard_exclusions": False,
                "exclusions": [],
                "has_duration": True,
                "duration_years": None,
                "is_perpetual": True,
                "duration_source_text": "Provider agrees to keep all Client Data strictly confidential in perpetuity",
                "has_permitted_disclosures": False,
                "permitted_recipients": [],
                "has_return_or_destroy": False,
                "has_residuals_clause": True,
                "residuals_source_text": "any personnel who receive Confidential Information may retain residual knowledge of such information in unaided memory, and such retention shall not constitute a breach of this Agreement",
                "has_injunctive_relief": True,
                "injunctive_relief_source_text": "Client shall be entitled to seek injunctive or other equitable relief without the necessity of proving actual damages",
                "is_mutual": False,
                "extraction_confidence": 0.93,
            },
        },
    ],
    "ip": [
        {
            "text": (
                "All deliverables created by Provider under this Agreement shall be "
                "deemed works made for hire. To the extent any deliverable does not "
                "qualify as a work made for hire, Provider hereby irrevocably assigns "
                "to Customer all right, title, and interest in such deliverable. "
                "Notwithstanding the foregoing, Provider retains all rights in its "
                "pre-existing intellectual property. Provider grants Customer a "
                "non-exclusive, perpetual license to use any Provider pre-existing "
                "IP incorporated into the deliverables."
            ),
            "ground_truth": {
                "has_customer_owns_deliverables": True,
                "has_provider_owns_deliverables": False,
                "ownership_source_text": "All deliverables created by Provider under this Agreement shall be deemed works made for hire",
                "has_pre_existing_ip_carveout": True,
                "pre_existing_ip_source_text": "Provider retains all rights in its pre-existing intellectual property",
                "has_work_for_hire": True,
                "work_for_hire_source_text": "All deliverables created by Provider under this Agreement shall be deemed works made for hire",
                "has_ip_assignment": True,
                "assignment_direction": "provider_to_customer",
                "ip_assignment_source_text": "Provider hereby irrevocably assigns to Customer all right, title, and interest in such deliverable",
                "has_license_grant": True,
                "license_scope": "non_exclusive",
                "license_source_text": "Provider grants Customer a non-exclusive, perpetual license to use any Provider pre-existing IP incorporated into the deliverables",
                "has_feedback_clause": False,
                "has_source_code_escrow": False,
                "has_non_compete": False,
                "extraction_confidence": 0.95,
            },
        },
        {
            "text": (
                "Provider shall retain all intellectual property rights in the "
                "Software and any modifications or enhancements thereto. Customer "
                "is granted a non-exclusive, non-transferable license to use the "
                "Software during the term of this Agreement. Customer agrees that "
                "any feedback, suggestions, or enhancement requests provided to "
                "Provider shall become the sole property of Provider. During the "
                "term and for twelve (12) months thereafter, Customer shall not "
                "develop, market, or sell any product or service that directly "
                "competes with the Software."
            ),
            "ground_truth": {
                "has_customer_owns_deliverables": False,
                "has_provider_owns_deliverables": True,
                "ownership_source_text": "Provider shall retain all intellectual property rights in the Software and any modifications or enhancements thereto",
                "has_pre_existing_ip_carveout": False,
                "has_work_for_hire": False,
                "has_ip_assignment": False,
                "has_license_grant": True,
                "license_scope": "non_exclusive",
                "license_source_text": "Customer is granted a non-exclusive, non-transferable license to use the Software during the term of this Agreement",
                "has_feedback_clause": True,
                "feedback_source_text": "any feedback, suggestions, or enhancement requests provided to Provider shall become the sole property of Provider",
                "has_source_code_escrow": False,
                "has_non_compete": True,
                "non_compete_source_text": "During the term and for twelve (12) months thereafter, Customer shall not develop, market, or sell any product or service that directly competes with the Software",
                "extraction_confidence": 0.93,
            },
        },
        {
            "text": (
                "Each party retains ownership of its pre-existing intellectual "
                "property. Any jointly developed IP shall be jointly owned. Provider "
                "shall deposit the source code of the Software with a reputable "
                "escrow agent. In the event Provider ceases operations or materially "
                "breaches this Agreement, the escrow agent shall release the source "
                "code to Customer."
            ),
            "ground_truth": {
                "has_customer_owns_deliverables": False,
                "has_provider_owns_deliverables": False,
                "ownership_source_text": "Any jointly developed IP shall be jointly owned",
                "has_pre_existing_ip_carveout": True,
                "pre_existing_ip_source_text": "Each party retains ownership of its pre-existing intellectual property",
                "has_work_for_hire": False,
                "has_ip_assignment": False,
                "has_license_grant": False,
                "has_feedback_clause": False,
                "has_source_code_escrow": True,
                "escrow_source_text": "Provider shall deposit the source code of the Software with a reputable escrow agent",
                "has_non_compete": False,
                "extraction_confidence": 0.90,
            },
        },
    ],
}


def _load_eval_data(clause_type: str) -> list[dict]:
    """Load eval data from data/eval/<type>_eval.json if it exists."""
    eval_path = os.path.join(_REPO_ROOT, "data", "eval", f"{clause_type}_eval.json")
    if not os.path.isfile(eval_path):
        return []
    with open(eval_path, "r") as f:
        data = json.load(f)
    return data


def _build_training_pair(clause_type: str, clause_text: str, ground_truth: dict) -> dict:
    """Build a single instruction-tuning pair.

    Uses the real prompt templates from the prompt registry so training data
    matches the format the model sees at inference time.
    """
    prompt_config = get_prompt(clause_type)
    instruction = prompt_config.format(clause_text=clause_text)
    output_json = json.dumps(ground_truth, indent=2)

    return {
        "instruction": instruction,
        "input": clause_text,
        "output": output_json,
        "clause_type": clause_type,
    }


def prepare_dataset(seed: int = 42) -> list[dict]:
    """Build the full training dataset from eval files + hardcoded examples."""
    all_pairs: list[dict] = []

    for clause_type in list_clause_types():
        # Try loading from eval data first
        eval_data = _load_eval_data(clause_type)
        if eval_data:
            for item in eval_data:
                if "text" in item and "ground_truth" in item:
                    pair = _build_training_pair(
                        clause_type, item["text"], item["ground_truth"]
                    )
                    all_pairs.append(pair)
            print(f"  {clause_type}: loaded {len(eval_data)} examples from eval data")
        else:
            # Fall back to hardcoded examples
            hardcoded = HARDCODED_EXAMPLES.get(clause_type, [])
            for item in hardcoded:
                pair = _build_training_pair(
                    clause_type, item["text"], item["ground_truth"]
                )
                all_pairs.append(pair)
            print(f"  {clause_type}: loaded {len(hardcoded)} hardcoded examples")

    random.seed(seed)
    random.shuffle(all_pairs)
    return all_pairs


def write_jsonl(records: list[dict], path: str) -> None:
    """Write records as JSONL to the given path."""
    os.makedirs(os.path.dirname(path), exist_ok=True)
    with open(path, "w") as f:
        for record in records:
            f.write(json.dumps(record) + "\n")
    print(f"  Wrote {len(records)} records to {path}")


def main() -> None:
    parser = argparse.ArgumentParser(
        description="Prepare instruction-tuning data for ALRM clause extractor"
    )
    parser.add_argument(
        "--output-dir",
        default=os.path.join(_REPO_ROOT, "data", "finetune"),
        help="Directory for output JSONL files (default: data/finetune/)",
    )
    parser.add_argument(
        "--val-split",
        type=float,
        default=0.1,
        help="Fraction of data for validation (default: 0.1)",
    )
    parser.add_argument(
        "--seed",
        type=int,
        default=42,
        help="Random seed for reproducibility (default: 42)",
    )
    args = parser.parse_args()

    print("Preparing fine-tuning dataset...")
    all_pairs = prepare_dataset(seed=args.seed)

    if not all_pairs:
        print("ERROR: No training data generated. Check data/eval/ and hardcoded examples.")
        sys.exit(1)

    # Split into train/validation
    split_idx = max(1, int(len(all_pairs) * (1 - args.val_split)))
    train_data = all_pairs[:split_idx]
    val_data = all_pairs[split_idx:]

    print(f"\nDataset split: {len(train_data)} train, {len(val_data)} validation")

    # Write JSONL files
    train_path = os.path.join(args.output_dir, "train.jsonl")
    val_path = os.path.join(args.output_dir, "val.jsonl")
    write_jsonl(train_data, train_path)
    write_jsonl(val_data, val_path)

    # Print summary
    print("\nPer-category counts:")
    from collections import Counter
    type_counts = Counter(r["clause_type"] for r in all_pairs)
    for ct in sorted(type_counts):
        print(f"  {ct}: {type_counts[ct]}")

    print(f"\nDone. Files written to {args.output_dir}/")


if __name__ == "__main__":
    main()
