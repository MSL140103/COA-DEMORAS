"""Native text extraction — SYSTEM_ARCHITECTURE.md section 4: try native text first,
OCR only when needed. This module is the "native text first" half; OCR is not yet
wired in for MVP1 (a scanned-image SOF will simply extract empty/near-empty pages,
which the heuristic extractor will correctly turn into zero candidates rather than
guessing)."""
from __future__ import annotations

import pdfplumber


def extract_native_text(path: str) -> list[str]:
    """Returns one string per page, in order. Never raises on a page with no
    extractable text — returns "" for that page instead."""
    pages: list[str] = []
    with pdfplumber.open(path) as pdf:
        for page in pdf.pages:
            pages.append(page.extract_text() or "")
    return pages
