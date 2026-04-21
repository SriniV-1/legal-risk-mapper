"""
Contract Clause Chunker
───────────────────────
Segments raw contract text into typed clause chunks suitable for embedding and
structured extraction.

Strategy:
  1. Split on section headers (numbered headings like "1.", "1.1", "ARTICLE I",
     or all-caps lines)
  2. Within each section, sub-split on long paragraphs using spaCy or semicolons
  3. Classify each chunk into one of the 6 target categories (or "other")
     using keyword heuristics — fast pre-filter, not final classification
  4. Attach metadata: section number, position, estimated category

The chunker intentionally over-segments slightly: it's better for RAG retrieval
to have focused chunks than to have multi-topic chunks that dilute similarity.
"""
from __future__ import annotations

import re
import logging
from dataclasses import dataclass, field, asdict
from typing import Optional

log = logging.getLogger(__name__)

# ── Chunk data structure ─────────────────────────────────────────────────────

@dataclass
class ClauseChunk:
    text: str
    chunk_index: int
    section_header: str = ""
    estimated_category: str = "other"
    char_count: int = 0
    contract_id: str = ""

    def __post_init__(self):
        self.char_count = len(self.text)

    def to_dict(self) -> dict:
        return asdict(self)


# ── Section splitting ────────────────────────────────────────────────────────

_SECTION_HEADER = re.compile(
    r"(?:^|\n)"
    r"("
    r"(?:ARTICLE|SECTION|EXHIBIT)\s+[IVXLCDM\d]+"  # ARTICLE I, SECTION 1
    r"|(?:\d{1,2}\.(?:\d{1,2}\.?)*)\s"              # 1. or 1.1 or 1.1.1
    r"|[A-Z][A-Z\s,/&]{4,}(?:\.|$)"                  # ALL CAPS HEADERS
    r")",
    re.MULTILINE,
)

_MIN_CHUNK_CHARS = 50
_MAX_CHUNK_CHARS = 1500
_TARGET_CHUNK_CHARS = 800


def _split_sections(text: str) -> list[tuple[str, str]]:
    """Split text into (header, body) tuples at section boundaries."""
    splits = list(_SECTION_HEADER.finditer(text))

    if not splits:
        return [("", text)]

    sections = []
    for i, match in enumerate(splits):
        header = match.group(1).strip()
        start = match.end()
        end = splits[i + 1].start() if i + 1 < len(splits) else len(text)
        body = text[start:end].strip()
        if body:
            sections.append((header, body))

    preamble = text[:splits[0].start()].strip()
    if preamble and len(preamble) >= _MIN_CHUNK_CHARS:
        sections.insert(0, ("PREAMBLE", preamble))

    return sections


# ── Sub-splitting long sections ──────────────────────────────────────────────

_PARAGRAPH_BREAK = re.compile(r"\n\s*\n")
_SEMICOLON_SPLIT = re.compile(r";\s*(?=[a-zA-Z(])")


def _subsplit(text: str) -> list[str]:
    """Break a long section body into smaller chunks."""
    if len(text) <= _MAX_CHUNK_CHARS:
        return [text]

    paragraphs = _PARAGRAPH_BREAK.split(text)
    if len(paragraphs) > 1 and all(len(p) <= _MAX_CHUNK_CHARS for p in paragraphs):
        return [p.strip() for p in paragraphs if len(p.strip()) >= _MIN_CHUNK_CHARS]

    chunks = []
    current = ""
    for para in paragraphs:
        if len(current) + len(para) <= _TARGET_CHUNK_CHARS:
            current = f"{current}\n\n{para}" if current else para
        else:
            if current:
                chunks.append(current.strip())
            if len(para) > _MAX_CHUNK_CHARS and ";" in para:
                parts = _SEMICOLON_SPLIT.split(para)
                sub_current = ""
                for part in parts:
                    if len(sub_current) + len(part) <= _TARGET_CHUNK_CHARS:
                        sub_current = f"{sub_current}; {part}" if sub_current else part
                    else:
                        if sub_current:
                            chunks.append(sub_current.strip())
                        sub_current = part
                if sub_current:
                    chunks.append(sub_current.strip())
                current = ""
            else:
                current = para
    if current:
        chunks.append(current.strip())

    return [c for c in chunks if len(c) >= _MIN_CHUNK_CHARS]


# ── Category classification (keyword heuristic) ─────────────────────────────

_CATEGORY_KEYWORDS: dict[str, list[str]] = {
    "liability": [
        "liability", "liable", "indemnif", "hold harmless", "consequential damage",
        "aggregate cap", "limitation of liability", "damages", "negligence",
        "warranty", "warranties", "disclaim", "as is", "as-is",
    ],
    "termination": [
        "terminat", "expir", "notice period", "for cause", "convenience",
        "survival", "wind-down", "cure period", "renewal", "non-renewal",
    ],
    "ip": [
        "intellectual property", "patent", "copyright", "trademark", "trade secret",
        "license grant", "work for hire", "work-for-hire", "residual",
        "ownership", "proprietary right", "feedback", "derivative work",
    ],
    "payment": [
        "payment", "invoice", "net 30", "net 60", "late fee", "interest rate",
        "price", "fee", "compensation", "true-up", "true up", "escalat",
        "currency", "tax", "withhold",
    ],
    "confidentiality": [
        "confidential", "non-disclosure", "nda", "trade secret",
        "return or destroy", "return or destruction", "receiving party",
        "disclosing party", "proprietary information",
    ],
    "governing_law": [
        "governing law", "jurisdiction", "venue", "arbitrat", "dispute resolution",
        "class action waiver", "jury waiver", "mediat", "forum",
        "applicable law", "choice of law",
    ],
}


def _classify_chunk(text: str, header: str = "") -> str:
    """Assign a category based on keyword density. Returns best match or 'other'."""
    combined = f"{header} {text}".lower()
    scores: dict[str, int] = {}
    for category, keywords in _CATEGORY_KEYWORDS.items():
        score = sum(1 for kw in keywords if kw in combined)
        if score > 0:
            scores[category] = score

    if not scores:
        return "other"
    return max(scores, key=scores.get)


# ── Public API ───────────────────────────────────────────────────────────────

def chunk_contract(
    text: str,
    contract_id: str = "",
) -> list[ClauseChunk]:
    """
    Segment a contract into typed clause chunks.

    Returns a list of ClauseChunk objects with estimated categories.
    """
    text = text.replace("\r\n", "\n").replace("\r", "\n")
    sections = _split_sections(text)
    chunks: list[ClauseChunk] = []

    for header, body in sections:
        sub_chunks = _subsplit(body)
        for sub_text in sub_chunks:
            category = _classify_chunk(sub_text, header)
            chunk = ClauseChunk(
                text=sub_text,
                chunk_index=len(chunks),
                section_header=header,
                estimated_category=category,
                contract_id=contract_id,
            )
            chunks.append(chunk)

    log.info(
        "Chunked %s: %d sections → %d chunks (categories: %s)",
        contract_id or "contract",
        len(sections),
        len(chunks),
        {cat: sum(1 for c in chunks if c.estimated_category == cat)
         for cat in set(c.estimated_category for c in chunks)},
    )
    return chunks
