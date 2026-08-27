"""SQLAlchemy ORM models — MVP1 subset of SYSTEM_ARCHITECTURE.md section 2.

Simplification note (documented, not silent): CalculationVersion persists its
AtomicInterval list, LaytimeResult and DemurrageResult as JSONB rather than as fully
normalized child tables (the architecture doc's long-term target). The domain engine
in app/domain is what actually computes and owns the semantics of that data; this
column is a durable, queryable snapshot of one deterministic run. Normalizing
AtomicInterval into its own versioned table is a reasonable next step once the
Rule/Comparison Engine needs to query across many calculations — not required for
MVP1's read patterns (always "the latest calculation for this voyage").
"""
from __future__ import annotations

import uuid
from datetime import datetime
from decimal import Decimal

from sqlalchemy import ForeignKey, Numeric, Table, Column, String
from sqlalchemy.dialects.postgresql import JSONB
from sqlalchemy.orm import Mapped, mapped_column, relationship
from sqlalchemy.sql import func

from app.infrastructure.db.base import Base


def _uuid() -> str:
    return str(uuid.uuid4())


class Voyage(Base):
    __tablename__ = "voyages"

    id: Mapped[str] = mapped_column(String, primary_key=True, default=_uuid)
    vessel_name: Mapped[str] = mapped_column(String)
    imo_number: Mapped[str | None] = mapped_column(String, nullable=True)
    voyage_number: Mapped[str] = mapped_column(String)
    counterparty: Mapped[str | None] = mapped_column(String, nullable=True)
    sw_user: Mapped[str | None] = mapped_column(String, nullable=True)
    rt_organization: Mapped[str | None] = mapped_column(String, nullable=True)

    load_port: Mapped[str | None] = mapped_column(String, nullable=True)
    discharge_port: Mapped[str | None] = mapped_column(String, nullable=True)
    terminal: Mapped[str | None] = mapped_column(String, nullable=True)
    berth: Mapped[str | None] = mapped_column(String, nullable=True)
    country: Mapped[str | None] = mapped_column(String, nullable=True)
    operation_type: Mapped[str] = mapped_column(String, default="LOADING")

    laycan_from: Mapped[datetime | None] = mapped_column(nullable=True)
    laycan_to: Mapped[datetime | None] = mapped_column(nullable=True)

    allowed_laytime_value: Mapped[Decimal] = mapped_column(Numeric(12, 4))
    allowed_laytime_unit: Mapped[str] = mapped_column(String, default="HOURS")

    demurrage_rate_type: Mapped[str] = mapped_column(String, default="FIXED_PDPRY")
    demurrage_rate_value: Mapped[Decimal] = mapped_column(Numeric(14, 2))
    currency: Mapped[str] = mapped_column(String, default="USD")

    daylight_restriction_enabled: Mapped[bool] = mapped_column(default=False)
    daylight_start: Mapped[str | None] = mapped_column(String, nullable=True)
    daylight_end: Mapped[str | None] = mapped_column(String, nullable=True)

    sealine: Mapped[bool] = mapped_column(default=False)
    lightering: Mapped[bool] = mapped_column(default=False)
    transshipment: Mapped[bool] = mapped_column(default=False)

    nor_allowance_hours: Mapped[Decimal] = mapped_column(Numeric(6, 2), default=Decimal(6))

    rule_set_version_id: Mapped[str | None] = mapped_column(
        ForeignKey("rule_set_versions.id"), nullable=True
    )

    workflow_state: Mapped[str] = mapped_column(String, default="VOYAGE_CREATED")
    comments: Mapped[str | None] = mapped_column(String, nullable=True)

    created_by: Mapped[str | None] = mapped_column(String, nullable=True)
    created_at: Mapped[datetime] = mapped_column(server_default=func.now())
    updated_at: Mapped[datetime] = mapped_column(server_default=func.now(), onupdate=func.now())

    port_calls: Mapped[list["PortCall"]] = relationship(back_populates="voyage", cascade="all, delete-orphan")
    documents: Mapped[list["Document"]] = relationship(back_populates="voyage", cascade="all, delete-orphan")
    calculation_versions: Mapped[list["CalculationVersion"]] = relationship(
        back_populates="voyage", cascade="all, delete-orphan"
    )
    manual_overrides: Mapped[list["ManualOverride"]] = relationship(back_populates="voyage", cascade="all, delete-orphan")


class PortCall(Base):
    __tablename__ = "port_calls"

    id: Mapped[str] = mapped_column(String, primary_key=True, default=_uuid)
    voyage_id: Mapped[str] = mapped_column(ForeignKey("voyages.id"))
    sequence_no: Mapped[int] = mapped_column(default=1)
    port: Mapped[str | None] = mapped_column(String, nullable=True)
    terminal: Mapped[str | None] = mapped_column(String, nullable=True)
    berth: Mapped[str | None] = mapped_column(String, nullable=True)
    operation_type: Mapped[str] = mapped_column(String, default="LOADING")

    voyage: Mapped[Voyage] = relationship(back_populates="port_calls")
    sof_events: Mapped[list["SOFEvent"]] = relationship(back_populates="port_call", cascade="all, delete-orphan")


