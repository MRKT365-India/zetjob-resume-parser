"""
OCR module for scanned / image-based resume PDFs.

Providers:
- gemini: Google Gemini Vision — renders PDF pages as images and extracts text
- stub: no-op (legacy / test mode)
"""
import base64
import logging
import os
from typing import Optional

logger = logging.getLogger(__name__)


def run_ocr(
    file_bytes: bytes,
    mime_type: Optional[str],
    file_name: Optional[str],
) -> str:
    """Run OCR on a file. Returns extracted text, or empty string on failure/stub."""
    provider = os.getenv("OCR_PROVIDER", "stub")

    if provider == "stub":
        return ""

    if provider == "gemini":
        return _ocr_gemini(file_bytes, mime_type, file_name)

    logger.warning("Unknown OCR provider: %s", provider)
    return ""


def _ocr_gemini(
    file_bytes: bytes,
    mime_type: Optional[str],
    file_name: Optional[str],
) -> str:
    """Use Gemini Vision to extract text from a scanned PDF resume.

    Renders each PDF page as a PNG image at 2x scale and sends it to
    Gemini Flash for text extraction.
    """
    try:
        import fitz  # PyMuPDF — already in requirements
        import google.generativeai as genai  # google-generativeai

        api_key = os.getenv("GEMINI_API_KEY")
        if not api_key:
            logger.warning("GEMINI_API_KEY not set — OCR unavailable")
            return ""

        genai.configure(api_key=api_key)
        model = genai.GenerativeModel("gemini-2.0-flash")

        pages_text: list[str] = []

        with fitz.open(stream=file_bytes, filetype="pdf") as doc:
            for page in doc:
                # Render at 2x resolution for better OCR quality
                mat = fitz.Matrix(2, 2)
                pix = page.get_pixmap(matrix=mat)
                img_bytes = pix.tobytes("png")
                img_b64 = base64.b64encode(img_bytes).decode()

                response = model.generate_content(
                    [
                        {
                            "inline_data": {
                                "mime_type": "image/png",
                                "data": img_b64,
                            }
                        },
                        (
                            "Extract all text from this resume page. "
                            "Return only the raw text, preserve line structure, "
                            "no commentary or formatting instructions."
                        ),
                    ]
                )

                if response.text:
                    pages_text.append(response.text.strip())

        return "\n\n".join(pages_text)

    except Exception as exc:  # noqa: BLE001
        logger.warning("Gemini OCR failed: %s", exc)
        return ""
