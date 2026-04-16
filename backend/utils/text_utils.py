"""
Text preprocessing and utility functions.
"""
import re
from typing import List, Tuple


def clean_text(text: str) -> str:
    """Normalize whitespace and remove control characters."""
    text = re.sub(r'\r\n|\r', '\n', text)
    text = re.sub(r'[ \t]+', ' ', text)
    text = re.sub(r'\n{3,}', '\n\n', text)
    return text.strip()


def extract_sentences(text: str) -> List[str]:
    """
    Split text into sentences using a simple regex-based splitter.
    Handles common abbreviations to avoid false splits.
    """
    # Protect common abbreviations
    protected = re.sub(
        r'\b(Mr|Mrs|Ms|Dr|Prof|Sr|Jr|vs|etc|i\.e|e\.g|Inc|Ltd|Corp|Co|No|Sec|Art)\.',
        r'\1<DOT>',
        text
    )
    # Split on sentence-ending punctuation
    sentences = re.split(r'(?<=[.!?])\s+(?=[A-Z0-9"])', protected)
    # Restore dots
    sentences = [s.replace('<DOT>', '.').strip() for s in sentences if s.strip()]
    return sentences


def get_context_window(text: str, match_start: int, match_end: int, window: int = 150) -> str:
    """Extract a context window around a matched position."""
    start = max(0, match_start - window)
    end = min(len(text), match_end + window)
    snippet = text[start:end].strip()
    # Add ellipsis if truncated
    if start > 0:
        snippet = '...' + snippet
    if end < len(text):
        snippet = snippet + '...'
    return snippet


def compute_tfidf_boost(keyword: str, text: str, corpus_freq: float = 0.1) -> float:
    """
    Simple TF-IDF-inspired score for a keyword in the document.
    Higher frequency in doc relative to corpus baseline → higher boost.
    """
    text_lower = text.lower()
    keyword_lower = keyword.lower()
    # Term frequency
    count = len(re.findall(r'\b' + re.escape(keyword_lower) + r'\b', text_lower))
    word_count = max(len(text_lower.split()), 1)
    tf = count / word_count
    # IDF approximation (inverse of corpus frequency baseline)
    import math
    idf = math.log(1 / (corpus_freq + 1e-9))
    tfidf = tf * idf
    # Normalize to 0-1 range
    return min(1.0, tfidf * 10)


def deduplicate_risks(risks: list, similarity_threshold: float = 0.7) -> list:
    """
    Remove near-duplicate risks based on text snippet overlap.
    Keeps the highest-severity version.
    """
    severity_order = {"High": 3, "Medium": 2, "Low": 1}
    seen_snippets = []
    deduped = []

    for risk in sorted(risks, key=lambda r: severity_order.get(r["severity"], 0), reverse=True):
        snippet = risk["text_snippet"].lower()
        is_dup = False
        for seen in seen_snippets:
            # Jaccard similarity on word sets
            set_a = set(snippet.split())
            set_b = set(seen.split())
            if len(set_a | set_b) == 0:
                continue
            similarity = len(set_a & set_b) / len(set_a | set_b)
            if similarity >= similarity_threshold:
                is_dup = True
                break
        if not is_dup:
            seen_snippets.append(snippet)
            deduped.append(risk)

    return deduped
