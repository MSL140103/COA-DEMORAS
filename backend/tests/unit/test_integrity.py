"""Test 23 (brief section 78): integrity check must catch a broken (double-counted
or gapped) timeline, not just trust the engine blindly."""
from datetime import datetime
from decimal import Decimal

from app.domain.timeline.engine import AtomicInterval
from app.domain.timeline.integrity import integrity_check


def _interval(start: datetime, end: datetime) -> AtomicInterval:
    return AtomicInterval(
        interval_start=start,
        interval_end=end,
        active_event_ids=[],
        matched_rule_ids=["X"],
        primary_rule_id="X",
        primary_rule_name="X",
        secondary_rule_ids=[],
        final_time_count_factor=Decimal(1),
        final_demurrage_rate_factor=Decimal(1),
        decision_reason="test",
    )


def test_valid_contiguous_timeline_passes():
    intervals = [
        _interval(datetime(2026, 1, 1, 8), datetime(2026, 1, 1, 9)),
        _interval(datetime(2026, 1, 1, 9), datetime(2026, 1, 1, 10)),
    ]
    result = integrity_check(intervals, datetime(2026, 1, 1, 8), datetime(2026, 1, 1, 10))
    assert result.ok


def test_overlapping_intervals_fail_double_deduction_check():
    intervals = [
        _interval(datetime(2026, 1, 1, 8), datetime(2026, 1, 1, 9, 30)),
        _interval(datetime(2026, 1, 1, 9), datetime(2026, 1, 1, 10)),  # overlaps previous
    ]
    result = integrity_check(intervals, datetime(2026, 1, 1, 8), datetime(2026, 1, 1, 10))
    assert not result.ok
    assert "DOUBLE DEDUCTION" in result.error


def test_gap_between_intervals_fails():
    intervals = [
        _interval(datetime(2026, 1, 1, 8), datetime(2026, 1, 1, 9)),
        _interval(datetime(2026, 1, 1, 9, 30), datetime(2026, 1, 1, 10)),  # gap 09:00-09:30
    ]
    result = integrity_check(intervals, datetime(2026, 1, 1, 8), datetime(2026, 1, 1, 10))
    assert not result.ok


def test_empty_timeline_over_zero_length_range_is_ok():
    result = integrity_check([], datetime(2026, 1, 1, 8), datetime(2026, 1, 1, 8))
    assert result.ok
