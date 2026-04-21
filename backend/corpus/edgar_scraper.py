"""
SEC EDGAR Scraper
─────────────────
Downloads EX-10 (material contract) exhibits containing Master Service Agreements
from SEC EDGAR using the full-text search API (EFTS).

Pipeline:
  1. Search EFTS for documents matching MSA-related queries
  2. Filter for EX-10 exhibit types (material contracts)
  3. Construct direct document URLs from CIK + accession + filename
  4. Download, clean HTML, verify MSA content, save to disk

Rate-limits to 10 req/sec per SEC fair-access policy.
"""
from __future__ import annotations

import json
import logging
import re
import time
from pathlib import Path
from typing import Generator
from html.parser import HTMLParser

import requests

from backend.corpus.config import (
    CORPUS_RAW_DIR,
    EDGAR_RATE_LIMIT,
    EDGAR_TARGET_CONTRACTS,
    EDGAR_USER_AGENT,
)

log = logging.getLogger(__name__)

# ── Rate limiter ─────────────────────────────────────────────────────────────

class _RateLimiter:
    """Token-bucket rate limiter for SEC EDGAR fair-access compliance."""

    def __init__(self, max_per_sec: int = EDGAR_RATE_LIMIT):
        self._min_interval = 1.0 / max_per_sec
        self._last_call = 0.0

    def wait(self):
        now = time.monotonic()
        elapsed = now - self._last_call
        if elapsed < self._min_interval:
            time.sleep(self._min_interval - elapsed)
        self._last_call = time.monotonic()


_limiter = _RateLimiter()

# ── HTTP helpers ─────────────────────────────────────────────────────────────

_session = requests.Session()
_session.headers.update({
    "User-Agent": EDGAR_USER_AGENT,
    "Accept-Encoding": "gzip, deflate",
})


def _get(url: str, **kwargs) -> requests.Response:
    _limiter.wait()
    resp = _session.get(url, timeout=30, **kwargs)
    resp.raise_for_status()
    return resp


# ── HTML → plain text ────────────────────────────────────────────────────────

class _HTMLStripper(HTMLParser):
    def __init__(self):
        super().__init__()
        self._parts: list[str] = []
        self._skip = False

    def handle_starttag(self, tag, attrs):
        if tag in ("script", "style"):
            self._skip = True
        elif tag in ("br", "p", "div", "tr", "li", "h1", "h2", "h3", "h4"):
            self._parts.append("\n")

    def handle_endtag(self, tag):
        if tag in ("script", "style"):
            self._skip = False
        elif tag in ("p", "div", "tr", "li", "h1", "h2", "h3", "h4"):
            self._parts.append("\n")

    def handle_data(self, data):
        if not self._skip:
            self._parts.append(data)

    def get_text(self) -> str:
        raw = "".join(self._parts)
        raw = re.sub(r"[ \t]+", " ", raw)
        raw = re.sub(r"\n{3,}", "\n\n", raw)
        return raw.strip()


def _html_to_text(html: str) -> str:
    stripper = _HTMLStripper()
    stripper.feed(html)
    return stripper.get_text()


# ── EDGAR EFTS search ────────────────────────────────────────────────────────

_EFTS_URL = "https://efts.sec.gov/LATEST/search-index"

_SEARCH_QUERIES = [
    '"master service agreement" "software"',
    '"master service agreement" "cloud"',
    '"master service agreement" "subscription"',
    '"master service agreement" "platform"',
    '"software license agreement"',
    '"cloud services agreement"',
    '"master service agreement"',
]


def _search_efts(query: str, start: int = 0) -> dict:
    """Search EDGAR full-text search. Returns raw JSON response."""
    params = {
        "q": query,
        "dateRange": "custom",
        "startdt": "2018-01-01",
        "enddt": "2025-12-31",
        "forms": "10-K,10-Q,8-K",
        "from": start,
    }
    resp = _get(_EFTS_URL, params=params)
    return resp.json()


def _build_document_url(cik: str, accession: str, filename: str) -> str:
    """Build the direct URL to an EDGAR document."""
    accession_nodash = accession.replace("-", "")
    return f"https://www.sec.gov/Archives/edgar/data/{cik}/{accession_nodash}/{filename}"


