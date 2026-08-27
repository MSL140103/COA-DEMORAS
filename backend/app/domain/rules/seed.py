"""MVP1 base rule set — a small number of illustrative, provisional rules
(SYSTEM_ARCHITECTURE.md section 23 / MVP1 scope: "0%, 50%, 100%").

Every rule here is scope=MANUAL with an explicit source_note flagging it as
provisional seed data, NOT a real contractual source. Per RULE 4 / brief section 56,
this is the correct way to represent "we don't have a real clause yet" — it is never
silently treated as sourced. Replace/duplicate these into scope=CONTRACT rules with a
real source_clause_id once Contract Clause Extraction (MVP2) is live.
"""
from __future__ import annotations

from decimal import Decimal

from app.domain.rules.models import RuleScope, RuleSetVersion, RuleStatus, RuleVersion

PROVISIONAL_NOTE = (
    "Provisional MVP1 seed rule — not yet linked to a real contract clause. "
    "Replace with a sourced RuleVersion before approving any real calculation."
)


def base_rule_set(rule_set_id: str = "SEED_BASE_RULESET_V1") -> RuleSetVersion:
    nor_allowance = RuleVersion(
        id="SEED_NOR_ALLOWANCE_V1",
        rule_definition_code="NOR_ALLOWANCE",
        name="NOR + Allowance",
        version_no=1,
        description="Time commences to run N hours after NOR is tendered, or securely moored, whichever occurs first.",
        conditions=None,  # consumed directly by app.domain.calculation.commencement, not interval-matched
        parameters={"allowance_hours": 6},
        time_count_factor=Decimal(1),
        demurrage_rate_factor=Decimal(1),
        priority=0,
        scope=RuleScope.MANUAL,
        source_note=PROVISIONAL_NOTE + " Modelled on the standard 'NOR + 6' clause (brief section 11).",
        status=RuleStatus.ACTIVE,
    )

    weather = RuleVersion(
        id="SEED_WEATHER_WINDOW_V1",
        rule_definition_code="WEATHER_WINDOW",
        name="Weather — 50% Count",
        version_no=1,
        description="Bad weather / fog / swell counts at 50% of elapsed time.",
        conditions={"field": "event.category", "op": "eq", "value": "WEATHER"},
        parameters={},
        time_count_factor=Decimal("0.5"),
        demurrage_rate_factor=Decimal("0.5"),
        priority=10,
        scope=RuleScope.MANUAL,
        source_note=PROVISIONAL_NOTE,
        status=RuleStatus.ACTIVE,
    )

    shifting = RuleVersion(
        id="SEED_SHIFTING_TREATMENT_V1",
        rule_definition_code="SHIFTING_TREATMENT",
        name="Shifting — Excluded",
        version_no=1,
        description="Time spent shifting between berths/anchorage does not count.",
        conditions={"field": "event.category", "op": "eq", "value": "SHIFTING"},
        parameters={},
        time_count_factor=Decimal(0),
        demurrage_rate_factor=Decimal(0),
        priority=20,  # outranks Weather when both are active in the same interval —
                      # reproduces the brief's canonical Shifting+Weather overlap example.
        scope=RuleScope.MANUAL,
        source_note=PROVISIONAL_NOTE,
        status=RuleStatus.ACTIVE,
    )

    return RuleSetVersion(
        id=rule_set_id,
        name="MVP1 Seed Base Rule Set",
        version_no=1,
        rules=[nor_allowance, weather, shifting],
        status=RuleStatus.ACTIVE,
    )
