"""Section-by-section analysis: splitting, section tags, and the raised local cap."""
import pytest
from fastapi.testclient import TestClient

from backend.main import app
from backend.services import sectioned_analysis as S
from backend.services import limits as L

client = TestClient(app)

BODY = ("The Supplier shall indemnify and hold harmless the Customer against all losses "
        "arising from any breach of this Agreement, without limitation of liability. ") * 3


def doc(*heads):
    return "\n".join(f"{h}\n{BODY}" for h in heads)


def wordseq(text):
    return text.split()


class TestSplit:
    def test_headers(self):
        text = doc("SECTION 1", "SECTION 2", "SECTION 3")
        secs = S.split_into_sections(text)
        assert [h for h, _ in secs] == ["SECTION 1", "SECTION 2", "SECTION 3"]
        assert secs[0][1].startswith("SECTION 1")

    def test_no_text_loss(self):
        text = "Short intro.\n" + doc("ARTICLE I", "ARTICLE II") + "\n1. tiny\n" + doc("SECTION 9")
        secs = S.split_into_sections(text)
        assert [w for _, t in secs for w in wordseq(t)] == wordseq(text)

    def test_no_headers(self):
        text = "just some plain lowercase words " * 30
        assert S.split_into_sections(text) == [("", text)]

    def test_short_preamble_kept(self):
        secs = S.split_into_sections("Hi.\n" + doc("SECTION 1", "SECTION 2"))
        # preamble under MIN words merges into the next section (taking its header), never dropped
        assert [h for h, _ in secs] == ["SECTION 1", "SECTION 2"]
        assert secs[0][1].startswith("Hi.")

    def test_long_preamble_header(self):
        pre = "This Agreement is made between the parties named below. " * 10
        secs = S.split_into_sections(pre + "\n" + doc("SECTION 1"))
        assert secs[0][0] == "PREAMBLE"

    def test_tiny_section_merges_into_previous(self):
        text = doc("SECTION 1") + "\nSECTION 2\nTiny.\n" + doc("SECTION 3")
        secs = S.split_into_sections(text)
        assert [h for h, _ in secs] == ["SECTION 1", "SECTION 3"]
        assert "Tiny." in secs[0][1]

    def test_oversized_section_split_into_parts(self, monkeypatch):
        monkeypatch.setattr(S, "SECTION_MAX_WORDS", 100)
        paras = "\n\n".join([BODY] * 6)  # ~25 words each
        text = "SECTION 1\n" + paras
        secs = S.split_into_sections(text)
        assert len(secs) > 1
        assert secs[0][0] == "SECTION 1 (part 1)"
        assert all(len(t.split()) <= 100 for _, t in secs)
        assert [w for _, t in secs for w in wordseq(t)] == wordseq(text)

    def test_oversized_without_paragraphs_uses_word_windows(self, monkeypatch):
        monkeypatch.setattr(S, "SECTION_MAX_WORDS", 50)
        text = "SECTION 1\n" + " ".join(f"w{i}" for i in range(180))
        secs = S.split_into_sections(text)
        assert len(secs) == 4
        assert [w for _, t in secs for w in wordseq(t)] == wordseq(text)


class TestLabels:
    def test_label_is_full_header_line(self):
        text = f"3.1 Payment Terms\n{BODY}\nARTICLE IV INDEMNIFICATION\n{BODY}\n3. Misc\n{BODY}"
        heads = [h for h, _ in S.split_into_sections(text)]
        assert heads == ["3.1 Payment Terms", "ARTICLE IV INDEMNIFICATION", "3. Misc"]

    def test_label_cut_at_first_sentence(self):
        text = "3.1 Customer shall pay all invoices within fifteen days. 3.2 Late fees apply.\n" + BODY
        assert S.split_into_sections(text)[0][0] == "3.1 Customer shall pay all invoices within fifteen days."

    def test_label_truncated_to_60_with_ellipsis(self):
        text = "SECTION 1 " + "x" * 200 + "\n" + BODY
        h = S.split_into_sections(text)[0][0]
        assert len(h) <= 61 and h.endswith("\u2026")


class TestAnalyzeDocument:
    def test_duplicate_clause_across_sections_appears_once(self):
        one = S.analyze_document(doc("SECTION 1"))
        two = S.analyze_document(doc("SECTION 1", "SECTION 2"))
        assert len(two) == len(one)
        assert all(r["section"] == "SECTION 1" and r["clause_index"] is not None for r in two)

    def test_section_tag_and_unique_clause_index(self):
        risks = S.analyze_document(doc("SECTION 1", "SECTION 2"))
        assert risks
        assert all("section" in r for r in risks)
        assert {r["section"] for r in risks} <= {"SECTION 1", "SECTION 2"}
        idx = [r["clause_index"] for r in risks if r["clause_index"] is not None]
        assert len(idx) == len(set(idx))
        scores = [r["score"] for r in risks]
        assert scores == sorted(scores, reverse=True)

    def test_headerless_doc_has_none_section(self):
        risks = S.analyze_document(BODY)
        assert risks and all(r["section"] is None for r in risks)


class TestRoutes:
    def test_60k_words_accepted(self):
        text = "SECTION 1\n" + "The parties agree to cooperate in good faith. " * 6700  # ~60k words
        assert L.count_words(text) > 50_000
        r = client.post("/analyze", json={"text": text})
        assert r.status_code == 200

    def test_101k_words_rejected(self):
        r = client.post("/analyze", json={"text": "word " * 101_000})
        assert r.status_code == 413


