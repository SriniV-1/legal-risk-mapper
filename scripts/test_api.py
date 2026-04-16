"""
Test script for Legal Risk Mapper API.
Runs several test cases and pretty-prints results.

Usage:
    python scripts/test_api.py
    python scripts/test_api.py --url http://localhost:8000
"""
import argparse
import json
import sys
from pathlib import Path

try:
    import requests
except ImportError:
    print("ERROR: 'requests' not installed. Run: pip install requests")
    sys.exit(1)


# ── ANSI colors ───────────────────────────────────────────────────────────────
RED    = "\033[91m"
YELLOW = "\033[93m"
GREEN  = "\033[92m"
BLUE   = "\033[94m"
BOLD   = "\033[1m"
RESET  = "\033[0m"

SEVERITY_COLOR = {"High": RED, "Medium": YELLOW, "Low": GREEN}


def color_severity(s: str) -> str:
    return SEVERITY_COLOR.get(s, "") + s + RESET


def print_separator(title=""):
    width = 70
    if title:
        pad = (width - len(title) - 2) // 2
        print(f"\n{'─' * pad} {BOLD}{title}{RESET} {'─' * pad}")
    else:
        print("─" * width)


# ── Test cases ─────────────────────────────────────────────────────────────────

TEST_CASES = [
    {
        "name": "SaaS Contract (high risk)",
        "payload": {
            "document_title": "SaaS Service Agreement",
            "text": """
            This agreement is provided AS-IS without warranty. Client shall indemnify and
            hold harmless Company for all third-party claims. Company may unilaterally
            change pricing at any time. The agreement automatically renews unless cancelled.
            Client must comply with all applicable laws including GDPR and export controls.
            Personal data may be shared with third parties. Unpaid balances accrue interest
            at 18% per annum. Early termination fee of 75% applies. Company's liability
            is limited at its sole discretion.
            """
        }
    },
    {
        "name": "Clean Simple Agreement (low risk)",
        "payload": {
            "document_title": "Simple NDA",
            "text": """
            This Non-Disclosure Agreement is between Party A and Party B. Both parties
            agree to keep shared information confidential for a period of two years.
            Any breach of this agreement should be reported in writing within 30 days.
            Disputes will be resolved through mediation in New York, USA.
            """
        }
    },
    {
        "name": "Privacy Policy (mixed risk)",
        "payload": {
            "document_title": "App Privacy Policy",
            "text": """
            We collect personal data including your location and browsing history using cookies.
            GDPR requires us to obtain consent for data processing. We implement industry-standard
            encryption. Data is retained per our data retention policy and applicable law.
            You may opt-out of marketing communications at any time.
            """
        }
    },
    {
        "name": "Sample file upload (contract.txt)",
        "file": str(Path(__file__).parent.parent / "data" / "sample_inputs" / "sample_contract.txt"),
    }
]


def run_tests(base_url: str):
    print(f"\n{BOLD}Legal Risk Mapper — API Test Suite{RESET}")
    print(f"Target: {BLUE}{base_url}{RESET}\n")

    # Health check
    print_separator("Health Check")
    try:
        r = requests.get(f"{base_url}/health", timeout=5)
        h = r.json()
        print(f"  Status : {GREEN}{h['status']}{RESET}")
        print(f"  Version: {h['version']}")
        print(f"  Engine : {h['nlp_engine']}")
    except Exception as e:
        print(f"{RED}FAILED: {e}{RESET}")
        print("Is the server running?  →  python -m uvicorn backend.main:app --reload")
        sys.exit(1)

    for tc in TEST_CASES:
        print_separator(tc["name"])
        try:
            if "file" in tc:
                fp = Path(tc["file"])
                if not fp.exists():
                    print(f"  {YELLOW}Skipping — file not found: {fp}{RESET}")
                    continue
                with open(fp, "rb") as f:
                    r = requests.post(
                        f"{base_url}/analyze/upload",
                        files={"file": (fp.name, f, "text/plain")},
                        timeout=15,
                    )
            else:
                r = requests.post(
                    f"{base_url}/analyze",
                    json=tc["payload"],
                    timeout=15,
                )

            if r.status_code != 200:
                print(f"  {RED}HTTP {r.status_code}: {r.text[:200]}{RESET}")
                continue

            data = r.json()
            lvl = data["overall_risk_level"]
            print(f"  Overall Risk  : {color_severity(lvl)}")
            print(f"  Total Risks   : {data['total_risks']}")
            print(f"  Severity      : {data['severity_breakdown']}")
            print(f"  By Category   : {data['risk_summary']}")
            print()

            for risk in data["risks"][:5]:  # Show top 5
                sev_str = f"[{color_severity(risk['severity'])}]"
                print(f"  {sev_str:<30} {BOLD}{risk['risk_type']}{RESET}")
                snippet = risk["text_snippet"][:80].replace("\n", " ")
                print(f"    Snippet: \"{snippet}…\"")
                print(f"    Confidence: {int(risk['score'] * 100)}%")
                print()

            if data["total_risks"] > 5:
                print(f"  … and {data['total_risks'] - 5} more risks (see full JSON)")

        except requests.Timeout:
            print(f"  {RED}Request timed out{RESET}")
        except Exception as e:
            print(f"  {RED}Error: {e}{RESET}")

    print_separator()
    print(f"\n{GREEN}All tests completed.{RESET}")
    print("For full JSON output, use the /docs endpoint or add --verbose flag.\n")


def main():
    parser = argparse.ArgumentParser(description="Test the Legal Risk Mapper API")
    parser.add_argument("--url", default="http://localhost:8000", help="API base URL")
    args = parser.parse_args()
    run_tests(args.url)


if __name__ == "__main__":
    main()
