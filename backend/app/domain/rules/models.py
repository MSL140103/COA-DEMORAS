"""Rules layer — how the contract treats a fact. Versioned, sourced, never hardcoded
math. See SYSTEM_ARCHITECTURE.md sections 2.4, 11, 12, 13.
"""
from __future__ import annotations

from decimal import Decimal
from enum import Enum
from typing import Any, Optional

from pydantic import BaseModel, model_validator


class RuleScope(str, Enum):
    GLOBAL = "GLOBAL"
    CONTRACT = "CONTRACT"
    COA = "COA"
    RECAP = "RECAP"
    COUNTERPARTY = "COUNTERPARTY"
    COUNTRY = "COUNTRY"
    PORT = "PORT"
    TERMINAL = "TERMINAL"
    VOYAGE = "VOYAGE"
    MANUAL = "MANUAL"


# Lower number = more specific = wins a priority tie in resolve_precedence().
SCOPE_SPECIFICITY: dict[RuleScope, int] = {
    RuleScope.VOYAGE: 0,
    RuleScope.TERMINAL: 1,
    RuleScope.PORT: 2,
    RuleScope.COUNTRY: 3,
    RuleScope.COUNTERPARTY: 4,
    RuleScope.RECAP: 5,
    RuleScope.COA: 6,
    RuleScope.CONTRACT: 7,
    RuleScope.MANUAL: 8,
    RuleScope.GLOBAL: 9,
}
# CONTRACTUAL DECISION REQUIRED (SYSTEM_ARCHITECTURE.md sections 15 & 29 item 5):
# this ordering is a reasonable default, not an assumed-correct legal hierarchy.
# It is intentionally a plain module-level table (not buried in the evaluator) so it
# can be swapped for a configurable ScopePrecedenceConfig without touching engine code.


class RuleStatus(str, Enum):
    DRAFT = "DRAFT"
    TESTING = "TESTING"
    ACTIVE = "ACTIVE"
    INACTIVE = "INACTIVE"
    SUPERSEDED = "SUPERSEDED"
    ARCHIVED = "ARCHIVED"


class RuleVersion(BaseModel):
    """One immutable version of a rule. Editing an ACTIVE rule must create a new
    RuleVersion (version_no + 1) — never mutate one that a Calculation may already
    reference (RULE 6, RULE 7).
    """

    id: str
    rule_definition_code: str  # stable rule *type*, e.g. "WEATHER_WINDOW" — never "WEATHER_50PCT"
    name: str
    version_no: int = 1
    description: Optional[str] = None

    # Condition AST — see app.domain.rules.conditions. None => never auto-matches
    # (reserved for the implicit DEFAULT_COUNT fallback, so a real rule always has
    # explicit conditions).
    conditions: Optional[dict[str, Any]] = None
    exceptions: Optional[dict[str, Any]] = None
    parameters: dict[str, Any] = {}

    time_count_factor: Decimal
    demurrage_rate_factor: Decimal
    priority: int = 0
    scope: RuleScope = RuleScope.GLOBAL
    scope_ref_id: Optional[str] = None

    effective_from: Optional[str] = None
    effective_to: Optional[str] = None

    source_document_id: Optional[str] = None
    source_clause_id: Optional[str] = None
    source_page: Optional[int] = None
    source_note: Optional[str] = None

    status: RuleStatus = RuleStatus.ACTIVE
    supersedes_version_id: Optional[str] = None
    requires_manual_confirmation: bool = False

    @model_validator(mode="after")
    def _no_rule_without_source(self) -> "RuleVersion":
        # RULE 4 / brief section 56: "NO RULE WITHOUT SOURCE" — materialized as a
        # hard model constraint, not just a UI warning. scope=MANUAL is the explicit
        # escape hatch for provisional/system rules (e.g. seed defaults) and must
        # carry a source_note explaining why no document citation exists.
        if self.scope != RuleScope.MANUAL and not self.source_clause_id:
            raise ValueError(
                f"RuleVersion {self.id} ({self.rule_definition_code}): "
                "SOURCE NOT LINKED — source_clause_id is required unless scope=MANUAL"
            )
        if self.scope == RuleScope.MANUAL and not self.source_note:
            raise ValueError(
                f"RuleVersion {self.id}: scope=MANUAL rules must explain themselves via source_note"
            )
        return self


class RuleSetVersion(BaseModel):
    """A frozen snapshot of which RuleVersions compose a rule set (brief section 44-45,
    SYSTEM_ARCHITECTURE.md section 2.4). A CalculationVersion always points at one of
    these, never at "whatever is active today" — that's what makes historical
    calculations reproducible (RULE 7).
    """

    id: str
    name: str
    version_no: int = 1
    rules: list[RuleVersion] = []
    status: RuleStatus = RuleStatus.ACTIVE
