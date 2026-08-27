"""Deterministic, regex/keyword-based SOF extractor — the MVP1 default.

This is NOT the long-term extraction strategy (SYSTEM_ARCHITECTURE.md section 5
specifies an LLM-based structured extractor as the real target); it exists so the
upload -> extract -> human review pipeline is genuinely usable end-to-end without
requiring an AI provider API key to be configured. It intentionally never claims high
confidence (every candidate is confidence_status=NEEDS_REVIEW) — the human review
table is not optional, here even more than for an AI extractor.

Swap this for an LLM-backed implementation of SOFExtractor (interface.py) by pointing
the Document router at a different extractor instance — nothing else changes,
because both live behind the same Protocol.
"""
from __future__ import annotations

import re

from dateutil import parser as dateutil_parser

from app.extraction.sof_extraction.interface import ExtractedEventCandidate
from app.extraction.sof_extraction.synonyms import EVENT_KEYWORDS

_DATETIME_RE = re.compile(
    r"(?P<d1>\d{1,2}[/.\-]\d{1,2}(?:[/.\-]\d{2,4})?)\s+(?:at\s+)?(?P<t1>\d{1,2}[:.]\d{2})"
    r"|(?P<t2>\d{1,2}[:.]\d{2})\s*(?:hrs?\.?)?\s+(?:on\s+)?(?P<d2>\d{1,2}[/.\-]\d{1,2}(?:[/.\-]\d{2,4})?)"
)


def _match_category(upper_line: str) -> tuple[str, str] | None:
    for pattern, category in EVENT_KEYWORDS:
        m = pattern.search(upper_line)
        if m:
            return category, m.group(0)
    return None


def _extract_datetime(line: str, reference_year: int):
    m = _DATETIME_RE.search(line)
    if not m:
        return None
    date_text = m.group("d1") or m.group("d2")
    time_text = m.group("t1") or m.group("t2")
    if not date_text or not time_text:
        return None
    try:
        from datetime import datetime as _dt

        return dateutil_parser.parse(
            f"{date_text} {time_text.replace('.', ':')}",
            dayfirst=True,
            default=_dt(reference_year, 1, 1),
        )
    except (ValueError, OverflowError):
        return None


def extract_candidates(pages: list[str], *, reference_year: int) -> list[ExtractedEventCandidate]:
    candidates: list[ExtractedEventCandidate] = []
    for page_no, text in enumerate(pages, start=1):
        for raw_line in text.splitlines():
            line = raw_line.strip()
            if not line:
                continue
            match = _match_category(line.upper())
            if match is None:
                continue
            category, matched_keyword = match
            start_time = _extract_datetime(line, reference_year)
            if start_time is None:
                # A category keyword with no parseable timestamp is exactly the
                # "extract only what you can cite" boundary (brief section 5) — skip
                # rather than guess a time.
                continue
            candidates.append(
                ExtractedEventCandidate(
                    category=category,
                    subtype=matched_keyword.title(),
                    start_time=start_time,
                    source_text=line,
                    page_number=page_no,
                    confidence_score=0.55,
                    confidence_status="NEEDS_REVIEW",
                )
            )
    return candidates


class HeuristicSOFExtractor:
    def extract(self, pages: list[str], *, reference_year: int) -> list[ExtractedEventCandidate]:
        return extract_candidates(pages, reference_year=reference_year)
