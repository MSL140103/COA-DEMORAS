"""Test 30 (brief section 78): calculation reproducibility — same inputs must always
produce the same output. Also exercises the full pipeline end-to-end as an
integration-of-domain-modules smoke test."""
from datetime import datetime, timedelta
from decimal import Decimal

import pytest

from app.domain.calculation.pipeline import CalculationBlocked, run_calculation
from app.domain.rules.seed import base_rule_set
from tests.unit.conftest import make_event


def _voyage_events():
    return [
        make_event("NOR_TENDERED", datetime(2026, 5, 28, 2, 6)),
        make_event("SECURELY_MOORED", datetime(2026, 5, 28, 11, 42)),
        make_event("COMMENCED_LOADING", datetime(2026, 5, 28, 11, 42), datetime(2026, 5, 29, 6, 0)),
        make_event("WEATHER", datetime(2026, 5, 28, 20, 0), datetime(2026, 5, 29, 0, 0)),
    ]


def test_reproducibility_same_inputs_same_outputs():
    rule_set = base_rule_set()
    run1 = run_calculation(
        events=_voyage_events(),
        rule_set=rule_set,
        allowed_laytime=timedelta(hours=36),
        demurrage_daily_rate=Decimal("50000"),
    )
    run2 = run_calculation(
        events=_voyage_events(),
        rule_set=rule_set,
        allowed_laytime=timedelta(hours=36),
        demurrage_daily_rate=Decimal("50000"),
    )
    assert run1.commencement.selected == run2.commencement.selected
    assert run1.laytime.used_laytime == run2.laytime.used_laytime
    assert run1.laytime.demurrage_commencement == run2.laytime.demurrage_commencement
    assert run1.demurrage.amount == run2.demurrage.amount
    assert [i.decision_reason for i in run1.intervals] == [i.decision_reason for i in run2.intervals]


def test_pipeline_commencement_is_nor_plus_6():
    rule_set = base_rule_set()
    run = run_calculation(
        events=_voyage_events(),
        rule_set=rule_set,
        allowed_laytime=timedelta(hours=36),
        demurrage_daily_rate=Decimal("50000"),
    )
    assert run.commencement.selected == datetime(2026, 5, 28, 8, 6)  # NOR + 6, earlier than moored 11:42
    assert run.integrity.ok


def test_pipeline_weather_reduces_counted_time():
    rule_set = base_rule_set()
    events_with_weather = _voyage_events()
    events_without_weather = [e for e in _voyage_events() if e.category != "WEATHER"]

    with_weather = run_calculation(
        events=events_with_weather,
        rule_set=rule_set,
        allowed_laytime=timedelta(hours=100),
        demurrage_daily_rate=Decimal("50000"),
    )
    without_weather = run_calculation(
        events=events_without_weather,
        rule_set=rule_set,
        allowed_laytime=timedelta(hours=100),
        demurrage_daily_rate=Decimal("50000"),
    )
    assert with_weather.laytime.used_laytime < without_weather.laytime.used_laytime


def test_no_confirmed_events_raises():
    with pytest.raises(ValueError):
        run_calculation(
            events=[],
            rule_set=base_rule_set(),
            allowed_laytime=timedelta(hours=36),
            demurrage_daily_rate=Decimal("50000"),
        )