def _iter_exhibit_hits(max_hits: int = 2000) -> Generator[dict, None, None]:
    """
    Yield EX-10 exhibit metadata from EFTS across all search queries.

    EFTS returns individual documents within filings. Each hit has:
      _id: "accession:filename"
      _source.file_type: e.g. "EX-10.1"
      _source.ciks: ["0001234567"]
      _source.adsh: "0001554855-23-000160"
      _source.display_names: ["Company Name (TICKER) (CIK ...)"]
    """
    seen_ids = set()
    total_yielded = 0

    for query in _SEARCH_QUERIES:
        if total_yielded >= max_hits:
            break
        offset = 0
        consecutive_empty = 0

        while total_yielded < max_hits:
            try:
                data = _search_efts(query, start=offset)
            except requests.HTTPError as e:
                log.warning("EFTS search failed at offset %d: %s", offset, e)
                break

            hits = data.get("hits", {}).get("hits", [])
            if not hits:
                break

            found_any = False
            for hit in hits:
                hit_id = hit.get("_id", "")
                if hit_id in seen_ids:
                    continue
                seen_ids.add(hit_id)

                src = hit.get("_source", {})
                file_type = (src.get("file_type") or "").upper()

                if not file_type.startswith("EX-10"):
                    continue

                accession = src.get("adsh", "")
                ciks = src.get("ciks", [])
                if not accession or not ciks:
                    continue

                # Extract filename from _id ("accession:filename")
                parts = hit_id.split(":", 1)
                if len(parts) != 2:
                    continue
                filename = parts[1]

                cik = ciks[0]
                company = ""
                display_names = src.get("display_names", [])
                if display_names:
                    company = re.sub(r"\s*\(CIK\s+\d+\)", "", display_names[0]).strip()
                    company = re.sub(r"\s*\([A-Z0-9, -]+\)\s*$", "", company).strip()

                url = _build_document_url(cik, accession, filename)

                yield {
                    "accession": accession,
                    "cik": cik,
                    "company": company,
                    "form_type": src.get("form", "") or src.get("root_forms", [""])[0],
                    "file_type": file_type,
                    "filed_date": src.get("file_date", ""),
                    "exhibit_url": url,
                    "filename": filename,
                }
                total_yielded += 1
                found_any = True

                if total_yielded >= max_hits:
                    break

            if not found_any:
                consecutive_empty += 1
                if consecutive_empty >= 3:
                    break
            else:
                consecutive_empty = 0

            offset += len(hits)

        log.info("Query %r: yielded %d EX-10 hits so far", query[:50], total_yielded)


# ── Download + clean exhibit ─────────────────────────────────────────────────

_MIN_CONTRACT_LENGTH = 2000
_MAX_CONTRACT_LENGTH = 500_000
_MSA_SIGNAL = re.compile(
    r"master\s+service[s]?\s+agreement|"
    r"software\s+as\s+a\s+service|"
    r"SaaS|"
    r"subscription\s+agreement|"
    r"cloud\s+service[s]?\s+agreement",
    re.IGNORECASE,
)


def _download_exhibit(url: str) -> str | None:
    """Download an exhibit and return cleaned plain text, or None if not useful."""
    try:
        resp = _get(url)
    except Exception as e:
        log.debug("Failed to download exhibit %s: %s", url, e)
        return None

    content_type = resp.headers.get("Content-Type", "")
    text = resp.text

    if "html" in content_type or text.strip().startswith("<"):
        text = _html_to_text(text)

    if len(text) < _MIN_CONTRACT_LENGTH:
        return None
    if len(text) > _MAX_CONTRACT_LENGTH:
        text = text[:_MAX_CONTRACT_LENGTH]

    if not _MSA_SIGNAL.search(text[:5000]):
        return None

    return text


# ── Public API ───────────────────────────────────────────────────────────────

def scrape_contracts(
    target: int = EDGAR_TARGET_CONTRACTS,
    output_dir: Path = CORPUS_RAW_DIR,
) -> list[dict]:
    """
    Scrape SaaS MSA contracts from SEC EDGAR.

    Returns list of metadata dicts for successfully downloaded contracts.
    Saves each contract as a .txt file in output_dir.
    """
    output_dir.mkdir(parents=True, exist_ok=True)
    manifest_path = output_dir / "manifest.json"

    existing: list[dict] = []
    if manifest_path.exists():
        existing = json.loads(manifest_path.read_text())
        log.info("Resuming: %d contracts already downloaded", len(existing))
    existing_accessions = {e["accession"] for e in existing}

    downloaded = list(existing)
    exhibits_checked = 0

    for exhibit in _iter_exhibit_hits(max_hits=target * 8):
        if len(downloaded) >= target:
            break

        if exhibit["accession"] in existing_accessions:
            continue

        exhibits_checked += 1
        text = _download_exhibit(exhibit["exhibit_url"])
        if text is None:
            continue

        contract_id = f"edgar_{len(downloaded):04d}"
        filename = f"{contract_id}.txt"
        (output_dir / filename).write_text(text, encoding="utf-8")

        meta = {
            "contract_id": contract_id,
            "filename": filename,
            "company": exhibit["company"],
            "form_type": exhibit["form_type"],
            "filed_date": exhibit["filed_date"],
            "accession": exhibit["accession"],
            "exhibit_url": exhibit["exhibit_url"],
            "char_count": len(text),
        }
        downloaded.append(meta)
        existing_accessions.add(exhibit["accession"])

        manifest_path.write_text(
            json.dumps(downloaded, indent=2), encoding="utf-8"
        )
        log.info(
            "[%d/%d] %s — %s (%d chars)",
            len(downloaded), target,
            contract_id, exhibit["company"], len(text),
        )

        if exhibits_checked % 50 == 0:
            log.info(
                "Progress: checked %d exhibits, downloaded %d contracts",
                exhibits_checked, len(downloaded),
            )

    log.info(
        "Scraping complete: %d contracts downloaded (checked %d exhibits)",
        len(downloaded), exhibits_checked,
    )
    return downloaded


if __name__ == "__main__":
    logging.basicConfig(level=logging.INFO, format="%(levelname)s %(message)s")
    results = scrape_contracts()
    print(f"\nDone. {len(results)} contracts saved to {CORPUS_RAW_DIR}")
