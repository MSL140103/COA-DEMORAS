from decimal import Decimal

import pytest

from app.domain.rules.models import RuleScope, RuleStatus, RuleVersion
from app.domain.rules.precedence import (
    DEFAULT_COUNT_RULE,
    RuleConflictDetected,
    RuleMatch,
    resolve_precedence,
)


def _rule(**overrides) -> RuleVersion:
    base = dict(
        id="R1",
        rule_definition_code="TEST",
        name="Test rule",
        conditions={"field": "event.category", "op": "eq", "value": "WEATHER"},
        time_count_factor=Decimal("0.5"),
        demurrage_rate_factor=Decimal("0.5"),
        priority=0,
        scope=RuleScope.MANUAL,
        source_note="test rule",
        status=RuleStatus.ACTIVE,
    )
    base.update(overrides)
    return RuleVersion(**base)


def test_no_matches_falls_back_to_default_count():
    primary, secondary = resolve_precedence([])
    assert primary.rule.id == DEFAULT_COUNT_RULE.id
    assert primary.rule.time_count_factor == Decimal(1)
    assert secondary == []


def test_single_match_is_primary_with_no_secondary():
    match = RuleMatch(rule=_rule(id="ONLY"))
    primary, secondary = resolve_precedence([match])
    assert primary is match
    assert secondary == []


def test_higher_priority_wins():
    low = RuleMatch(rule=_rule(id="LOW", priority=1))
    high = RuleMatch(rule=_rule(id="HIGH", priority=10))
    primary, secondary = resolve_precedence([low, high])
    assert primary.rule.id == "HIGH"
    assert [m.rule.id for m in secondary] == ["LOW"]


def test_priority_tie_broken_by_scope_specificity():
    global_rule = RuleMatch(
        rule=_rule(id="GLOBAL", priority=5, scope=RuleScope.GLOBAL, source_note=None, source_clause_id="C1")
    )
    voyage_rule = RuleMatch(
        rule=_rule(id="VOYAGE", priority=5, scope=RuleScope.VOYAGE, source_note=None, source_clause_id="C2")
    )
    primary, secondary = resolve_precedence([global_rule, voyage_rule])
    assert primary.rule.id == "VOYAGE"
    assert [m.rule.id for m in secondary] == ["GLOBAL"]


def test_true_tie_raises_rule_conflict_not_arbitrary_choice():
    a = RuleMatch(rule=_rule(id="A", priority=5, scope=RuleScope.GLOBAL, source_note=None, source_clause_id="C1"))
    b = RuleMatch(rule=_rule(id="B", priority=5, scope=RuleScope.GLOBAL, source_note=None, source_clause_id="C2"))
    with pytest.raises(RuleConflictDetected):
        resolve_precedence([a, b])
