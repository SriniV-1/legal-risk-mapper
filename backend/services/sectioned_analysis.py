"""Section-by-section risk analysis, so long documents don't go through one giant pass."""
from __future__ import annotations

import re

from backend.corpus.chunker import _SECTION_HEADER
from backend.services.limits import LOCAL_MAX_WORDS
from backend.services.risk_analyzer import analyze_risks
from backend.utils.text_utils import deduplicate_risks

MIN_SECTION_WORDS = 40
SECTION_MAX_WORDS = LOCAL_MAX_WORDS

_PARA = re.compile(r"\n\s*\n")


def _wc(t: str) -> int:
    return len(t.split())


def _parts(text: str) -> list[str]:
    """Pack paragraphs into chunks <= SECTION_MAX_WORDS; oversized paragraphs get word windows."""
    chunks: list[str] = []
    cur: list[str] = []
    cur_n = 0
    for para in _PARA.split(text):
        n = _wc(para)
        if n > SECTION_MAX_WORDS:
            if cur:
                chunks.append("\n\n".join(cur))
                cur, cur_n = [], 0
            w = para.split()
            chunks += [" ".join(w[i:i + SECTION_MAX_WORDS]) for i in range(0, len(w), SECTION_MAX_WORDS)]
        elif cur_n + n > SECTION_MAX_WORDS:
            chunks.append("\n\n".join(cur))
            cur, cur_n = [para], n
        else:
            cur.append(para)
            cur_n += n
    if cur:
        chunks.append("\n\n".join(cur))
    return [c for c in chunks if c.strip()]


def _label(line: str) -> str:
    """Header line cut at the first sentence end (letter or ')' then '.', not '3.1') or at 60 chars."""
    line = line.strip()
    m = re.search(r"[a-z)]\.(?:\s|$)", line)
    if m and m.start() + 2 <= 60:
        return line[:m.start() + 2]
    return line if len(line) <= 60 else line[:60].rstrip() + "\u2026"


def split_into_sections(text: str) -> list[tuple[str, str]]:
    """(header, section_text) pairs. Every word of `text` lands in exactly one section, in order."""
    starts = [m.start(1) for m in _SECTION_HEADER.finditer(text)]
    if not starts:
        return [("", text)]
    # label = the whole header line, not just the regex match ("3." -> "3.1 Payment Terms")
    heads = [_label(text[i:].split("\n", 1)[0]) for i in starts]
    bounds = starts + [len(text)]
    secs: list[tuple[str, str]] = []
    if text[:starts[0]].strip():
        secs.append(("PREAMBLE", text[:starts[0]]))
    secs += [(h, text[bounds[i]:bounds[i + 1]]) for i, h in enumerate(heads)]

    merged: list[tuple[str, str]] = []
    for h, t in secs:
        if merged and _wc(t) < MIN_SECTION_WORDS:
            merged[-1] = (merged[-1][0], merged[-1][1] + "\n" + t)
        else:
            merged.append((h, t))
    if len(merged) > 1 and _wc(merged[0][1]) < MIN_SECTION_WORDS:
        merged[1] = (merged[1][0], merged[0][1] + "\n" + merged[1][1])
        merged.pop(0)

    out: list[tuple[str, str]] = []
    for h, t in merged:
        if _wc(t) > SECTION_MAX_WORDS:
            out += [(f"{h} (part {i})", p) for i, p in enumerate(_parts(t), 1)]
        else:
            out.append((h, t))
    return out


def analyze_document(text: str) -> list[dict]:
    """Run analyze_risks per section; tag each risk with its section; clause_index is document-global."""
    # Cross-category escalation and dedup inside analyze_risks are per-section here (accepted); only the final dedup is document-wide.
    all_risks: list[dict] = []
    offset = 0
    for header, body in split_into_sections(text):
        risks = analyze_risks(body)
        top = -1
        for r in risks:
            r["section"] = header or None
            if r.get("clause_index") is not None:
                top = max(top, r["clause_index"])
                r["clause_index"] += offset
        offset += top + 1
        all_risks += risks
    # dedup across sections too, so boilerplate repeated in many sections is reported once
    return sorted(deduplicate_risks(all_risks), key=lambda r: r["score"], reverse=True)
