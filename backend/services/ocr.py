"""
OCR fallback for scanned PDF text extraction.

Pipeline:
  1. Try PyMuPDF (fast, digital PDFs)
  2. If extracted text < 50 chars → likely scanned → fall back to Tesseract OCR
  3. If Tesseract is not installed → log warning, return whatever PyMuPDF got
"""
import logging

logger = logging.getLogger("lrm.ocr")

# Minimum character count to consider a PDF "digital" (has selectable text).
_MIN_DIGITAL_CHARS = 50


def extract_text_from_pdf(pdf_bytes: bytes) -> tuple[str, str]:
    """
    Extract text from a PDF, falling back to OCR for scanned documents.

    Returns:
        (text, method) where method is "digital" or "ocr".
    """
    # ── Step 1: Try PyMuPDF for digital text ─────────────────────────────
    pymupdf_text = ""
    try:
        import pymupdf
        doc = pymupdf.open(stream=pdf_bytes, filetype="pdf")
        pages = [page.get_text() for page in doc]
        page_count = len(pages)
        doc.close()
        pymupdf_text = "\n\n".join(pages)
    except Exception as e:
        logger.warning("PyMuPDF extraction failed: %s", e)
        page_count = 0

    # If we got enough text, it's a digital PDF — fast path.
    if len(pymupdf_text.strip()) >= _MIN_DIGITAL_CHARS:
        logger.info(
            "Digital PDF extraction | pages=%d | chars=%d",
            page_count, len(pymupdf_text),
        )
        return pymupdf_text, "digital"

    # ── Step 2: Fall back to OCR ─────────────────────────────────────────
    logger.info(
        "PyMuPDF returned %d chars (< %d threshold), attempting OCR fallback",
        len(pymupdf_text.strip()), _MIN_DIGITAL_CHARS,
    )

    try:
        from pdf2image import convert_from_bytes
        import pytesseract
    except ImportError as e:
        logger.warning(
            "OCR dependencies not available (%s); returning PyMuPDF text as-is", e
        )
        return pymupdf_text, "digital"

    try:
        images = convert_from_bytes(pdf_bytes)
        ocr_pages = []
        for i, image in enumerate(images):
            text = pytesseract.image_to_string(image)
            ocr_pages.append(text)

        ocr_text = "\n\n".join(ocr_pages)
        logger.info(
            "OCR extraction complete | pages=%d | chars=%d",
            len(ocr_pages), len(ocr_text),
        )
        return ocr_text, "ocr"

    except Exception as e:
        # Covers TesseractNotFoundError, poppler not installed, etc.
        logger.warning(
            "OCR fallback failed (%s); returning PyMuPDF text as-is", e
        )
        return pymupdf_text, "digital"
