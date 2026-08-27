"""Bridges the DB layer to the pure domain Calculation pipeline.

This is the only place allowed to import both `app.infrastructure.db` and
`app.domain.calculation` — routers must never call the domain engine directly with
raw request data, and the domain engine must never import SQLAlchemy. Keeping the
seam here is what makes app.domain independently testable and reproducible.
"""
from __future__ import annotations

import json
from dataclasses import asdict
from datetime import timedelta
from decimal import Decimal

from sqlalchemy import select
from sqlalchemy.orm import Session

from app.domain.calculation.overrides import ManualOverride as DomainManualOverride
from app.domain.calculation.pipeline import CalculationBlocked, run_calculation
from app.infrastructure.db import models as orm
from app.infrastructure.db.mappers import rule_set_version_to_domain, sof_event_to_domain


class NoRuleSetAssigned(ValueError):
    pass


def _json_default(value):
    if isinstance(value, Decimal):
        return str(value)
    if hasattr(value, "isoformat"):
        return value.isoformat()
    return str(value)


def _serialize_run(run) -> dict:
    return json.loads(
        json.dumps(
            {
                "commencement": {
                    "candidates": [
                        {"label": c.label, "time": c.time, "rule_id": c.rule_id} for c in run.commencement.candidates
                    ],
                    "selected": run.commencement.selected,
                    "selected_label": run.commencement.selected_label,
                    "rule_applied": run.commencement.rule_applied,
                },
                "intervals": [
                    {
                        "interval_start": i.interval_start,
                        "interval_end": i.interval_end,
                        "duration_seconds": i.duration.total_seconds(),
                        "active_event_ids": i.active_event_ids,
                        "matched_rule_ids": i.matched_rule_ids,
                        "primary_rule_id": i.primary_rule_id,
                        "primary_rule_name": i.primary_rule_name,
                        "secondary_rule_ids": i.secondary_rule_ids,
                        "final_time_count_factor": i.final_time_count_factor,
                        "final_demurrage_rate_factor": i.final_demurrage_rate_factor,
                        "decision_reason": i.decision_reason,
                    }
                    for i in run.intervals
                ],
                "integrity": {"ok": run.integrity.ok, "error": run.integrity.error, "detail": run.integrity.detail},
                "laytime": {
                    "gross_elapsed_seconds": run.laytime.gross_elapsed.total_seconds(),
                    "used_laytime_seconds": run.laytime.used_laytime.total_seconds(),
                    "remaining_laytime_seconds": run.laytime.remaining_laytime.total_seconds(),
                    "excess_time_seconds": run.laytime.excess_time.total_seconds(),
                    "demurrage_commencement": run.laytime.demurrage_commencement,
                },
                "demurrage": {
                    "full_rate_time_seconds": run.demurrage.full_rate_time.total_seconds(),
                    "half_rate_time_seconds": run.demurrage.half_rate_time.total_seconds(),
                    "other_rate_time_seconds": run.demurrage.other_rate_time.total_seconds(),
                    "daily_rate": run.demurrage.daily_rate,
                    "amount": run.demurrage.amount,
                },
            },
            default=_json_default,
        )
    )


def run_and_persist_calculation(db: Session, voyage: orm.Voyage, *, created_by: str | None = None) -> orm.CalculationVersion:
    if not voyage.rule_set_version_id:
        raise NoRuleSetAssigned(f"Voyage {voyage.id} has no rule_set_version_id assigned")

    rule_set_row = db.get(orm.RuleSetVersion, voyage.rule_set_version_id)
    rule_set = rule_set_version_to_domain(rule_set_row)

    port_call_ids = [pc.id for pc in voyage.port_calls]
    event_rows = db.scalars(
        select(orm.SOFEvent).where(orm.SOFEvent.port_call_id.in_(port_call_ids))
    ).all()
    domain_events = [sof_event_to_domain(e) for e in event_rows]

    override_rows = db.scalars(
        select(orm.ManualOverride).where(orm.ManualOverride.voyage_id == voyage.id)
    ).all()
    domain_overrides = [
        DomainManualOverride(
            id=o.id,
            target_key=o.target_key,
            new_time_count_factor=o.new_time_count_factor,
            new_demurrage_rate_factor=o.new_demurrage_rate_factor,
            reason=o.reason,
            created_by=o.created_by,
            created_at=o.created_at,
            supporting_clause_id=o.supporting_clause_id,
            superseded_by=o.superseded_by,
        )
        for o in override_rows
    ]

    allowed_laytime = _to_timedelta(voyage.allowed_laytime_value, voyage.allowed_laytime_unit)

    try:
        run = run_calculation(
            events=domain_events,
            rule_set=rule_set,
            allowed_laytime=allowed_laytime,
            demurrage_daily_rate=voyage.demurrage_rate_value,
            overrides=domain_overrides,
            nor_allowance_hours=voyage.nor_allowance_hours,
        )
        integrity_ok = True
        status = "CALCULATED"
    except CalculationBlocked as exc:
        # The integrity guard tripped — persist the failure itself as evidence
        # (brief section 41) rather than silently discarding the attempt.
        raise

    results = _serialize_run(run)

    prev_count = db.scalar(
        select(orm.CalculationVersion.version_no)
        .where(orm.CalculationVersion.voyage_id == voyage.id)
        .order_by(orm.CalculationVersion.version_no.desc())
    )
    next_version = (prev_count or 0) + 1

    calc = orm.CalculationVersion(
        voyage_id=voyage.id,
        version_no=next_version,
        kind="SW",
        rule_set_version_id=rule_set.id,
        event_snapshot_ids=[e.id for e in domain_events if e.status.value == "CONFIRMED"],
        manual_override_ids=[o.id for o in domain_overrides if o.superseded_by is None],
        results=results,
        integrity_ok=integrity_ok,
        status=status,
        created_by=created_by,
    )
    db.add(calc)
    db.commit()
    db.refresh(calc)
    return calc


def _to_timedelta(value: Decimal, unit: str) -> timedelta:
    if unit == "HOURS":
        return timedelta(hours=float(value))
    if unit in ("RUNNING_DAYS", "WEATHER_WORKING_DAYS"):
        # CONTRACTUAL DECISION REQUIRED (SYSTEM_ARCHITECTURE.md section 29 item 3):
        # weather working day calendars are not yet implemented; RUNNING_DAYS is
        # treated as a plain 24h day for MVP1.
        return timedelta(days=float(value))
    raise ValueError(f"Unsupported allowed_laytime_unit: {unit!r}")
