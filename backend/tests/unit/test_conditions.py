from datetime import datetime

from app.domain.rules.conditions import evaluate_condition_tree
from tests.unit.conftest import make_event


def _ctx(events, **extra):
    base = {"events": events, "context": {}, "voyage": {}, "params": {}}
    base.update(extra)
    return base


def test_event_category_eq_matches_any_active_event():
    events = [make_event("WEATHER", datetime(2026, 1, 1, 8), datetime(2026, 1, 1, 10))]
    node = {"field": "event.category", "op": "eq", "value": "WEATHER"}
    assert evaluate_condition_tree(node, _ctx(events)) is True


def test_event_category_eq_false_when_no_events():
    node = {"field": "event.category", "op": "eq", "value": "WEATHER"}
    assert evaluate_condition_tree(node, _ctx([])) is False


def test_all_and_any_and_not():
    events = [make_event("WEATHER", datetime(2026, 1, 1, 8), datetime(2026, 1, 1, 10))]
    ctx = _ctx(events, voyage={"via_sealine": True})
    tree = {
        "all": [
            {"field": "event.category", "op": "eq", "value": "WEATHER"},
            {"field": "voyage.via_sealine", "op": "eq", "value": True},
            {"not": {"field": "voyage.via_sealine", "op": "eq", "value": False}},
        ]
    }
    assert evaluate_condition_tree(tree, ctx) is True


def test_context_field_with_param_reference():
    ctx = _ctx([], context={"hours_since_nor": 40}, params={"weather_window_hours": 48})
    node = {"field": "context.hours_since_nor", "op": "lte", "value": {"param": "weather_window_hours"}}
    assert evaluate_condition_tree(node, ctx) is True

    ctx2 = _ctx([], context={"hours_since_nor": 80}, params={"weather_window_hours": 48})
    assert evaluate_condition_tree(node, ctx2) is False


def test_none_node_is_vacuously_true():
    assert evaluate_condition_tree(None, _ctx([])) is True
