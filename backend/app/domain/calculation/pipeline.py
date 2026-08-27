"""Top-level Calculation pipeline — wires together commencement, atomic timeline,
integrity check, laytime and demurrage into one deterministic run.

This is the one function the API/service layer should call to produce a
CalculationVersion's results. It never touches AI, network, or a database — inputs
are plain domain objects, output is a plain result object, so it is trivially
reproducible given the same (events, rule_set, overrides, parameters) tuple, which is
exactly what RULE 7 (historical reproducibility) requires.
"""
from __future__ import annotations

from dataclasses import dataclass
from datetime import datetime, timedelta
from decimal import Decimal

from app.domain.calculation.commencement import CommencementDetermination, determine_commencement
from app.domain.calculation.demurrage import DemurrageResult, calculate_demurrage
from app.domain.calculation.laytime import LaytimeResult, calculate_laytime
from app.domain.calculation.overrides import ManualOverride, apply_overrides
from app.domain.facts.models import SOFEvent
from app.domain.rules.models import RuleSetVersion
from app.domain.timeline.engine import AtomicInterval, build_atomic_timeline
from app.domain.timeline.integrity import IntegrityResult, integrity_check


class CalculationBlocked(Exception):
    """Raised when the integrity check fails — a CalculationVersion in this state
    must never be approvable (SYSTEM_ARCHITECTURE.md section 16 / brief section 41)."""


@dataclass
class CalculationRun:
    commencement: CommencementDetermination
    intervals: list[AtomicInterval]
    integrity: IntegrityResult
    laytime: LaytimeResult
    demurrage: DemurrageResult


def _find_single(events: list[SOFEvent], category: str) -> datetime | None:
    matches = [e for e in events if e.category == category]
    if not matches:
        return None
    # If several exist (e.g. a corrected duplicate), the earliest confirmed one wins;
    # true conflicting duplicates should have been resolved during SOF review.
    return sorted(matches, key=lambda e: e.start_time)[0].start_time


def run_calculation(
    *,
    events: list[SOFEvent],
    rule_set: RuleSetVersion,
    allowed_laytime: timedelta,
    demurrage_daily_rate: Decimal,
    overrides: list[ManualOverride] | None = None,
    nor_allowance_hours: Decimal | None = None,
) -> CalculationRun:
    overrides = overrides or []
    confirmed = [e for e in events if e.status.value == "CONFIRMED"]
    if not confirmed:
        raise ValueError("No confirmed SOF events — nothing to calculate")

    nor_time = _find_single(confirmed, "NOR_TENDERED")
    moored_time = _find_single(confirmed, "SECURELY_MOORED") or _find_single(confirmed, "ALL_FAST")

    allowance = nor_allowance_hours
    if allowance is None:
        nor_rule = next((r for r in rule_set.rules if r.rule_definition_code == "NOR_ALLOWANCE"), None)
        allowance = Decimal(str(nor_rule.parameters.get("allowance_hours", 6))) if nor_rule else Decimal(6)

    commencement = determine_commencement(
        nor_tendered=nor_time,
        securely_moored=moored_time,
        allowance_hours=allowance,
    )

    gross_start = min(e.start_time for e in confirmed)
    gross_end = max(e.effective_end for e in confirmed)
    if gross_start == gross_end:
        gross_end = gross_start + timedelta(seconds=1)

    intervals = build_atomic_timeline(confirmed, rule_set, gross_start, gross_end)
    intervals = apply_overrides(intervals, overrides)

    integrity = integrity_check(intervals, gross_start, gross_end)
    if not integrity.ok:
        raise CalculationBlocked(f"{integrity.error}: {integrity.detail}")

    laytime = calculate_laytime(intervals, commencement.selected, allowed_laytime)
    demurrage = calculate_demurrage(intervals, laytime.demurrage_commencement, demurrage_daily_rate)

    return CalculationRun(
        commencement=commencement,
        intervals=intervals,
        integrity=integrity,
        laytime=laytime,
        demurrage=demurrage,
    )
