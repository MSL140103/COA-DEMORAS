from __future__ import annotations

from datetime import datetime

from fastapi import APIRouter, Depends, File, Form, HTTPException, UploadFile
from sqlalchemy import select
from sqlalchemy.orm import Session

from app.api.routers.sof_events import _primary_port_call
from app.api.schemas import DocumentOut, DocumentUploadResult
from app.extraction.sof_extraction.heuristic_extractor import HeuristicSOFExtractor
from app.extraction.sof_extraction.native_text import extract_native_text
from app.infrastructure.db import models as orm
from app.infrastructure.db.base import get_db
from app.infrastructure.storage.local import save_upload

router = APIRouter(prefix="/voyages/{voyage_id}/documents", tags=["documents"])

_EXTRACTOR = HeuristicSOFExtractor()


@router.get("", response_model=list[DocumentOut])
def list_documents(voyage_id: str, db: Session = Depends(get_db)):
    return list(db.scalars(select(orm.Document).where(orm.Document.voyage_id == voyage_id)).all())


@router.post("", response_model=DocumentUploadResult, status_code=201)
async def upload_document(
    voyage_id: str,
    file: UploadFile = File(...),
    type: str = Form(...),
    reference_year: int = Form(default=datetime.utcnow().year),
    db: Session = Depends(get_db),
):
    """Upload a document (SOF, Charter Party, etc.). For type=SOF and a PDF with
    extractable native text, immediately runs the heuristic extractor and creates
    candidate SOFEvent rows (status=EXTRACTED, confidence_status=NEEDS_REVIEW) — they
    still require human review/confirmation before any calculation will use them
    (brief section 9); nothing here writes a CONFIRMED event.
    """
    voyage = db.get(orm.Voyage, voyage_id)
    if voyage is None:
        raise HTTPException(status_code=404, detail="Voyage not found")

    content = await file.read()
    storage_uri, digest = save_upload(voyage_id, file.filename or "upload", content)

    document = orm.Document(
        voyage_id=voyage_id,
        type=type,
        filename=file.filename or "upload",
        storage_uri=storage_uri,
        mime_type=file.content_type,
        sha256_hash=digest,
        status="UPLOADED",
    )
    db.add(document)
    db.flush()

    candidate_count = 0
    if (file.content_type == "application/pdf") or (file.filename or "").lower().endswith(".pdf"):
        pages = extract_native_text(storage_uri)
        document.page_count = len(pages)
        document.extraction_method = "NATIVE_TEXT"
        document.extracted_text = "\n\f\n".join(pages)
        document.status = "TEXT_READY"

        if type == "SOF":
            port_call = _primary_port_call(db, voyage_id)
            candidates = _EXTRACTOR.extract(pages, reference_year=reference_year)
            for candidate in candidates:
                db.add(
                    orm.SOFEvent(
                        port_call_id=port_call.id,
                        document_id=document.id,
                        page_number=candidate.page_number,
                        category=candidate.category,
                        subtype=candidate.subtype,
                        start_time=candidate.start_time,
                        source_text=candidate.source_text,
                        confidence_score=candidate.confidence_score,
                        confidence_status=candidate.confidence_status,
                        status="EXTRACTED",
                    )
                )
            candidate_count = len(candidates)
    else:
        document.status = "TEXT_READY" if type != "SOF" else "UNSUPPORTED_FORMAT"

    db.commit()
    db.refresh(document)
    return DocumentUploadResult(document=document, candidate_events_created=candidate_count)
