"""Facts layer — what happened, per the SOF. No treatment/percentage lives here.

RULE 5 (facts and rules must remain separate) is enforced structurally: this module
has no field for "count %" or "treatment". That only ever appears on
app.domain.timeline.engine.AtomicInterval, derived from a RuleVersion.
"""
from __future__ import annotations

from datetime import datetime
from enum import Enum
from typing import Optional

from pydantic import BaseModel, ConfigDict, model_validator


class ConfidenceStatus(str, Enum):
    CONFIRMED = "CONFIRMED"
    PROBABLE = "PROBABLE"
    UNKNOWN = "UNKNOWN"
    CONFLICTING_INFORMATION = "CONFLICTING_INFORMATION"
    NEEDS_REVIEW = "NEEDS_REVIEW"


class SOFEventStatus(str, Enum):
    EXTRACTED = "EXTRACTED"
    EDITED = "EDITED"
    CONFIRMED = "CONFIRMED"
    REJECTED = "REJECTED"
    SPLIT = "SPLIT"
    MERGED = "MERGED"


# Closed catalogue per SYSTEM_ARCHITECTURE.md section 8 / brief section 8.
# Extraction must map to one of these or fall back to OTHER + subtype — never invent
# a new category value silently (it would silently stop matching Rule conditions).
EVENT_CATEGORIES: set[str] = {
    "ARRIVAL", "ARRIVAL_ANCHORAGE", "NOR_TENDERED", "NOR_ACCEPTED", "ANCHOR_DROPPED",
    "ANCHOR_AWEIGH", "PILOT_ON_BOARD", "COMMENCED_INWARD_PASSAGE", "TUG_OPERATIONS",
    "ALL_FAST", "SECURELY_MOORED", "GANGWAY_IN_PLACE", "AUTHORITIES_ON_BOARD",
    "AUTHORITIES_DISEMBARKED", "FREE_PRATIQUE", "HOSE_CONNECTION", "COMMENCED_LOADING",
    "COMMENCED_DISCHARGING", "CARGO_STOPPED", "CARGO_RESUMED", "COMPLETED_LOADING",
    "COMPLETED_DISCHARGING", "HOSES_DISCONNECTED", "BUNKERING", "BALLASTING",
    "DEBALLASTING", "SLOPS", "TANK_WASHING", "SHIP_LINING_UP", "DRAINING_PUMPS_PIPELINES",
    "LINE_FLUSHING", "SHIFTING", "UNBERTHING", "REBERTHING", "WEATHER", "PORT_CLOSURE",
    "WAITING_BERTH", "BERTH_UNAVAILABLE", "WAITING_CARGO", "AWAITING_CARGO_DOCUMENTS",
    "WAITING_INSTRUCTIONS", "VESSEL_BREAKDOWN", "SHORE_EQUIPMENT_BREAKDOWN", "STRIKE",
    "CHARTERERS_DELAY", "DEPARTURE", "OTHER",
}


class SOFEvent(BaseModel):
    """A single fact extracted from (or entered against) a Statement of Facts."""

    model_config = ConfigDict(validate_assignment=True)

    id: str
    port_call_id: str
    category: str
    subtype: Optional[str] = None
    start_time: datetime
    end_time: Optional[datetime] = None
    source_text: Optional[str] = None
    document_id: Optional[str] = None
    page_number: Optional[int] = None
    confidence_score: Optional[float] = None
    confidence_status: ConfidenceStatus = ConfidenceStatus.NEEDS_REVIEW
    status: SOFEventStatus = SOFEventStatus.EXTRACTED
    parent_event_id: Optional[str] = None
    comment: Optional[str] = None

    @model_validator(mode="after")
    def _check_range(self) -> "SOFEvent":
        if self.end_time is not None and self.end_time < self.start_time:
            raise ValueError(f"SOFEvent {self.id}: end_time before start_time")
        return self

    @property
    def effective_end(self) -> datetime:
        return self.end_time if self.end_time is not None else self.start_time

    @property
    def is_instantaneous(self) -> bool:
        return self.end_time is None or self.end_time == self.start_time

    def overlaps(self, start: datetime, end: datetime) -> bool:
        """Whether this event occupies any part of [start, end).

        Instantaneous markers (e.g. "NOR Tendered") never occupy a range — they are
        used as timeline *boundaries*, not as "active events" inside an interval.
        """
        if self.is_instantaneous:
            return False
        return self.start_time < end and self.effective_end > start


class EventEvidence(BaseModel):
    """Append-only correction history for a SOFEvent (brief section 9)."""

    id: str
    sof_event_id: str
    field_changed: str
    previous_value: Optional[str] = None
    new_value: Optional[str] = None
    changed_by: str
    changed_at: datetime
    reason: Optional[str] = None
    document_id: Optional[str] = None
    page_number: Optional[int] = None
