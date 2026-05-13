"""
Before/After comparison: regex-only vs hybrid (regex + semantic).

This script demonstrates the core value of the semantic layer: it catches
risky clauses that are PARAPHRASED in ways the regex patterns can't see.

Run:
    python scripts/test_semantic.py
"""
import sys
from pathlib import Path

# Let the script run from the project root without installing the package
sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from backend.services.risk_analyzer import analyze_risks
from backend.services import semantic_analyzer
from backend.models import embeddings


# ── ANSI colors ──
RED, YELLOW, GREEN, BLUE, BOLD, DIM, RESET = (
    "\033[91m", "\033[93m", "\033[92m", "\033[94m",
    "\033[1m", "\033[2m", "\033[0m",
)
SEV_COLOR = {"High": RED, "Medium": YELLOW, "Low": GREEN}


# ─────────────────────────────────────────────────────────────────────────────
#  TEST INPUTS
# ─────────────────────────────────────────────────────────────────────────────

# CRUCIAL: this text deliberately AVOIDS the regex keywords.
#  • no "indemnify", no "hold harmless"  → uses "make whole" instead
#  • no "sole discretion"                 → uses "as it sees fit"
#  • no "automatically renew"             → uses "successive terms"
#  • no "share with third parties"        → uses "transmit to partners"
#  • no "personal data"                   → uses "user-specific information"
# Pure regex will miss almost all of this. Semantic layer should catch it.
SNEAKY_TEXT = """
Agreement for Platform Access

The receiving party agrees to make the disclosing party whole for any costs,
expenses, or financial losses incurred as a result of any breach of this
agreement, without limit as to amount or duration.

User-specific information gathered during your engagement with our platform
may be transmitted to and retained on servers located in jurisdictions outside
your country of residence where data protection standards may differ.

The company may take such actions as it sees fit to protect its interests,
and its determinations on matters of interpretation shall be final.

This agreement shall continue for successive annual terms unless either party
provides written notice of non-renewal at least ninety days before the end
of the then-current term.

Platform services are delivered on a commercially reasonable basis and the
provider makes no guarantees regarding continuous availability, fitness for
any particular purpose, or accuracy of results.

We may gather facial geometry and voice patterns during authentication for
improved security and personalization of the user experience.
"""

# Control: same risks but expressed in regex-friendly language
OBVIOUS_TEXT = """
The client shall indemnify and hold harmless the company from all claims.
We share personal data with third parties for marketing purposes.
Terms may change at our sole discretion at any time.
This agreement automatically renews for annual terms.
Services are provided AS-IS without warranty.
We collect biometric data for authentication.
"""


# ─────────────────────────────────────────────────────────────────────────────
#  PRINT HELPERS
# ─────────────────────────────────────────────────────────────────────────────

def section(title):
    print(f"\n{BOLD}{'═' * 74}{RESET}")
    print(f"{BOLD}  {title}{RESET}")
    print(f"{BOLD}{'═' * 74}{RESET}")


def print_risk(r, idx):
    sev = r["severity"]
    color = SEV_COLOR.get(sev, "")
    sources = "+".join(r.get("sources", ["?"]))
    sim = r.get("semantic_similarity")
    sim_str = f" sim={sim:.2f}" if sim is not None else ""
    ci = r.get("clause_index", "?")

    print(f"\n  {BOLD}[{idx}]{RESET} {color}{sev:6}{RESET} {BOLD}{r['risk_type']}{RESET}")
    print(f"      {DIM}clause #{ci} · score={r['score']:.2f} · via={sources}{sim_str}{RESET}")
    snip = r["text_snippet"].replace("\n", " ").strip()
    if len(snip) > 140:
        snip = snip[:137] + "..."
    print(f"      {DIM}“{snip}”{RESET}")
    expl = r["explanation"]
    if len(expl) > 200:
        expl = expl[:197] + "..."
    print(f"      {expl}")


