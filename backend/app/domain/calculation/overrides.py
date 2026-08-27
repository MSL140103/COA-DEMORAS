"""Manual Override application — SYSTEM_ARCHITECTURE.md section 17.

RULE 9 (human overrides must never be silently overwritten) is honored by never
mutating the engine's original AtomicInterval: an override produces a *new* interval
object whose decision_reason explicitly retains the original system suggestion.
The override records themselves (this module's ManualOverride) are the append-only
audit trail — the caller is responsible for persisting every one ever created, never
just the latest.
"""
from __future__ import annotations

from dataclasses import dataclass
from datetime import datetime
from decimal import Decimal

from app.domain.timeline.engine import AtomicInterval


@dataclass
class ManualOverride:
    id: str
    target_key: str  # f"{interval_start.isoformat()}|{interval_end.isoformat()}"
    new_time_count_factor: Decimal | None
    new_demurrage_rate_factor: Decimal | None
    reason: str
    created_by: str
    created_at: datetime
    supporting_clause_id: str | None = None
    superseded_by: str | None = None


def interval_key(interval: AtomicInterval) -> str:
    return f"{interval.interval_start.isoformat()}|{interval.interval_end.isoformat()}"


def apply_overrides(intervals: list[AtomicInterval], overrides: list[ManualOverride]) -> list[AtomicInterval]:
    """Apply the *active* (non-superseded) override per interval, if any."""
    active_by_key: dict[str, ManualOverride] = {}
    for override in overrides:
        if override.superseded_by is not None:
            continue
        active_by_key[override.target_key] = override  # last one wins if duplicates slip in

    result: list[AtomicInterval] = []
    for interval in intervals:
        override = active_by_key.get(interval_key(interval))
        if override is None:
            result.append(interval)
            continue

        new_time_factor = (
            override.new_time_count_factor
            if override.new_time_count_factor is not None
            else interval.final_time_count_factor
        )
        new_rate_factor = (
            override.new_demurrage_rate_factor
            if override.new_demurrage_rate_factor is not None
            else interval.final_demurrage_rate_factor
        )
        reason = (
            f'MANUAL OVERRIDE by {override.created_by}: "{override.reason}". '
            f"Original system suggestion — {interval.decision_reason}"
        )
        result.append(
            interval.model_copy(
                update={
                    "final_time_count_factor": new_time_factor,
                    "final_demurrage_rate_factor": new_rate_factor,
                    "decision_reason": reason,
                }
            )
        )
    return result
