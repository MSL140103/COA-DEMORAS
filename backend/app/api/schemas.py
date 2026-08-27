from __future__ import annotations

from datetime import datetime
from decimal import Decimal
from typing import Optional

from pydantic import BaseModel, ConfigDict


class VoyageCreate(BaseModel):
    vessel_name: str
    voyage_number: str
    counterparty: Optional[str] = None
    sw_user: Optional[str] = None
    load_port: Optional[str] = None
    discharge_port: Optional[str] = None
    terminal: Optional[str] = None
    berth: Optional[str] = None
    country: Optional[str] = None
    operation_type: str = "LOADING"
    laycan_from: Optional[datetime] = None
    laycan_to: Optional[datetime] = None
    allowed_laytime_value: Decimal
    allowed_laytime_unit: str = "HOURS"
    demurrage_rate_type: str = "FIXED_PDPRY"
    demurrage_rate_value: Decimal
    currency: str = "USD"
    daylight_restriction_enabled: bool = False
    daylight_start: Optional[str] = None
    daylight_end: Optional[str] = None
    sealine: bool = False
    lightering: bool = False
    transshipment: bool = False
    nor_allowance_hours: Decimal = Decimal(6)
    comments: Optional[str] = None
    created_by: Optional[str] = None


class VoyageOut(VoyageCreate):
    model_config = ConfigDict(from_attributes=True)
    id: str
    workflow_state: str
    created_at: datetime


class PortCallOut(BaseModel):
    model_config = ConfigDict(from_attributes=True)
    id: str
    voyage_id: str
    sequence_no: int
    port: Optional[str] = None
    terminal: Optional[str] = None
    berth: Optional[str] = None
    operation_type: str


class SOFEventCreate(BaseModel):
    category: str
    subtype: Optional[str] = None
    start_time: datetime
    end_time: Optional[datetime] = None
    source_text: Optional[str] = None
    document_id: Optional[str] = None
    page_number: Optional[int] = None
    confidence_score: Optional[float] = None
    confidence_status: str = "NEEDS_REVIEW"
    comment: Optional[str] = None


class SOFEventUpdate(BaseModel):
    category: Optional[str] = None
    subtype: Optional[str] = None
    start_time: Optional[datetime] = None
    end_time: Optional[datetime] = None
    status: Optional[str] = None
    confidence_status: Optional[str] = None
    comment: Optional[str] = None
    changed_by: str
    reason: Optional[str] = None


class SOFEventOut(BaseModel):
    model_config = ConfigDict(from_attributes=True)
    id: str
    port_call_id: str
    category: str
    subtype: Optional[str] = None
    start_time: datetime
    end_time: Optional[datetime] = None
    source_text: Optional[str] = None
    document_id: Optional[str] = None
    page_number: Optional[int] = None
    confidence_score: Optional[float] = None
    confidence_status: str
    status: str
    comment: Optional[str] = None


class ManualOverrideCreate(BaseModel):
    target_key: str
    new_time_count_factor: Optional[Decimal] = None
    new_demurrage_rate_factor: Optional[Decimal] = None
    reason: str
    supporting_clause_id: Optional[str] = None
    comment: Optional[str] = None
    created_by: str


class ManualOverrideOut(BaseModel):
    model_config = ConfigDict(from_attributes=True)
    id: str
    voyage_id: str
    target_key: str
    new_time_count_factor: Optional[Decimal] = None
    new_demurrage_rate_factor: Optional[Decimal] = None
    reason: str
    created_by: str
    created_at: datetime
    superseded_by: Optional[str] = None


class DocumentOut(BaseModel):
    model_config = ConfigDict(from_attributes=True)
    id: str
    voyage_id: str
    type: str
    filename: str
    mime_type: Optional[str] = None
    page_count: Optional[int] = None
    extraction_method: Optional[str] = None
    status: str
    uploaded_at: datetime


class DocumentUploadResult(BaseModel):
    document: DocumentOut
    candidate_events_created: int


class CalculationVersionOut(BaseModel):
    model_config = ConfigDict(from_attributes=True)
    id: str
    voyage_id: str
    version_no: int
    kind: str
    rule_set_version_id: str
    results: dict
    integrity_ok: bool
    status: str
    created_at: datetime
