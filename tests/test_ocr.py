"""Tests for PDF OCR fallback extraction (Phase 14.3)."""
import io
from unittest.mock import patch, MagicMock

import pytest
from fastapi.testclient import TestClient

from backend.main import app


client = TestClient(app)


# ── Helpers ──────────────────────────────────────────────────────────────────

def _make_digital_pdf(text: str = "This is a digital PDF with enough text for testing purposes and extraction.") -> bytes:
    """Create a minimal in-memory PDF with selectable text using PyMuPDF."""
    import pymupdf
    doc = pymupdf.open()
    page = doc.new_page()
    page.insert_text((72, 72), text)
    pdf_bytes = doc.tobytes()
    doc.close()
    return pdf_bytes


def _make_empty_pdf() -> bytes:
    """Create a PDF with no text content (blank page)."""
    import pymupdf
    doc = pymupdf.open()
    doc.new_page()
    pdf_bytes = doc.tobytes()
    doc.close()
    return pdf_bytes


# ── Unit tests for extract_text_from_pdf ─────────────────────────────────────

class TestDigitalPdfExtraction:
    """Digital PDFs should use PyMuPDF (fast path), method='digital'."""

    def test_digital_pdf_returns_text_and_method(self):
        from backend.services.ocr import extract_text_from_pdf

        pdf_bytes = _make_digital_pdf()
        text, method = extract_text_from_pdf(pdf_bytes)

        assert method == "digital"
        assert len(text.strip()) >= 50
        assert "digital PDF" in text

    def test_pymupdf_preferred_over_ocr(self):
        """When PyMuPDF extracts enough text, OCR should never be called."""
        from backend.services.ocr import extract_text_from_pdf

        pdf_bytes = _make_digital_pdf()
        text, method = extract_text_from_pdf(pdf_bytes)

        # Digital path should be used — OCR never invoked
        assert method == "digital"
        assert len(text.strip()) >= 50


class TestOcrFallback:
    """Scanned PDFs (< 50 chars from PyMuPDF) should fall back to OCR."""

    def test_ocr_fallback_for_scanned_pdf(self):
        """When PyMuPDF returns little text, OCR should be invoked."""
        from backend.services.ocr import extract_text_from_pdf

        pdf_bytes = _make_empty_pdf()

        mock_image = MagicMock()
        mock_convert = MagicMock(return_value=[mock_image])
        mock_tesseract = MagicMock()
        mock_tesseract.image_to_string = MagicMock(return_value="OCR extracted contract text for testing")

        with patch.dict("sys.modules", {
            "pdf2image": MagicMock(convert_from_bytes=mock_convert),
            "pytesseract": mock_tesseract,
        }):
            # Force re-import within the function
            text, method = extract_text_from_pdf(pdf_bytes)

        assert method == "ocr"
        assert "OCR extracted" in text

    def test_graceful_fallback_tesseract_not_installed(self):
        """When pytesseract import fails, should return PyMuPDF text without crashing."""
        from backend.services.ocr import extract_text_from_pdf
        import builtins

        pdf_bytes = _make_empty_pdf()

        original_import = builtins.__import__

        def mock_import(name, *args, **kwargs):
            if name in ("pytesseract", "pdf2image"):
                raise ImportError(f"No module named '{name}'")
            return original_import(name, *args, **kwargs)

        with patch.object(builtins, "__import__", side_effect=mock_import):
            text, method = extract_text_from_pdf(pdf_bytes)

        # Should not crash; returns whatever PyMuPDF got
        assert method == "digital"
        assert isinstance(text, str)

    def test_graceful_fallback_tesseract_runtime_error(self):
        """When Tesseract binary is missing at runtime, should not crash."""
        from backend.services.ocr import extract_text_from_pdf

        pdf_bytes = _make_empty_pdf()

        mock_convert = MagicMock(return_value=[MagicMock()])

        # Simulate TesseractNotFoundError (a subclass of OSError)
        class TesseractNotFoundError(OSError):
            pass

        mock_tesseract = MagicMock()
        mock_tesseract.image_to_string = MagicMock(
            side_effect=TesseractNotFoundError("tesseract is not installed")
        )

        with patch.dict("sys.modules", {
            "pdf2image": MagicMock(convert_from_bytes=mock_convert),
            "pytesseract": mock_tesseract,
        }):
            text, method = extract_text_from_pdf(pdf_bytes)

        # Falls back to PyMuPDF output
        assert method == "digital"
        assert isinstance(text, str)


class TestEmptyPdf:
    """Empty/blank PDFs should be handled without errors."""

    def test_empty_pdf_returns_string(self):
        from backend.services.ocr import extract_text_from_pdf
        import builtins

        pdf_bytes = _make_empty_pdf()

        original_import = builtins.__import__

        # Mock OCR deps to avoid needing Tesseract
        def mock_import(name, *args, **kwargs):
            if name in ("pytesseract", "pdf2image"):
                raise ImportError(f"No module named '{name}'")
            return original_import(name, *args, **kwargs)

        with patch.object(builtins, "__import__", side_effect=mock_import):
            text, method = extract_text_from_pdf(pdf_bytes)

        assert isinstance(text, str)
        assert method == "digital"


class TestUploadEndpointExtractionMethod:
    """The /analyze/upload response should include X-Extraction-Method header."""

    def test_pdf_upload_includes_extraction_method_header(self):
        pdf_bytes = _make_digital_pdf(
            "This contract contains an indemnification clause that exposes significant liability risk to the party."
        )

        response = client.post(
            "/analyze/upload",
            files={"file": ("contract.pdf", io.BytesIO(pdf_bytes), "application/pdf")},
        )

        assert response.status_code == 200
        assert "x-extraction-method" in response.headers
        assert response.headers["x-extraction-method"] in ("digital", "ocr")

    def test_txt_upload_includes_extraction_method_header(self):
        text_content = b"This contract contains an indemnification clause that exposes significant liability risk."

        response = client.post(
            "/analyze/upload",
            files={"file": ("contract.txt", io.BytesIO(text_content), "text/plain")},
        )

        assert response.status_code == 200
        assert response.headers.get("x-extraction-method") == "text"
