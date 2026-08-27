from __future__ import annotations

from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy import select
from sqlalchemy.orm import Session

from app.api.schemas import VoyageCreate, VoyageOut
from app.infrastructure.db import models as orm
from app.infrastructure.db.base import get_db
from app.workflow.rules_service import ensure_seed_rule_set

router = APIRouter(prefix="/voyages", tags=["voyages"])


@router.post("", response_model=VoyageOut, status_code=201)
def create_voyage(payload: VoyageCreate, db: Session = Depends(get_db)) -> orm.Voyage:
    rule_set = ensure_seed_rule_set(db)

    voyage = orm.Voyage(**payload.model_dump(), rule_set_version_id=rule_set.id)
    db.add(voyage)
    db.flush()

    port_call = orm.PortCall(
        voyage_id=voyage.id,
        sequence_no=1,
        port=payload.load_port if payload.operation_type == "LOADING" else payload.discharge_port,
        terminal=payload.terminal,
        berth=payload.berth,
        operation_type=payload.operation_type,
    )
    db.add(port_call)
    db.commit()
    db.refresh(voyage)
    return voyage


@router.get("", response_model=list[VoyageOut])
def list_voyages(db: Session = Depends(get_db)) -> list[orm.Voyage]:
    return list(db.scalars(select(orm.Voyage).order_by(orm.Voyage.created_at.desc())).all())


@router.get("/{voyage_id}", response_model=VoyageOut)
def get_voyage(voyage_id: str, db: Session = Depends(get_db)) -> orm.Voyage:
    voyage = db.get(orm.Voyage, voyage_id)
    if voyage is None:
        raise HTTPException(status_code=404, detail="Voyage not found")
    return voyage
