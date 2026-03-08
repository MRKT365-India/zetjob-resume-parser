"""Tests for app/av.py — filetype antivirus validation."""
import pytest
from app.av import scan_file, MAX_FILE_SIZE

# Magic byte fixtures
PDF_BYTES = b"%PDF-1.4 fake pdf content for testing" + b"x" * 100
DOCX_BYTES = b"PK\x03\x04" + b"\x00" * 100
DOC_BYTES = b"\xd0\xcf\x11\xe0" + b"\x00" * 100
GARBAGE_BYTES = b"\xff\xfe\xfd\xfc" + b"not a real file" * 10


# --- filetype provider ---

def test_clean_pdf(monkeypatch):
    monkeypatch.setenv("AV_PROVIDER", "filetype")
    result = scan_file(PDF_BYTES, "application/pdf", "resume.pdf")
    assert result["verdict"] == "clean"
    assert result["reason"] is None


def test_clean_docx(monkeypatch):
    monkeypatch.setenv("AV_PROVIDER", "filetype")
    result = scan_file(
        DOCX_BYTES,
        "application/vnd.openxmlformats-officedocument.wordprocessingml.document",
        "resume.docx",
    )
    assert result["verdict"] == "clean"


def test_clean_pdf_no_mime(monkeypatch):
    """No MIME type provided — should still pass if magic bytes are valid."""
    monkeypatch.setenv("AV_PROVIDER", "filetype")
    result = scan_file(PDF_BYTES, None, "resume.pdf")
    assert result["verdict"] == "clean"


def test_blocked_oversized(monkeypatch):
    monkeypatch.setenv("AV_PROVIDER", "filetype")
    big_file = b"%PDF" + b"\x00" * (MAX_FILE_SIZE + 1)
    result = scan_file(big_file, "application/pdf", "big.pdf")
    assert result["verdict"] == "blocked"
    assert "too large" in result["reason"].lower()


def test_blocked_empty(monkeypatch):
    monkeypatch.setenv("AV_PROVIDER", "filetype")
    result = scan_file(b"", None, "empty.pdf")
    assert result["verdict"] == "blocked"


def test_blocked_unknown_magic(monkeypatch):
    monkeypatch.setenv("AV_PROVIDER", "filetype")
    result = scan_file(GARBAGE_BYTES, "application/pdf", "evil.pdf")
    assert result["verdict"] == "blocked"
    assert "magic bytes" in result["reason"].lower()


def test_blocked_extension_mismatch_pdf(monkeypatch):
    """File claims to be PDF by name but has DOCX magic bytes."""
    monkeypatch.setenv("AV_PROVIDER", "filetype")
    result = scan_file(DOCX_BYTES, "application/pdf", "fake.pdf")
    assert result["verdict"] == "blocked"
    assert "extension" in result["reason"].lower() or "not a pdf" in result["reason"].lower()


def test_blocked_extension_mismatch_docx(monkeypatch):
    """File claims to be DOCX by name but has PDF magic bytes."""
    monkeypatch.setenv("AV_PROVIDER", "filetype")
    result = scan_file(PDF_BYTES, None, "fake.docx")
    assert result["verdict"] == "blocked"


def test_blocked_disallowed_mime(monkeypatch):
    """MIME type that isn't in the allowed set."""
    monkeypatch.setenv("AV_PROVIDER", "filetype")
    result = scan_file(PDF_BYTES, "text/html", "resume.pdf")
    assert result["verdict"] == "blocked"
    assert "mime type" in result["reason"].lower()


# --- stub provider ---

def test_stub_returns_pending(monkeypatch):
    monkeypatch.setenv("AV_PROVIDER", "stub")
    result = scan_file(GARBAGE_BYTES, None, "anything.pdf")
    assert result["verdict"] == "pending"
    assert "stub" in result["reason"].lower()


# --- unknown provider ---

def test_unknown_provider_returns_error(monkeypatch):
    monkeypatch.setenv("AV_PROVIDER", "virustotal")
    result = scan_file(PDF_BYTES, None, "resume.pdf")
    assert result["verdict"] == "error"