class Document(Base):
    __tablename__ = "documents"

    id: Mapped[str] = mapped_column(String, primary_key=True, default=_uuid)
    voyage_id: Mapped[str] = mapped_column(ForeignKey("voyages.id"))
    type: Mapped[str] = mapped_column(String)
    filename: Mapped[str] = mapped_column(String)
    storage_uri: Mapped[str] = mapped_column(String)
    mime_type: Mapped[str | None] = mapped_column(String, nullable=True)
    page_count: Mapped[int | None] = mapped_column(nullable=True)
    extraction_method: Mapped[str | None] = mapped_column(String, nullable=True)
    extracted_text: Mapped[str | None] = mapped_column(String, nullable=True)
    status: Mapped[str] = mapped_column(String, default="UPLOADED")
    uploaded_by: Mapped[str | None] = mapped_column(String, nullable=True)
    uploaded_at: Mapped[datetime] = mapped_column(server_default=func.now())
    sha256_hash: Mapped[str | None] = mapped_column(String, nullable=True)

    voyage: Mapped[Voyage] = relationship(back_populates="documents")


class SOFEvent(Base):
    __tablename__ = "sof_events"

    id: Mapped[str] = mapped_column(String, primary_key=True, default=_uuid)
    port_call_id: Mapped[str] = mapped_column(ForeignKey("port_calls.id"))
    document_id: Mapped[str | None] = mapped_column(ForeignKey("documents.id"), nullable=True)
    page_number: Mapped[int | None] = mapped_column(nullable=True)

    category: Mapped[str] = mapped_column(String)
    subtype: Mapped[str | None] = mapped_column(String, nullable=True)
    start_time: Mapped[datetime] = mapped_column()
    end_time: Mapped[datetime | None] = mapped_column(nullable=True)

    source_text: Mapped[str | None] = mapped_column(String, nullable=True)
    confidence_score: Mapped[float | None] = mapped_column(nullable=True)
    confidence_status: Mapped[str] = mapped_column(String, default="NEEDS_REVIEW")
    status: Mapped[str] = mapped_column(String, default="EXTRACTED")
    parent_event_id: Mapped[str | None] = mapped_column(String, nullable=True)
    comment: Mapped[str | None] = mapped_column(String, nullable=True)

    created_at: Mapped[datetime] = mapped_column(server_default=func.now())
    updated_at: Mapped[datetime] = mapped_column(server_default=func.now(), onupdate=func.now())

    port_call: Mapped[PortCall] = relationship(back_populates="sof_events")
    evidence: Mapped[list["EventEvidence"]] = relationship(back_populates="sof_event", cascade="all, delete-orphan")


class EventEvidence(Base):
    __tablename__ = "event_evidence"

    id: Mapped[str] = mapped_column(String, primary_key=True, default=_uuid)
    sof_event_id: Mapped[str] = mapped_column(ForeignKey("sof_events.id"))
    field_changed: Mapped[str] = mapped_column(String)
    previous_value: Mapped[str | None] = mapped_column(String, nullable=True)
    new_value: Mapped[str | None] = mapped_column(String, nullable=True)
    changed_by: Mapped[str] = mapped_column(String)
    changed_at: Mapped[datetime] = mapped_column(server_default=func.now())
    reason: Mapped[str | None] = mapped_column(String, nullable=True)

    sof_event: Mapped[SOFEvent] = relationship(back_populates="evidence")


rule_set_version_rules = Table(
    "rule_set_version_rules",
    Base.metadata,
    Column("rule_set_version_id", ForeignKey("rule_set_versions.id"), primary_key=True),
    Column("rule_version_id", ForeignKey("rule_versions.id"), primary_key=True),
)


class RuleVersion(Base):
    __tablename__ = "rule_versions"

    id: Mapped[str] = mapped_column(String, primary_key=True, default=_uuid)
    rule_definition_code: Mapped[str] = mapped_column(String)
    name: Mapped[str] = mapped_column(String)
    version_no: Mapped[int] = mapped_column(default=1)
    description: Mapped[str | None] = mapped_column(String, nullable=True)

    conditions: Mapped[dict | None] = mapped_column(JSONB, nullable=True)
    exceptions: Mapped[dict | None] = mapped_column(JSONB, nullable=True)
    parameters: Mapped[dict] = mapped_column(JSONB, default=dict)

    time_count_factor: Mapped[Decimal] = mapped_column(Numeric(5, 4))
    demurrage_rate_factor: Mapped[Decimal] = mapped_column(Numeric(5, 4))
    priority: Mapped[int] = mapped_column(default=0)
    scope: Mapped[str] = mapped_column(String, default="MANUAL")
    scope_ref_id: Mapped[str | None] = mapped_column(String, nullable=True)

    source_document_id: Mapped[str | None] = mapped_column(String, nullable=True)
    source_clause_id: Mapped[str | None] = mapped_column(String, nullable=True)
    source_page: Mapped[int | None] = mapped_column(nullable=True)
    source_note: Mapped[str | None] = mapped_column(String, nullable=True)

    status: Mapped[str] = mapped_column(String, default="ACTIVE")
    supersedes_version_id: Mapped[str | None] = mapped_column(String, nullable=True)
    requires_manual_confirmation: Mapped[bool] = mapped_column(default=False)

    created_by: Mapped[str | None] = mapped_column(String, nullable=True)
    created_at: Mapped[datetime] = mapped_column(server_default=func.now())


