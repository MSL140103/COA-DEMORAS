from __future__ import annotations

from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy import select
from sqlalchemy.orm import Session

from app.api.schemas import CalculationVersionOut
from app.domain.calculation.pipeline import CalculationBlocked
from app.infrastructure.db import models as orm
from app.infrastructure.db.base import get_db
from app.workflow.calculation_service import NoRuleSetAssigned, run_and_persist_calculation

router = APIRouter(prefix="/voyages/{voyage_id}/calculations", tags=["calculations"])


def _get_voyage(db: Session, voyage_id: str) -> orm.Voyage:
    voyage = db.get(orm.Voyage, voyage_id)
    if voyage is None:
        raise HTTPException(status_code=404, detail="Voyage not found")
    return voyage


@router.post("", response_model=CalculationVersionOut, status_code=201)
def run_calculation_endpoint(voyage_id: str, created_by: str = "system", db: Session = Depends(get_db)):
    voyage = _get_voyage(db, voyage_id)
    try:
        return run_and_persist_calculation(db, voyage, created_by=created_by)
    except NoRuleSetAssigned as exc:
        raise HTTPException(status_code=422, detail=str(exc)) from exc
    except CalculationBlocked as exc:
        raise HTTPException(status_code=409, detail=f"CALCULATION INTEGRITY ERROR: {exc}") from exc
    except ValueError as exc:
        raise HTTPException(status_code=422, detail=str(exc)) from exc


@router.get("", response_model=list[CalculationVersionOut])
def list_calculations(voyage_id: str, db: Session = Depends(get_db)):
    _get_voyage(db, voyage_id)
    return list(
        db.scalars(
            select(orm.CalculationVersion)
            .where(orm.CalculationVersion.voyage_id == voyage_id)
            .order_by(orm.CalculationVersion.version_no.desc())
        ).all()
    )


@router.get("/latest", response_model=CalculationVersionOut)
def latest_calculation(voyage_id: str, db: Session = Depends(get_db)):
    _get_voyage(db, voyage_id)
    calc = db.scalar(
        select(orm.CalculationVersion)
        .where(orm.CalculationVersion.voyage_id == voyage_id)
        .order_by(orm.CalculationVersion.version_no.desc())
    )
    if calc is None:
        raise HTTPException(status_code=404, detail="No calculation yet for this voyage")
    return calc


@router.get("/{calculation_id}/intervals/{index}/explanation")
def explain_interval(voyage_id: str, calculation_id: str, index: int, db: Session = Depends(get_db)):
    """Single endpoint powering the 'Clickable Rule' explanation panel
    (SYSTEM_ARCHITECTURE.md sections 14, 59) — always derived from what was actually
    persisted for this CalculationVersion, never recomputed live."""
    calc = db.get(orm.CalculationVersion, calculation_id)
    if calc is None or calc.voyage_id != voyage_id:
        raise HTTPException(status_code=404, detail="Calculation not found")

    intervals = calc.results.get("intervals", [])
    if index < 0 or index >= len(intervals):
        raise HTTPException(status_code=404, detail="Interval index out of range")
    interval = intervals[index]

    primary_rule = db.get(orm.RuleVersion, interval["primary_rule_id"])
    secondary_rules = [db.get(orm.RuleVersion, rid) for rid in interval["secondary_rule_ids"]]

    active_events = [db.get(orm.SOFEvent, eid) for eid in interval["active_event_ids"]]

    def _rule_out(r: orm.RuleVersion | None):
        if r is None:
            return None
        return {
            "id": r.id,
            "name": r.name,
            "rule_definition_code": r.rule_definition_code,
            "time_count_factor": r.time_count_factor,
            "demurrage_rate_factor": r.demurrage_rate_factor,
            "scope": r.scope,
            "source_document_id": r.source_document_id,
            "source_clause_id": r.source_clause_id,
            "source_page": r.source_page,
            "source_note": r.source_note,
        }

    def _event_out(e: orm.SOFEvent | None):
        if e is None:
            return None
        return {
            "id": e.id,
            "category": e.category,
            "start_time": e.start_time,
            "end_time": e.end_time,
            "source_text": e.source_text,
            "document_id": e.document_id,
            "page_number": e.page_number,
        }

    return {
        "interval": interval,
        "sof_evidence": [_event_out(e) for e in active_events],
        "selected_rule": _rule_out(primary_rule),
        "secondary_rules": [_rule_out(r) for r in secondary_rules],
        "decision_reason": interval["decision_reason"],
    }
