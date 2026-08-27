from __future__ import annotations

from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy import select
from sqlalchemy.orm import Session

from app.api.schemas import ManualOverrideCreate, ManualOverrideOut
from app.infrastructure.db import models as orm
from app.infrastructure.db.base import get_db
from app.workflow.calculation_service import run_and_persist_calculation

router = APIRouter(prefix="/voyages/{voyage_id}/overrides", tags=["overrides"])


@router.get("", response_model=list[ManualOverrideOut])
def list_overrides(voyage_id: str, db: Session = Depends(get_db)):
    return list(
        db.scalars(
            select(orm.ManualOverride)
            .where(orm.ManualOverride.voyage_id == voyage_id)
            .order_by(orm.ManualOverride.created_at)
        ).all()
    )


@router.post("", response_model=ManualOverrideOut, status_code=201)
def create_override(voyage_id: str, payload: ManualOverrideCreate, db: Session = Depends(get_db)):
    """Create a manual override and immediately trigger a new CalculationVersion
    (SYSTEM_ARCHITECTURE.md section 17) — the previous suggestion is never deleted,
    only recorded as superseded once a later override replaces it for the same
    target_key."""
    voyage = db.get(orm.Voyage, voyage_id)
    if voyage is None:
        raise HTTPException(status_code=404, detail="Voyage not found")

    latest_calc = db.scalar(
        select(orm.CalculationVersion)
        .where(orm.CalculationVersion.voyage_id == voyage_id)
        .order_by(orm.CalculationVersion.version_no.desc())
    )
    original_value = {}
    if latest_calc is not None:
        for interval in latest_calc.results.get("intervals", []):
            key = f"{interval['interval_start']}|{interval['interval_end']}"
            if key == payload.target_key:
                original_value = {
                    "final_time_count_factor": interval["final_time_count_factor"],
                    "final_demurrage_rate_factor": interval["final_demurrage_rate_factor"],
                    "primary_rule_id": interval["primary_rule_id"],
                    "decision_reason": interval["decision_reason"],
                }
                break

    # Supersede any prior active override on the same target — never delete it.
    prior = db.scalars(
        select(orm.ManualOverride).where(
            orm.ManualOverride.voyage_id == voyage_id,
            orm.ManualOverride.target_key == payload.target_key,
            orm.ManualOverride.superseded_by.is_(None),
        )
    ).all()

    override = orm.ManualOverride(
        voyage_id=voyage_id,
        target_key=payload.target_key,
        original_value=original_value,
        new_time_count_factor=payload.new_time_count_factor,
        new_demurrage_rate_factor=payload.new_demurrage_rate_factor,
        reason=payload.reason,
        supporting_clause_id=payload.supporting_clause_id,
        comment=payload.comment,
        created_by=payload.created_by,
    )
    db.add(override)
    db.flush()

    for old in prior:
        old.superseded_by = override.id

    db.commit()
    db.refresh(override)

    run_and_persist_calculation(db, voyage, created_by=payload.created_by)

    return override
