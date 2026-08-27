"""Rule precedence resolution — SYSTEM_ARCHITECTURE.md section 15.

When multiple RuleVersions match the same atomic interval, exactly one becomes the
"primary" rule (RULE 1: one second, one final treatment); the rest become documented
"secondary" events/rules for the explanation trail (RULE 3), never silently dropped.

A genuine, irreducible tie (same priority, same scope specificity) is NEVER resolved
by an arbitrary tiebreak such as insertion order — that is exactly the kind of silent
decision RULE 10 prohibits. It raises RuleConflictDetected instead.
"""
from __future__ import annotations

from dataclasses import dataclass, field
from decimal import Decimal

from app.domain.facts.models import SOFEvent
from app.domain.rules.models import SCOPE_SPECIFICITY, RuleScope, RuleStatus, RuleVersion


@dataclass
class RuleMatch:
    rule: RuleVersion
    trace: dict = field(default_factory=dict)


class RuleConflictDetected(Exception):
    """Two or more rules matched with identical priority and scope specificity.

    This must surface to the user as a RuleConflict requiring manual selection
    (brief section 28/50) — it must never be swallowed and auto-resolved.
    """

    def __init__(self, tied: list[RuleMatch]):
        self.tied = tied
        names = ", ".join(f"{m.rule.name} ({m.rule.id})" for m in tied)
        super().__init__(f"CONTRACTUAL RULE CONFLICT — unresolved tie between: {names}")


# System fallback for an interval with no matching rule: standard laytime counts in
# full. This is itself a normal RuleVersion (scope=MANUAL, lowest possible priority)
# so it goes through the exact same explanation/audit path as any contractual rule —
# never a special case baked into the engine.
DEFAULT_COUNT_RULE = RuleVersion(
    id="SYSTEM_DEFAULT_COUNT_V1",
    rule_definition_code="DEFAULT_COUNT",
    name="Default — Time Counts in Full",
    version_no=1,
    conditions=None,
    time_count_factor=Decimal(1),
    demurrage_rate_factor=Decimal(1),
    priority=-1_000_000,
    scope=RuleScope.MANUAL,
    source_note=(
        "System fallback: no contractual rule matched this period. Standard laytime "
        "practice — uninterrupted time counts in full — applies by default."
    ),
    status=RuleStatus.ACTIVE,
)


def resolve_precedence(matches: list[RuleMatch]) -> tuple[RuleMatch, list[RuleMatch]]:
    if not matches:
        return RuleMatch(rule=DEFAULT_COUNT_RULE, trace={"reason": "no rule matched"}), []
    if len(matches) == 1:
        return matches[0], []

    ranked = sorted(matches, key=lambda m: -m.rule.priority)
    top_priority = ranked[0].rule.priority
    tied_priority = [m for m in ranked if m.rule.priority == top_priority]
    if len(tied_priority) == 1:
        winner = tied_priority[0]
        return winner, [m for m in matches if m is not winner]

    scope_ranked = sorted(tied_priority, key=lambda m: SCOPE_SPECIFICITY[m.rule.scope])
    best_specificity = SCOPE_SPECIFICITY[scope_ranked[0].rule.scope]
    tied_scope = [m for m in scope_ranked if SCOPE_SPECIFICITY[m.rule.scope] == best_specificity]
    if len(tied_scope) == 1:
        winner = tied_scope[0]
        return winner, [m for m in matches if m is not winner]

    raise RuleConflictDetected(tied_scope)


def render_reason(primary: RuleMatch, secondary: list[RuleMatch], active_events: list[SOFEvent]) -> str:
    categories = ", ".join(sorted({e.category for e in active_events})) or "no active events"
    pct = f"{primary.rule.time_count_factor * 100:.0f}%"
    text = f'"{primary.rule.name}" applied — time counts at {pct}. Active events: {categories}.'
    if secondary:
        sec_names = ", ".join(m.rule.name for m in secondary)
        text += (
            f" Concurrent secondary rule(s)/event(s) ({sec_names}) matched this period but produced "
            f'no additional deduction — it was already fully treated under "{primary.rule.name}". '
            "Reason: NO DOUBLE DEDUCTION."
        )
    return text
