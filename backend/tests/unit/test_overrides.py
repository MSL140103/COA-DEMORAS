"""Test 18/25 (brief section 78): Manual Override — RULE 9, never silently overwrite
the original suggestion."""
from datetime import datetime
from decimal import Decimal

from app.domain.calculation.overrides import ManualOverride, apply_overrides, interval_key
from app.domain.timeline.engine import AtomicInterval


def _interval(start, end) -> AtomicInterval:
    return AtomicInterval(
        interval_start=start,
        interval_end=end,
        active_event_ids=["EV1"],
        matched_rule_ids=["SEED_WEATHER_WINDOW_V1"],
        primary_rule_id="SEED_WEATHER_WINDOW_V1",
        primary_rule_name="Weather — 50% Count",
        secondary_rule_ids=[],
        final_time_count_factor=Decimal("0.5"),
        final_demurrage_rate_factor=Decimal("0.5"),
        decision_reason='"Weather — 50% Count" applied — time counts at 50%.',
    )


def test_override_changes_factor_and_preserves_original_reason():
    interval = _interval(datetime(2026, 1, 1, 8), datetime(2026, 1, 1, 10))
    override = ManualOverride(
        id="OV1",
        target_key=interval_key(interval),
        new_time_count_factor=Decimal(1),
        new_demurrage_rate_factor=Decimal(1),
        reason="Weather did not actually delay cargo operations — vessel worked through it",
        created_by="operator@sw.com",
        created_at=datetime(2026, 1, 1, 12, 0),
    )
    result = apply_overrides([interval], [override])
    assert len(result) == 1
    updated = result[0]
    assert updated.final_time_count_factor == Decimal(1)
    assert "MANUAL OVERRIDE by operator@sw.com" in updated.decision_reason
    assert "Weather — 50% Count" in updated.decision_reason  # original suggestion retained


def test_no_override_leaves_interval_untouched():
    interval = _interval(datetime(2026, 1, 1, 8), datetime(2026, 1, 1, 10))
    result = apply_overrides([interval], [])
    assert result[0] == interval


def test_superseded_override_is_ignored():
    interval = _interval(datetime(2026, 1, 1, 8), datetime(2026, 1, 1, 10))
    old = ManualOverride(
        id="OV1",
        target_key=interval_key(interval),
        new_time_count_factor=Decimal(1),
        new_demurrage_rate_factor=Decimal(1),
        reason="first guess",
        created_by="a@sw.com",
        created_at=datetime(2026, 1, 1, 9, 0),
        superseded_by="OV2",
    )
    result = apply_overrides([interval], [old])
    assert result[0].final_time_count_factor == Decimal("0.5")  # untouched — superseded override ignored
