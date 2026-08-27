from __future__ import annotations

from sqlalchemy import select
from sqlalchemy.orm import Session

from app.domain.rules.seed import base_rule_set
from app.infrastructure.db import models as orm

SEED_RULE_SET_NAME = "MVP1 Seed Base Rule Set"


def ensure_seed_rule_set(db: Session) -> orm.RuleSetVersion:
    """Idempotently materialize the MVP1 provisional rule set in the DB.

    Returns the existing row if already seeded — never creates duplicates, and never
    mutates a RuleSetVersion that a CalculationVersion may already reference.
    """
    existing = db.scalar(select(orm.RuleSetVersion).where(orm.RuleSetVersion.name == SEED_RULE_SET_NAME))
    if existing is not None:
        return existing

    domain_set = base_rule_set()
    rule_rows = []
    for rule in domain_set.rules:
        row = orm.RuleVersion(
            id=rule.id,
            rule_definition_code=rule.rule_definition_code,
            name=rule.name,
            version_no=rule.version_no,
            description=rule.description,
            conditions=rule.conditions,
            exceptions=rule.exceptions,
            parameters=rule.parameters,
            time_count_factor=rule.time_count_factor,
            demurrage_rate_factor=rule.demurrage_rate_factor,
            priority=rule.priority,
            scope=rule.scope.value,
            scope_ref_id=rule.scope_ref_id,
            source_document_id=rule.source_document_id,
            source_clause_id=rule.source_clause_id,
            source_page=rule.source_page,
            source_note=rule.source_note,
            status=rule.status.value,
            supersedes_version_id=rule.supersedes_version_id,
            requires_manual_confirmation=rule.requires_manual_confirmation,
        )
        db.add(row)
        rule_rows.append(row)

    rule_set_row = orm.RuleSetVersion(
        id=domain_set.id,
        name=domain_set.name,
        version_no=domain_set.version_no,
        status=domain_set.status.value,
        rules=rule_rows,
    )
    db.add(rule_set_row)
    db.commit()
    db.refresh(rule_set_row)
    return rule_set_row
