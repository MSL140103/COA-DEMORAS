"""Test 20 (brief section 78): full -> half rate demurrage, and independence of
final_time_count_factor from final_demurrage_rate_factor (brief section 24 /
Shellvoy 15(2))."""
from datetime import datetime
from decimal import Decimal

from app.domain.calculation.demurrage import calculate_demurrage
from app.domain.timeline.engine import AtomicInterval


def _interval(start, end, rate_factor) -> AtomicInterval:
    return AtomicInterval(
        interval_start=start,
        interval_end=end,
        active_event_ids=[],
        matched_rule_ids=["X"],
        primary_rule_id="X",
        primary_rule_name="X",
        secondary_rule_ids=[],
        final_time_count_factor=Decimal(1),  # counts 100% toward laytime either way
        final_demurrage_rate_factor=Decimal(rate_factor),
        decision_reason="test",
    )


def test_full_then_half_rate_demurrage_amount():
    commencement = datetime(2026, 1, 1, 0, 0)
    intervals = [
        _interval(datetime(2026, 1, 1, 0, 0), datetime(2026, 1, 2, 0, 0), "1"),  # 1 full day
        _interval(datetime(2026, 1, 2, 0, 0), datetime(2026, 1, 3, 0, 0), "0.5"),  # 1 day @ half rate
    ]
    result = calculate_demurrage(intervals, commencement, daily_rate=Decimal("50000"))
    assert result.full_rate_time.days == 1
    assert result.half_rate_time.days == 1
    # 1 day full (50000) + 1 day half (25000) = 75000.00
    assert result.amount == Decimal("75000.00")


def test_no_demurrage_before_commencement():
    result = calculate_demurrage([], None, daily_rate=Decimal("50000"))
    assert result.amount == Decimal("0.00")


def test_time_before_demurrage_commencement_excluded():
    commencement = datetime(2026, 1, 2, 0, 0)
    intervals = [_interval(datetime(2026, 1, 1, 0, 0), datetime(2026, 1, 2, 0, 0), "1")]  # entirely before
    result = calculate_demurrage(intervals, commencement, daily_rate=Decimal("50000"))
    assert result.amount == Decimal("0.00")


def test_pro_rata_partial_day():
    commencement = datetime(2026, 1, 1, 0, 0)
    intervals = [_interval(datetime(2026, 1, 1, 0, 0), datetime(2026, 1, 1, 12, 0), "1")]  # half a day
    result = calculate_demurrage(intervals, commencement, daily_rate=Decimal("48000"))
    assert result.amount == Decimal("24000.00")
