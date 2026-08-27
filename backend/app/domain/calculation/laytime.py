"""Laytime Calculation Engine — SYSTEM_ARCHITECTURE.md section 9.

Purely arithmetic over an already-resolved list of AtomicInterval. This module never
evaluates a rule condition — that already happened in the Timeline Engine. RULE 8
(the LLM/engine boundary) is enforced by this module having zero AI/network
dependency: it is 100% deterministic given its inputs and is fully unit-testable.
"""
from __future__ import annotations

from dataclasses import dataclass
from datetime import datetime, timedelta
from decimal import Decimal

from app.domain.timeline.engine import AtomicInterval


@dataclass
class LaytimeResult:
    gross_elapsed: timedelta
    used_laytime: timedelta
    remaining_laytime: timedelta
    excess_time: timedelta
    demurrage_commencement: datetime | None
    cumulative_seconds_at_end: dict[str, Decimal]  # interval key "start|end" -> cumulative counted seconds


def _interval_key(interval: AtomicInterval) -> str:
    return f"{interval.interval_start.isoformat()}|{interval.interval_end.isoformat()}"


def calculate_laytime(
    intervals: list[AtomicInterval],
    commencement: datetime,
    allowed_laytime: timedelta,
) -> LaytimeResult:
    ordered = sorted(intervals, key=lambda i: i.interval_start)
    allowed_seconds = Decimal(allowed_laytime.total_seconds())

    cumulative = Decimal(0)
    demurrage_commencement: datetime | None = None
    cumulative_map: dict[str, Decimal] = {}

    for interval in ordered:
        if interval.interval_end <= commencement:
            cumulative_map[_interval_key(interval)] = cumulative
            continue

        eff_start = max(interval.interval_start, commencement)
        elapsed_seconds = Decimal((interval.interval_end - eff_start).total_seconds())
        counted = elapsed_seconds * interval.final_time_count_factor

        prev_cumulative = cumulative
        cumulative += counted
        cumulative_map[_interval_key(interval)] = cumulative

        if demurrage_commencement is None and cumulative >= allowed_seconds:
            remaining_needed = allowed_seconds - prev_cumulative
            if interval.final_time_count_factor > 0:
                seconds_needed = remaining_needed / interval.final_time_count_factor
                demurrage_commencement = eff_start + timedelta(seconds=float(seconds_needed))
            else:
                # A zero-factor interval cannot itself cross the threshold (it adds
                # no counted time), so this branch is unreachable in practice; kept
                # as an explicit, safe fallback rather than a silent assumption.
                demurrage_commencement = interval.interval_end

    used = min(cumulative, allowed_seconds)
    remaining = max(allowed_seconds - cumulative, Decimal(0))
    excess = max(cumulative - allowed_seconds, Decimal(0))
    gross_elapsed = ordered[-1].interval_end - ordered[0].interval_start if ordered else timedelta(0)

    return LaytimeResult(
        gross_elapsed=gross_elapsed,
        used_laytime=timedelta(seconds=float(used)),
        remaining_laytime=timedelta(seconds=float(remaining)),
        excess_time=timedelta(seconds=float(excess)),
        demurrage_commencement=demurrage_commencement,
        cumulative_seconds_at_end=cumulative_map,
    )
