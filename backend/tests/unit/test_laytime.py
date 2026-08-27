"""Test 19 (brief section 78): allowed laytime exhausted midway through an interval —
demurrage commencement must be the exact timestamp, not just "somewhere in this
interval"."""
from datetime import datetime, timedelta
from decimal import Decimal

from app.domain.calculation.laytime import calculate_laytime
from app.domain.timeline.engine import AtomicInterval


def _interval(start, end, factor="1") -> AtomicInterval:
    return AtomicInterval(
        interval_start=start,
        interval_end=end,
        active_event_ids=[],
        matched_rule_ids=["X"],
        primary_rule_id="X",
        primary_rule_name="X",
        secondary_rule_ids=[],
        final_time_count_factor=Decimal(factor),
        final_demurrage_rate_factor=Decimal(factor),
        decision_reason="test",
    )


def test_exhaustion_midway_at_full_rate():
    commencement = datetime(2026, 1, 1, 8, 0)
    intervals = [_interval(datetime(2026, 1, 1, 8, 0), datetime(2026, 1, 1, 14, 0))]  # 6h @ 100%
    result = calculate_laytime(intervals, commencement, allowed_laytime=timedelta(hours=5))
    assert result.demurrage_commencement == datetime(2026, 1, 1, 13, 0)
    assert result.used_laytime == timedelta(hours=5)
    assert result.excess_time == timedelta(hours=1)
    assert result.remaining_laytime == timedelta(0)


def test_exhaustion_midway_at_half_rate_interpolates_correctly():
    commencement = datetime(2026, 1, 1, 8, 0)
    # 4 hours @ 50% counted = 2h counted; allowed = 1h -> crosses halfway through, at
    # elapsed 2h into the interval (since 2h * 50% = 1h counted).
    intervals = [_interval(datetime(2026, 1, 1, 8, 0), datetime(2026, 1, 1, 12, 0), factor="0.5")]
    result = calculate_laytime(intervals, commencement, allowed_laytime=timedelta(hours=1))
    assert result.demurrage_commencement == datetime(2026, 1, 1, 10, 0)


def test_no_demurrage_when_laytime_not_exhausted():
    commencement = datetime(2026, 1, 1, 8, 0)
    intervals = [_interval(datetime(2026, 1, 1, 8, 0), datetime(2026, 1, 1, 10, 0))]
    result = calculate_laytime(intervals, commencement, allowed_laytime=timedelta(hours=5))
    assert result.demurrage_commencement is None
    assert result.used_laytime == timedelta(hours=2)
    assert result.remaining_laytime == timedelta(hours=3)


def test_time_before_commencement_never_counts():
    commencement = datetime(2026, 1, 1, 10, 0)
    intervals = [_interval(datetime(2026, 1, 1, 8, 0), datetime(2026, 1, 1, 12, 0))]  # starts before commencement
    result = calculate_laytime(intervals, commencement, allowed_laytime=timedelta(hours=5))
    # Only 08:00-10:00 excluded; 10:00-12:00 (2h) counted.
    assert result.used_laytime == timedelta(hours=2)