class TestGroqRateLimit:
    @staticmethod
    def _err():
        import groq, httpx
        req = httpx.Request("POST", "https://api.groq.com/x")
        resp = httpx.Response(429, request=req, headers={"retry-after": "17"})
        return groq.RateLimitError("rate limited", response=resp, body=None)

    MSG = "Groq's shared free-tier limit is busy right now. Wait about a minute and try again."
    CLAUSE = "Company's total liability shall not exceed the fees paid in the twelve months preceding the claim."

    def test_benchmark_429(self, monkeypatch):
        import backend.benchmarking.benchmarker as B
        err = self._err()
        monkeypatch.setattr(B, "benchmark_clause", lambda *a, **k: (_ for _ in ()).throw(err))
        r = client.post("/benchmark", json={"text": self.CLAUSE})
        assert r.status_code == 429 and r.json()["detail"] == self.MSG
        assert r.headers["retry-after"] == "17"

    def test_redline_429_default_retry_after(self, monkeypatch):
        import groq, httpx
        import backend.benchmarking.benchmarker as B
        e = groq.RateLimitError("x", response=httpx.Response(429, request=httpx.Request("POST", "https://a")), body=None)
        monkeypatch.setattr(B, "benchmark_clause", lambda *a, **k: (_ for _ in ()).throw(e))
        r = client.post("/redline", json={"text": self.CLAUSE})
        assert r.status_code == 429 and r.json()["detail"] == self.MSG
        assert r.headers["retry-after"] == "60"

    def test_extract_clause_propagates(self, monkeypatch):
        import pytest
        import groq
        from backend.extraction import extractor as E
        err = self._err()
        monkeypatch.setattr(E, "_call_llm", lambda *a, **k: (_ for _ in ()).throw(err))
        with pytest.raises(groq.RateLimitError):
            E.extract_clause(self.CLAUSE, clause_type="liability", max_retries=1)

    def test_generate_redlines_propagates(self, monkeypatch):
        import pytest
        import groq
        from backend.redline import generator as G
        from backend.benchmarking.schemas import BenchmarkResult
        err = self._err()
        monkeypatch.setattr(G, "_call_llm", lambda *a, **k: (_ for _ in ()).throw(err))
        with pytest.raises(groq.RateLimitError):
            G.generate_redlines(self.CLAUSE, BenchmarkResult(clause_type="liability", sample_size=0))

    def test_slowapi_handler_detail(self):
        from slowapi.errors import RateLimitExceeded
        import asyncio
        from backend.main import _rate_limited
        class Lim:  # minimal Limit stand-in
            error_message = None
            limit = "10 per 1 minute"
        resp = asyncio.run(_rate_limited(None, RateLimitExceeded(Lim())))
        assert resp.status_code == 429
        assert b"Too many requests from you in the last minute" in resp.body
        assert resp.headers["retry-after"]


def _old_dedup(risks, similarity_threshold=0.7):
    """Reference copy of the original O(n^2) deduplicate_risks."""
    severity_order = {"High": 3, "Medium": 2, "Low": 1}
    seen_snippets, deduped = [], []
    for risk in sorted(risks, key=lambda r: severity_order.get(r["severity"], 0), reverse=True):
        snippet = risk["text_snippet"].lower()
        is_dup = False
        for seen in seen_snippets:
            set_a, set_b = set(snippet.split()), set(seen.split())
            if len(set_a | set_b) == 0:
                continue
            if len(set_a & set_b) / len(set_a | set_b) >= similarity_threshold:
                is_dup = True
                break
        if not is_dup:
            seen_snippets.append(snippet)
            deduped.append(risk)
    return deduped


class TestDedupFast:
    @staticmethod
    def _risks(rng, n):
        vocab = [f"w{i}" for i in range(40)]
        out = []
        for i in range(n):
            if out and rng.random() < 0.3:  # near-duplicate of an earlier one
                words = out[rng.randrange(len(out))]["text_snippet"].split()
                if words and rng.random() < 0.7:
                    words[rng.randrange(len(words))] = rng.choice(vocab)
                snippet = " ".join(words).upper() if rng.random() < 0.3 else " ".join(words)
            else:
                snippet = " ".join(rng.choices(vocab, k=rng.randint(0, 15)))
            out.append({"severity": rng.choice(["High", "Medium", "Low"]), "text_snippet": snippet, "i": i})
        return out

    def test_matches_reference(self):
        import random
        from backend.utils.text_utils import deduplicate_risks
        rng = random.Random(7)
        for _ in range(300):
            risks = self._risks(rng, rng.randint(0, 40))
            assert deduplicate_risks(risks) == _old_dedup(risks)
            assert deduplicate_risks(risks, 0.5) == _old_dedup(risks, 0.5)

    def test_3000_distinct_under_2s(self):
        import random, time
        from backend.utils.text_utils import deduplicate_risks
        rng = random.Random(1)
        vocab = [f"w{i}" for i in range(3000)]
        risks = [{"severity": "High", "text_snippet": " ".join(rng.choices(vocab, k=rng.randint(10, 40)))}
                 for _ in range(3000)]
        t = time.time()
        assert len(deduplicate_risks(risks)) == 3000
        assert time.time() - t < 2
