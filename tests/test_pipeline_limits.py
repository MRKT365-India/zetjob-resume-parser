import asyncio
import base64

from app.pipeline import run_pipeline


def test_rejects_invalid_base64_payload():
    result = asyncio.run(
        run_pipeline({"fileBase64": "%%%not-base64%%%", "fileName": "resume.pdf", "mimeType": "application/pdf"})
    )
    assert result["error"] == "Invalid base64 payload"


def test_rejects_file_over_5mb():
    oversized = base64.b64encode(b"a" * (5 * 1024 * 1024 + 1)).decode("ascii")
    result = asyncio.run(
        run_pipeline({"fileBase64": oversized, "fileName": "resume.pdf", "mimeType": "application/pdf"})
    )
    assert result["error"] == "File exceeds 5MB limit"