def summarize(risks, label):
    print(f"\n  {BOLD}{label}:{RESET} {len(risks)} risk(s)")
    if not risks:
        return
    by_cat = {}
    by_sev = {"High": 0, "Medium": 0, "Low": 0}
    by_source = {"regex_only": 0, "semantic_only": 0, "hybrid": 0}
    for r in risks:
        by_cat[r["risk_type"]] = by_cat.get(r["risk_type"], 0) + 1
        by_sev[r["severity"]] += 1
        srcs = set(r.get("sources", []))
        if srcs == {"regex"}:
            by_source["regex_only"] += 1
        elif srcs == {"semantic"}:
            by_source["semantic_only"] += 1
        elif srcs == {"regex", "semantic"}:
            by_source["hybrid"] += 1
    print(f"    Severity : {RED}{by_sev['High']} High{RESET}, "
          f"{YELLOW}{by_sev['Medium']} Medium{RESET}, "
          f"{GREEN}{by_sev['Low']} Low{RESET}")
    print(f"    Sources  : {by_source['regex_only']} regex-only · "
          f"{by_source['semantic_only']} semantic-only · "
          f"{BOLD}{by_source['hybrid']} hybrid{RESET}")
    print(f"    Categories: {by_cat}")


# ─────────────────────────────────────────────────────────────────────────────
#  REGEX-ONLY SIMULATION (disables semantic layer temporarily)
# ─────────────────────────────────────────────────────────────────────────────

def analyze_regex_only(text):
    """Monkey-patch the semantic analyzer to return [] for this call."""
    original = semantic_analyzer.semantic_analyze
    semantic_analyzer.semantic_analyze = lambda clauses: []
    try:
        return analyze_risks(text)
    finally:
        semantic_analyzer.semantic_analyze = original


# ─────────────────────────────────────────────────────────────────────────────
#  MAIN
# ─────────────────────────────────────────────────────────────────────────────

def main():
    section("ALRM — Semantic vs Regex-Only Comparison")

    # Report engine status
    print(f"  Semantic model available : {embeddings.is_available()}")
    try:
        import spacy
        print(f"  spaCy available          : True ({spacy.__version__})")
    except ImportError:
        print("  spaCy available          : False")

    # ── TEST 1: Sneaky text (paraphrased risks) ─────────────────────────────
    section("TEST 1: SNEAKY text (paraphrased — regex-unfriendly)")
    print(f"{DIM}{SNEAKY_TEXT.strip()}{RESET}")

    regex_only = analyze_regex_only(SNEAKY_TEXT)
    print(f"\n{BOLD}▸ REGEX-ONLY:{RESET}")
    summarize(regex_only, "Detected")
    for i, r in enumerate(regex_only[:5], 1):
        print_risk(r, i)

    hybrid = analyze_risks(SNEAKY_TEXT)
    print(f"\n{BOLD}▸ HYBRID (regex + semantic):{RESET}")
    summarize(hybrid, "Detected")
    for i, r in enumerate(hybrid[:10], 1):
        print_risk(r, i)

    delta = len(hybrid) - len(regex_only)
    print(f"\n  {BOLD}{GREEN}→ Semantic layer found {delta} additional risk(s) "
          f"that regex missed.{RESET}")

    # ── TEST 2: Obvious text (both layers should agree) ─────────────────────
    section("TEST 2: OBVIOUS text (regex-friendly control)")

    regex_only2 = analyze_regex_only(OBVIOUS_TEXT)
    hybrid2 = analyze_risks(OBVIOUS_TEXT)

    print(f"\n{BOLD}▸ REGEX-ONLY:{RESET}")
    summarize(regex_only2, "Detected")
    print(f"\n{BOLD}▸ HYBRID:{RESET}")
    summarize(hybrid2, "Detected")

    hybrid_count = sum(1 for r in hybrid2 if set(r.get("sources", [])) == {"regex", "semantic"})
    print(f"\n  {BOLD}{GREEN}→ {hybrid_count} risk(s) confirmed by BOTH layers "
          f"(higher confidence).{RESET}")

    print(f"\n{BOLD}{'═' * 74}{RESET}")
    print(f"{BOLD}  All tests complete.{RESET}\n")


if __name__ == "__main__":
    main()
