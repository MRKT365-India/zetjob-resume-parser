"""
Antivirus / file validation module.

Providers:
- filetype: magic bytes + size + MIME type validation (MVP, no external service)
- stub: no-op (legacy / test mode)
"""
import logging
import os
from typing import Optional

logger = logging.getLogger(__name__)

MAX_FILE_SIZE = 10 * 1024 * 1024  # 10 MB

MAGIC_BYTES: dict[str, bytes] = {
    "pdf": b"%PDF",
    "docx": b"PK\x03\x04",
    "doc": b"\xd0\xcf\x11\xe0",
}

ALLOWED_MIME_TYPES = {
    "application/pdf",
    "application/vnd.openxmlformats-officedocument.wordprocessingml.document",
    "application/msword",
    "application/octet-stream",
}


def scan_file(
    file_bytes: bytes,
    mime_type: Optional[str],
    file_name: Optional[str],
) -> dict:
    """Scan a file for security issues.

    Returns:
        dict with keys:
            verdict: "clean" | "blocked" | "pending" | "error"
            reason: str | None
    """
    provider = os.getenv("AV_PROVIDER", "stub")

    if provider == "stub":
        return {"verdict": "pending", "reason": "stub - not implemented"}

    if provider == "filetype":
        return _scan_filetype(file_bytes, mime_type, file_name)

    logger.warning("Unknown AV provider: %s", provider)
    return {"verdict": "error", "reason": f"Unknown AV provider: {provider}"}


def _scan_filetype(
    file_bytes: bytes,
    mime_type: Optional[str],
    file_name: Optional[str],
) -> dict:
    """Validate file via magic bytes, size, and MIME type."""

    # Empty file
    if not file_bytes:
        return {"verdict": "blocked", "reason": "Empty file"}

    # Size check
    if len(file_bytes) > MAX_FILE_SIZE:
        return {
            "verdict": "blocked",
            "reason": f"File too large: {len(file_bytes):,} bytes (max {MAX_FILE_SIZE:,})",
        }

    # Magic bytes — detect actual file type
    detected_type: Optional[str] = None
    for file_type, magic in MAGIC_BYTES.items():
        if file_bytes[: len(magic)] == magic:
            detected_type = file_type
            break

    if detected_type is None:
        return {
            "verdict": "blocked",
            "reason": "Unrecognised file type (magic bytes check failed)",
        }

    # Extension vs magic bytes consistency
    lower_name = (file_name or "").lower()
    if lower_name.endswith(".pdf") and detected_type != "pdf":
        return {
            "verdict": "blocked",
            "reason": "File extension says PDF but content is not a PDF",
        }
    if lower_name.endswith(".docx") and detected_type != "docx":
        return {
            "verdict": "blocked",
            "reason": "File extension says DOCX but content is not a DOCX",
        }
    if lower_name.endswith(".doc") and detected_type not in ("doc", "docx"):
        return {
            "verdict": "blocked",
            "reason": "File extension says DOC but content does not match",
        }

    # MIME type check (only if caller provides it)
    if mime_type and mime_type not in ALLOWED_MIME_TYPES:
        return {
            "verdict": "blocked",
            "reason": f"MIME type not allowed: {mime_type}",
        }

    return {"verdict": "clean", "reason": None}
