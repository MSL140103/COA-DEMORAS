from datetime import datetime, timedelta
from decimal import Decimal

from app.domain.rules.seed import base_rule_set
from app.domain.timeline.engine import build_atomic_timeline, collect_boundaries
from app.domain.timeline.integrity import integrity_check
from tests.unit.conftest import make_event


def test_case_21_shifting_weather_overlap_no_double_deduction():
    """Test 21/23/36 (brief sections 36, 78): the canonical example.

        Shifting  10:00-12:00 (0%)
        Weather   11:00-13:00 (50%)

    Expected atomic intervals:
        10:00-11:00  Shifting only        -> 0%
        11:00-12:00  Shifting + Weather   -> 0% (Shifting wins, Weather is secondary,
                                                   NO extra deduction for the same period)
        12:00-13:00  Weather only         -> 50%
    """
    rule_set = base_rule_set()
    shifting = make_event("SHIFTING", datetime(2026, 1, 1, 10, 0), datetime(2026, 1, 1, 12, 0))
    weather = make_event("WEATHER", datetime(2026, 1, 1, 11, 0), datetime(2026, 1, 1, 13, 0))

    intervals = build_atomic_timeline(
        [shifting, weather], rule_set, datetime(2026, 1, 1, 10, 0), datetime(2026, 1, 1, 13, 0)
    )

    assert len(intervals) == 3
    a, b, c = intervals

    assert (a.interval_start, a.interval_end) == (datetime(2026, 1, 1, 10, 0), datetime(2026, 1, 1, 11, 0))
    assert a.final_time_count_factor == Decimal(0)
    assert a.primary_rule_name == "Shifting — Excluded"
    assert a.secondary_rule_ids == []

    assert (b.interval_start, b.interval_end) == (datetime(2026, 1, 1, 11, 0), datetime(2026, 1, 1, 12, 0))
    assert b.final_time_count_factor == Decimal(0)
    assert b.primary_rule_name == "Shifting — Excluded"
    assert len(b.secondary_rule_ids) == 1  # Weather matched but is secondary
    assert "NO DOUBLE DEDUCTION" in b.decision_reason

    assert (c.interval_start, c.interval_end) == (datetime(2026, 1, 1, 12, 0), datetime(2026, 1, 1, 13, 0))
    assert c.final_time_count_factor == Decimal("0.5")
    assert c.primary_rule_name == "Weather — 50% Count"

    # The whole gross timeline must be accounted for exactly once (RULE 2).
    result = integrity_check(intervals, datetime(2026, 1, 1, 10, 0), datetime(2026, 1, 1, 13, 0))
    assert result.ok, result.detail


def test_case_22_triple_overlap_shifting_weather_and_default():
    """Test 22: shifting + weather + an unrelated third event concurrently — the
    third event must show up as an additional secondary event, still zero extra
    deduction."""
    rule_set = base_rule_set()
    shifting = make_event("SHIFTING", datetime(2026, 1, 1, 10, 0), datetime(2026, 1, 1, 12, 0))
    weather = make_event("WEATHER", datetime(2026, 1, 1, 11, 0), datetime(2026, 1, 1, 13, 0))
    bunkering = make_event("BUNKERING", datetime(2026, 1, 1, 11, 30), datetime(2026, 1, 1, 14, 0))

    intervals = build_atomic_timeline(
        [shifting, weather, bunkering],
        rule_set,
        datetime(2026, 1, 1, 10, 0),
        datetime(2026, 1, 1, 14, 0),
    )
    triple = next(i for i in intervals if i.interval_start == datetime(2026, 1, 1, 11, 30))
    assert triple.interval_end == datetime(2026, 1, 1, 12, 0)
    assert triple.final_time_count_factor == Decimal(0)
    assert triple.primary_rule_name == "Shifting — Excluded"
    # Weather matched (secondary); bunkering has no matching rule in the seed set so it
    # simply doesn't appear as a matched rule — it's still visible via active_event_ids.
    assert len(triple.active_event_ids) == 3


def test_default_count_when_no_rule_matches():
    rule_set = base_rule_set()
    ordinary = make_event("COMMENCED_LOADING", datetime(2026, 1, 1, 8, 0), datetime(2026, 1, 1, 12, 0))
    intervals = build_atomic_timeline(
        [ordinary], rule_set, datetime(2026, 1, 1, 8, 0), datetime(2026, 1, 1, 12, 0)
    )
    assert len(intervals) == 1
    assert intervals[0].final_time_count_factor == Decimal(1)
    assert intervals[0].primary_rule_id == "SYSTEM_DEFAULT_COUNT_V1"


def test_collect_boundaries_clips_to_gross_range_and_dedupes():
    e1 = make_event("WEATHER", datetime(2026, 1, 1, 9, 0), datetime(2026, 1, 1, 11, 0))
    e2 = make_event("WEATHER", datetime(2026, 1, 1, 11, 0), datetime(2026, 1, 1, 15, 0))  # end outside range
    boundaries = collect_boundaries([e1, e2], datetime(2026, 1, 1, 8, 0), datetime(2026, 1, 1, 12, 0))
    assert boundaries == [
        datetime(2026, 1, 1, 8, 0),
        datetime(2026, 1, 1, 9, 0),
        datetime(2026, 1, 1, 11, 0),
        datetime(2026, 1, 1, 12, 0),
    ]


def test_instantaneous_events_are_boundaries_not_active_intervals():
    marker = make_event("NOR_TENDERED", datetime(2026, 1, 1, 9, 0))  # no end_time
    span = make_event("COMMENCED_LOADING", datetime(2026, 1, 1, 8, 0), datetime(2026, 1, 1, 12, 0))
    rule_set = base_rule_set()
    intervals = build_atomic_timeline(
        [marker, span], rule_set, datetime(2026, 1, 1, 8, 0), datetime(2026, 1, 1, 12, 0)
    )
    # The marker splits the timeline into two intervals but is never itself "active".
    assert len(intervals) == 2
    assert all("NOR_TENDERED" not in i.active_event_ids for i in intervals)
