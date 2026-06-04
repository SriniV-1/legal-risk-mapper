"""
Tests for upload hardening on the /analyze/upload endpoint.

Covers:
  - File size limit (10 MB, HTTP 413)
  - MIME / magic-byte validation (fake PDF → 400)
  - Valid .txt accepted
  - Valid .pdf accepted
  - Empty file handled gracefully
"""
import pytest
from fastapi.testclient import TestClient

from backend.main import app

client = TestClient(app)


class TestUploadSizeLimit:
    def test_file_over_10mb_rejected(self):
        """A file exceeding 10 MB must be rejected with HTTP 413."""
        oversized = b"x" * (10 * 1024 * 1024 + 1)
        r = client.post(
            "/analyze/upload",
            files={"file": ("big.txt", oversized, "text/plain")},
        )
        assert r.status_code == 413
        assert "too large" in r.json()["detail"].lower()


class TestMimeValidation:
    def test_renamed_exe_as_pdf_rejected(self):
        """A non-PDF file renamed to .pdf (no %PDF header) must be rejected."""
        # MZ header = Windows PE/EXE signature
        fake_pdf = b"MZ\x90\x00\x03\x00\x00\x00" + b"\x00" * 256
        r = client.post(
            "/analyze/upload",
            files={"file": ("malware.pdf", fake_pdf, "application/pdf")},
        )
        assert r.status_code == 400
        assert "%PDF" in r.json()["detail"]

    def test_random_bytes_as_pdf_rejected(self):
        """Random binary content named .pdf must be rejected."""
        r = client.post(
            "/analyze/upload",
            files={"file": ("report.pdf", b"not a pdf at all", "application/pdf")},
        )
        assert r.status_code == 400


class TestValidUploads:
    def test_valid_txt_accepted(self):
        """A normal .txt file with sufficient content should be accepted."""
        content = b"This agreement is provided AS-IS. No warranties. Client shall indemnify Company."
        r = client.post(
            "/analyze/upload",
            files={"file": ("contract.txt", content, "text/plain")},
        )
        assert r.status_code == 200
        data = r.json()
        assert "total_risks" in data
        assert data["total_risks"] >= 0

    def test_valid_pdf_accepted(self):
        """A real PDF file should be accepted and analyzed."""
        import pymupdf

        doc = pymupdf.open()
        page = doc.new_page()
        page.insert_text(
            (72, 72),
            "This agreement is provided AS-IS without warranty. "
            "Client shall indemnify Company against all claims.",
        )
        pdf_bytes = doc.tobytes()
        doc.close()

        r = client.post(
            "/analyze/upload",
            files={"file": ("contract.pdf", pdf_bytes, "application/pdf")},
        )
        assert r.status_code == 200
        data = r.json()
        assert "total_risks" in data

    def test_valid_md_accepted(self):
        """A .md (markdown) file should be accepted like .txt."""
        content = b"# Contract\n\nThis agreement is provided AS-IS. No warranties. Client shall indemnify Company."
        r = client.post(
            "/analyze/upload",
            files={"file": ("contract.md", content, "text/markdown")},
        )
        assert r.status_code == 200


class TestEmptyFileHandling:
    def test_empty_file_rejected_gracefully(self):
        """An empty file should be rejected with 400, not crash."""
        r = client.post(
            "/analyze/upload",
            files={"file": ("empty.txt", b"", "text/plain")},
        )
        assert r.status_code == 400
        assert "empty" in r.json()["detail"].lower()

    def test_whitespace_only_file_rejected(self):
        """A file with only whitespace should be rejected."""
        r = client.post(
            "/analyze/upload",
            files={"file": ("blank.txt", b"   \n\n  ", "text/plain")},
        )
        assert r.status_code == 400

    def test_empty_pdf_rejected(self):
        """An empty file named .pdf (no %PDF header) should be rejected."""
        r = client.post(
            "/analyze/upload",
            files={"file": ("empty.pdf", b"", "application/pdf")},
        )
        assert r.status_code == 400
