"""No-Double-Deduction integrity check — SYSTEM_ARCHITECTURE.md section 16.

Defense in depth: build_atomic_timeline() makes double deduction structurally
impossible by construction (disjoint, contiguous intervals; exactly one factor each).
This module actively re-verifies that invariant after the fact, because a
CalculationVersion must never be approvable while it is unverified.
"""
from __future__ import annotations

from dataclasses import dataclass
from datetime import datetime, timedelta

from app.domain.timeline.engine import AtomicInterval


@dataclass
class IntegrityResult:
    ok: bool
    error: str | None = None
    detail: str | None = None


def integrity_check(intervals: list[AtomicInterval], gross_start: datetime, gross_end: datetime) -> IntegrityResult:
    if not intervals:
        if gross_start == gross_end:
            return IntegrityResult(ok=True)
        return IntegrityResult(
            ok=False,
            error="CALCULATION INTEGRITY ERROR — POSSIBLE DOUBLE DEDUCTION",
            detail="no intervals were produced for a non-empty gross timeline",
        )

    ordered = sorted(intervals, key=lambda i: i.interval_start)

    total = sum((i.duration for i in ordered), timedelta())
    gross = gross_end - gross_start
    if total != gross:
        return IntegrityResult(
            ok=False,
            error="CALCULATION INTEGRITY ERROR — POSSIBLE DOUBLE DEDUCTION",
            detail=f"sum(interval durations)={total} != gross timeline={gross}",
        )

    if ordered[0].interval_start != gross_start or ordered[-1].interval_end != gross_end:
        return IntegrityResult(
            ok=False,
            error="GAP OR OVERLAP DETECTED",
            detail=(
                f"timeline does not span exactly [gross_start, gross_end]: "
                f"got [{ordered[0].interval_start}, {ordered[-1].interval_end}]"
            ),
        )

    for a, b in zip(ordered, ordered[1:]):
        if a.interval_end != b.interval_start:
            return IntegrityResult(
                ok=False,
                error="GAP OR OVERLAP DETECTED",
                detail=f"interval ending {a.interval_end} is not immediately followed by one starting there (next starts {b.interval_start})",
            )

    return IntegrityResult(ok=True)
