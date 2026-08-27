"""Test 29 (brief section 78): a rule without a contractual source must be rejected,
not silently accepted. RULE 4 / brief section 56."""
from decimal import Decimal

import pytest
from pydantic import ValidationError

from app.domain.rules.models import RuleScope, RuleVersion


def test_non_manual_rule_without_source_clause_is_rejected():
    with pytest.raises(ValidationError, match="SOURCE NOT LINKED"):
        RuleVersion(
            id="BAD",
            rule_definition_code="WEATHER_WINDOW",
            name="Weather 50%",
            conditions={"field": "event.category", "op": "eq", "value": "WEATHER"},
            time_count_factor=Decimal("0.5"),
            demurrage_rate_factor=Decimal("0.5"),
            scope=RuleScope.CONTRACT,  # not MANUAL -> requires source_clause_id
        )


def test_manual_rule_without_source_note_is_rejected():
    with pytest.raises(ValidationError, match="source_note"):
        RuleVersion(
            id="BAD2",
            rule_definition_code="WEATHER_WINDOW",
            name="Weather 50%",
            conditions={"field": "event.category", "op": "eq", "value": "WEATHER"},
            time_count_factor=Decimal("0.5"),
            demurrage_rate_factor=Decimal("0.5"),
            scope=RuleScope.MANUAL,
        )


def test_contract_scoped_rule_with_source_clause_is_accepted():
    rule = RuleVersion(
        id="GOOD",
        rule_definition_code="WEATHER_WINDOW",
        name="Weather 50%",
        conditions={"field": "event.category", "op": "eq", "value": "WEATHER"},
        time_count_factor=Decimal("0.5"),
        demurrage_rate_factor=Decimal("0.5"),
        scope=RuleScope.CONTRACT,
        source_clause_id="CLAUSE-15",
        source_document_id="DOC-1",
        source_page=12,
    )
    assert rule.source_clause_id == "CLAUSE-15"


def test_manual_scope_with_source_note_is_accepted():
    rule = RuleVersion(
        id="GOOD2",
        rule_definition_code="WEATHER_WINDOW",
        name="Weather 50%",
        conditions={"field": "event.category", "op": "eq", "value": "WEATHER"},
        time_count_factor=Decimal("0.5"),
        demurrage_rate_factor=Decimal("0.5"),
        scope=RuleScope.MANUAL,
        source_note="Provisional seed rule pending real clause",
    )
    assert rule.scope == RuleScope.MANUAL
