from __future__ import annotations

from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy import select
from sqlalchemy.orm import Session

from app.api.schemas import SOFEventCreate, SOFEventOut, SOFEventUpdate
from app.infrastructure.db import models as orm
from app.infrastructure.db.base import get_db

router = APIRouter(prefix="/voyages/{voyage_id}/sof-events", tags=["sof-events"])


def _primary_port_call(db: Session, voyage_id: str) -> orm.PortCall:
    port_call = db.scalar(
        select(orm.PortCall).where(orm.PortCall.voyage_id == voyage_id).order_by(orm.PortCall.sequence_no)
    )
    if port_call is None:
        raise HTTPException(status_code=404, detail="Voyage has no port call")
    return port_call


@router.get("", response_model=list[SOFEventOut])
def list_sof_events(voyage_id: str, db: Session = Depends(get_db)) -> list[orm.SOFEvent]:
    port_call = _primary_port_call(db, voyage_id)
    return list(
        db.scalars(
            select(orm.SOFEvent).where(orm.SOFEvent.port_call_id == port_call.id).order_by(orm.SOFEvent.start_time)
        ).all()
    )


@router.post("", response_model=SOFEventOut, status_code=201)
def create_sof_event(voyage_id: str, payload: SOFEventCreate, db: Session = Depends(get_db)) -> orm.SOFEvent:
    port_call = _primary_port_call(db, voyage_id)
    event = orm.SOFEvent(port_call_id=port_call.id, status="EXTRACTED", **payload.model_dump())
    db.add(event)
    db.commit()
    db.refresh(event)
    return event


_EDITABLE_FIELDS = ("category", "subtype", "start_time", "end_time", "status", "confidence_status", "comment")


@router.patch("/{event_id}", response_model=SOFEventOut)
def update_sof_event(
    voyage_id: str, event_id: str, payload: SOFEventUpdate, db: Session = Depends(get_db)
) -> orm.SOFEvent:
    event = db.get(orm.SOFEvent, event_id)
    if event is None or event.port_call.voyage_id != voyage_id:
        raise HTTPException(status_code=404, detail="SOF event not found")

    changes = payload.model_dump(exclude={"changed_by", "reason"}, exclude_none=True)
    for field, new_value in changes.items():
        if field not in _EDITABLE_FIELDS:
            continue
        old_value = getattr(event, field)
        if str(old_value) == str(new_value):
            continue
        db.add(
            orm.EventEvidence(
                sof_event_id=event.id,
                field_changed=field,
                previous_value=str(old_value) if old_value is not None else None,
                new_value=str(new_value) if new_value is not None else None,
                changed_by=payload.changed_by,
                reason=payload.reason,
            )
        )
        setattr(event, field, new_value)

    # Any human-driven edit that isn't purely a status transition to CONFIRMED moves
    # the event out of raw EXTRACTED state — RULE: nothing reaches CONFIRMED except
    # by explicit human action (brief section 9).
    if event.status == "EXTRACTED" and payload.status != "CONFIRMED":
        event.status = "EDITED"

    db.commit()
    db.refresh(event)
    return event
