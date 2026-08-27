"""SOFExtractor boundary — the Extraction Layer / Facts Layer seam
(SYSTEM_ARCHITECTURE.md sections 1.1, 5). Every extractor implementation, deterministic
or AI-backed, produces ExtractedEventCandidate — never a confirmed SOFEvent. Only a
human action (the SOF Events review table, brief section 9) can create a CONFIRMED
domain SOFEvent that the Calculation Engine will use.
"""
from __future__ import annotations

from dataclasses import dataclass
from datetime import datetime
from typing import Protocol


@dataclass
class ExtractedEventCandidate:
    category: str
    subtype: str | None
    start_time: datetime | None
    source_text: str
    page_number: int
    confidence_score: float
    confidence_status: str = "NEEDS_REVIEW"


class SOFExtractor(Protocol):
    def extract(self, pages: list[str], *, reference_year: int) -> list[ExtractedEventCandidate]: ...
