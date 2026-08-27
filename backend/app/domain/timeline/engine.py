"""Atomic Timeline Engine — SYSTEM_ARCHITECTURE.md section 8.

Deterministic, no I/O, no AI. Turns a set of confirmed SOFEvents plus a frozen
RuleSetVersion into a list of AtomicInterval: contiguous, non-overlapping slices of
time where every second has exactly one final treatment (RULE 1) and no period is
ever deducted twice by construction (RULE 2) — see integrity.py for the active
verification of that guarantee.
"""
from __future__ import annotations

from datetime import datetime, timedelta
from decimal import Decimal

from pydantic import BaseModel, ConfigDict

from app.domain.facts.models import SOFEvent
from app.domain.rules.conditions import evaluate_condition_tree
from app.domain.rules.models import RuleSetVersion, RuleStatus
from app.domain.rules.precedence import RuleMatch, render_reason, resolve_precedence


class AtomicInterval(BaseModel):
    model_config = ConfigDict(frozen=True)

    interval_start: datetime
    interval_end: datetime
    active_event_ids: list[str]
    matched_rule_ids: list[str]
    primary_rule_id: str
    primary_rule_name: str
    secondary_rule_ids: list[str]
    final_time_count_factor: Decimal
    final_demurrage_rate_factor: Decimal
    decision_reason: str

    @property
    def duration(self) -> timedelta:
        return self.interval_end - self.interval_start


def collect_boundaries(events: list[SOFEvent], gross_start: datetime, gross_end: datetime) -> list[datetime]:
    """All timestamps where the active-event set (and therefore possibly the
    applicable rule) can change, clipped to [gross_start, gross_end].

    NOTE (MVP1 scope): structural boundaries that are *not* tied to a SOF event —
    e.g. the 48h/72h weather-window edge, daylight-restriction windows — are not yet
    collected here. They belong to the Weather Engine (MVP4, brief section 31) and
    must be added to this function (not layered on top of it) when that lands, or a
    rule change exactly at such a boundary would silently apply to the whole
    straddling interval instead of being split.
    """
    boundaries = {gross_start, gross_end}
    for event in events:
        if gross_start <= event.start_time <= gross_end:
            boundaries.add(event.start_time)
        end = event.effective_end
        if gross_start <= end <= gross_end:
            boundaries.add(end)
    return sorted(boundaries)


def _evaluate_rules_for_interval(
    active_events: list[SOFEvent],
    rule_set: RuleSetVersion,
    base_context: dict,
) -> list[RuleMatch]:
    matches: list[RuleMatch] = []
    for rule in rule_set.rules:
        if rule.status != RuleStatus.ACTIVE:
            continue
        if rule.conditions is None:
            # Reserved for the implicit DEFAULT_COUNT fallback — a real contractual
            # rule always carries explicit conditions so it never accidentally
            # matches every interval.
            continue
        local_ctx = {**base_context, "events": active_events, "params": rule.parameters}
        matched = evaluate_condition_tree(rule.conditions, local_ctx)
        if not matched:
            continue
        excepted = rule.exceptions is not None and evaluate_condition_tree(rule.exceptions, local_ctx)
        if excepted:
            continue
        matches.append(RuleMatch(rule=rule, trace={"conditions": rule.conditions}))
    return matches


def build_atomic_timeline(
    events: list[SOFEvent],
    rule_set: RuleSetVersion,
    gross_start: datetime,
    gross_end: datetime,
    base_context: dict | None = None,
) -> list[AtomicInterval]:
    base_context = base_context or {"context": {}, "voyage": {}}
    boundaries = collect_boundaries(events, gross_start, gross_end)

    intervals: list[AtomicInterval] = []
    for start, end in zip(boundaries, boundaries[1:]):
        if start >= end:
            continue
        active = [e for e in events if e.overlaps(start, end)]
        matches = _evaluate_rules_for_interval(active, rule_set, base_context)
        primary, secondary = resolve_precedence(matches)
        intervals.append(
            AtomicInterval(
                interval_start=start,
                interval_end=end,
                active_event_ids=[e.id for e in active],
                matched_rule_ids=[m.rule.id for m in matches] or [primary.rule.id],
                primary_rule_id=primary.rule.id,
                primary_rule_name=primary.rule.name,
                secondary_rule_ids=[m.rule.id for m in secondary],
                final_time_count_factor=primary.rule.time_count_factor,
                final_demurrage_rate_factor=primary.rule.demurrage_rate_factor,
                decision_reason=render_reason(primary, secondary, active),
            )
        )
    return intervals