class RuleSetVersion(Base):
    __tablename__ = "rule_set_versions"

    id: Mapped[str] = mapped_column(String, primary_key=True, default=_uuid)
    name: Mapped[str] = mapped_column(String)
    version_no: Mapped[int] = mapped_column(default=1)
    status: Mapped[str] = mapped_column(String, default="ACTIVE")
    created_at: Mapped[datetime] = mapped_column(server_default=func.now())

    rules: Mapped[list[RuleVersion]] = relationship(secondary=rule_set_version_rules)


class CalculationVersion(Base):
    """Append-only snapshot of one deterministic engine run (RULE 7)."""

    __tablename__ = "calculation_versions"

    id: Mapped[str] = mapped_column(String, primary_key=True, default=_uuid)
    voyage_id: Mapped[str] = mapped_column(ForeignKey("voyages.id"))
    version_no: Mapped[int] = mapped_column(default=1)
    kind: Mapped[str] = mapped_column(String, default="SW")

    rule_set_version_id: Mapped[str] = mapped_column(ForeignKey("rule_set_versions.id"))
    event_snapshot_ids: Mapped[list[str]] = mapped_column(JSONB, default=list)
    manual_override_ids: Mapped[list[str]] = mapped_column(JSONB, default=list)
    calculation_engine_version: Mapped[str] = mapped_column(String, default="0.1.0")

    results: Mapped[dict] = mapped_column(JSONB)  # commencement, intervals, laytime, demurrage
    integrity_ok: Mapped[bool] = mapped_column(default=False)
    status: Mapped[str] = mapped_column(String, default="CALCULATED")

    created_by: Mapped[str | None] = mapped_column(String, nullable=True)
    created_at: Mapped[datetime] = mapped_column(server_default=func.now())

    voyage: Mapped[Voyage] = relationship(back_populates="calculation_versions")


class ManualOverride(Base):
    __tablename__ = "manual_overrides"

    id: Mapped[str] = mapped_column(String, primary_key=True, default=_uuid)
    voyage_id: Mapped[str] = mapped_column(ForeignKey("voyages.id"))
    target_type: Mapped[str] = mapped_column(String, default="ATOMIC_INTERVAL")
    target_key: Mapped[str] = mapped_column(String)

    original_value: Mapped[dict] = mapped_column(JSONB)
    new_time_count_factor: Mapped[Decimal | None] = mapped_column(Numeric(5, 4), nullable=True)
    new_demurrage_rate_factor: Mapped[Decimal | None] = mapped_column(Numeric(5, 4), nullable=True)

    reason: Mapped[str] = mapped_column(String)
    supporting_clause_id: Mapped[str | None] = mapped_column(String, nullable=True)
    comment: Mapped[str | None] = mapped_column(String, nullable=True)

    superseded_by: Mapped[str | None] = mapped_column(String, nullable=True)

    created_by: Mapped[str] = mapped_column(String)
    created_at: Mapped[datetime] = mapped_column(server_default=func.now())

    voyage: Mapped[Voyage] = relationship(back_populates="manual_overrides")


class AuditLog(Base):
    __tablename__ = "audit_log"

    id: Mapped[str] = mapped_column(String, primary_key=True, default=_uuid)
    entity_type: Mapped[str] = mapped_column(String)
    entity_id: Mapped[str] = mapped_column(String)
    user_id: Mapped[str | None] = mapped_column(String, nullable=True)
    timestamp: Mapped[datetime] = mapped_column(server_default=func.now())
    field: Mapped[str | None] = mapped_column(String, nullable=True)
    previous_value: Mapped[str | None] = mapped_column(String, nullable=True)
    new_value: Mapped[str | None] = mapped_column(String, nullable=True)
    reason: Mapped[str | None] = mapped_column(String, nullable=True)
    time_impact: Mapped[str | None] = mapped_column(String, nullable=True)
    financial_impact: Mapped[Decimal | None] = mapped_column(Numeric(14, 2), nullable=True)
    rule_version_id: Mapped[str | None] = mapped_column(String, nullable=True)
    calculation_version_id: Mapped[str | None] = mapped_column(String, nullable=True)
