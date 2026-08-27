"""ORM <-> domain object mappers. Keeps app.domain free of any SQLAlchemy import
(RULE 8's "no AI/network dependency" boundary extends naturally to "no DB dependency
either" — the domain engine must stay independently testable and reproducible)."""
from __future__ import annotations

from app.domain.facts.models import SOFEvent as DomainSOFEvent
from app.domain.rules.models import RuleSetVersion as DomainRuleSetVersion
from app.domain.rules.models import RuleVersion as DomainRuleVersion
from app.infrastructure.db import models as orm


def sof_event_to_domain(row: orm.SOFEvent) -> DomainSOFEvent:
    return DomainSOFEvent(
        id=row.id,
        port_call_id=row.port_call_id,
        category=row.category,
        subtype=row.subtype,
        start_time=row.start_time,
        end_time=row.end_time,
        source_text=row.source_text,
        document_id=row.document_id,
        page_number=row.page_number,
        confidence_score=row.confidence_score,
        confidence_status=row.confidence_status,
        status=row.status,
        parent_event_id=row.parent_event_id,
        comment=row.comment,
    )


def rule_version_to_domain(row: orm.RuleVersion) -> DomainRuleVersion:
    return DomainRuleVersion(
        id=row.id,
        rule_definition_code=row.rule_definition_code,
        name=row.name,
        version_no=row.version_no,
        description=row.description,
        conditions=row.conditions,
        exceptions=row.exceptions,
        parameters=row.parameters or {},
        time_count_factor=row.time_count_factor,
        demurrage_rate_factor=row.demurrage_rate_factor,
        priority=row.priority,
        scope=row.scope,
        scope_ref_id=row.scope_ref_id,
        source_document_id=row.source_document_id,
        source_clause_id=row.source_clause_id,
        source_page=row.source_page,
        source_note=row.source_note,
        status=row.status,
        supersedes_version_id=row.supersedes_version_id,
        requires_manual_confirmation=row.requires_manual_confirmation,
    )


def rule_set_version_to_domain(row: orm.RuleSetVersion) -> DomainRuleSetVersion:
    return DomainRuleSetVersion(
        id=row.id,
        name=row.name,
        version_no=row.version_no,
        rules=[rule_version_to_domain(r) for r in row.rules],
        status=row.status,
    )
