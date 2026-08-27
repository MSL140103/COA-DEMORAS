"""Demurrage Calculation Engine — SYSTEM_ARCHITECTURE.md section 10.

Splits on-demurrage time into full/half/other rate buckets using
AtomicInterval.final_demurrage_rate_factor — a field kept deliberately separate from
final_time_count_factor throughout the domain model, because a Shellvoy 15(2)-style
clause can require time to count at one factor while the *rate* applicable to that
time (once on demurrage) differs (brief section 24).

CONTRACTUAL DECISION REQUIRED (SYSTEM_ARCHITECTURE.md section 29 item 4): pro-rata
rounding for "running day or part thereof" is not specified by the brief. This
implementation uses an exact fractional-day calculation (no rounding up to a coarser
unit) as the documented default — confirm against real SW/RT practice before
approving any real amount.
"""
from __future__ import annotations

from dataclasses import dataclass
from datetime import datetime, timedelta
from decimal import ROUND_HALF_UP, Decimal

from app.domain.timeline.engine import AtomicInterval

SECONDS_PER_DAY = Decimal(86400)


@dataclass
class DemurrageResult:
    full_rate_time: timedelta
    half_rate_time: timedelta
    other_rate_time: timedelta
    daily_rate: Decimal
    amount: Decimal


def calculate_demurrage(
    intervals: list[AtomicInterval],
    demurrage_commencement: datetime | None,
    daily_rate: Decimal,
) -> DemurrageResult:
    if demurrage_commencement is None:
        return DemurrageResult(
            full_rate_time=timedelta(0),
            half_rate_time=timedelta(0),
            other_rate_time=timedelta(0),
            daily_rate=daily_rate,
            amount=Decimal("0.00"),
        )

    full_seconds = Decimal(0)
    half_seconds = Decimal(0)
    other_seconds = Decimal(0)
    other_weighted_seconds = Decimal(0)

    for interval in sorted(intervals, key=lambda i: i.interval_start):
        if interval.interval_end <= demurrage_commencement:
            continue
        eff_start = max(interval.interval_start, demurrage_commencement)
        elapsed = Decimal((interval.interval_end - eff_start).total_seconds())
        factor = interval.final_demurrage_rate_factor

        if factor == 1:
            full_seconds += elapsed
        elif factor == Decimal("0.5"):
            half_seconds += elapsed
        else:
            other_seconds += elapsed
            other_weighted_seconds += elapsed * factor

    amount = (
        (full_seconds / SECONDS_PER_DAY) * daily_rate
        + (half_seconds / SECONDS_PER_DAY) * daily_rate * Decimal("0.5")
        + (other_weighted_seconds / SECONDS_PER_DAY) * daily_rate
    ).quantize(Decimal("0.01"), rounding=ROUND_HALF_UP)

    return DemurrageResult(
        full_rate_time=timedelta(seconds=float(full_seconds)),
        half_rate_time=timedelta(seconds=float(half_seconds)),
        other_rate_time=timedelta(seconds=float(other_seconds)),
        daily_rate=daily_rate,
        amount=amount,
    )
