"""Laytime commencement determination — SYSTEM_ARCHITECTURE.md section 9, brief
section 11 ("NOR + 6").

A small, standalone, deterministic sub-module: given the candidate trigger events and
an allowance, it picks the commencement timestamp and records *why* — every candidate
considered, not just the winner — so the UI can render exactly the
    NOR: ... / NOR + 6: ... / Securely Moored: ... / Selected: ... / Rule: ...
block from the brief.
"""
from __future__ import annotations

from dataclasses import dataclass
from datetime import datetime, timedelta
from decimal import Decimal
from typing import Literal


class CommencementUndetermined(ValueError):
    """UNKNOWN / REVIEW REQUIRED — never guess a commencement time."""


@dataclass
class CommencementCandidate:
    label: str
    time: datetime | None
    rule_id: str


@dataclass
class CommencementDetermination:
    candidates: list[CommencementCandidate]
    selected: datetime
    selected_label: str
    rule_applied: str


def determine_commencement(
    *,
    nor_tendered: datetime | None,
    securely_moored: datetime | None,
    allowance_hours: Decimal,
    selection: Literal["EARLIEST", "LATEST"] = "EARLIEST",
) -> CommencementDetermination:
    candidates: list[CommencementCandidate] = []
    if nor_tendered is not None:
        candidates.append(
            CommencementCandidate(
                label=f"NOR + {allowance_hours}h",
                time=nor_tendered + timedelta(hours=float(allowance_hours)),
                rule_id="NOR_ALLOWANCE",
            )
        )
    if securely_moored is not None:
        candidates.append(
            CommencementCandidate(
                label="Securely Moored",
                time=securely_moored,
                rule_id="SECURELY_MOORED_TRIGGER",
            )
        )

    valid = [c for c in candidates if c.time is not None]
    if not valid:
        raise CommencementUndetermined(
            "UNKNOWN / REVIEW REQUIRED — cannot determine laytime commencement: "
            "neither NOR Tendered nor Securely Moored is available"
        )

    chosen = min(valid, key=lambda c: c.time) if selection == "EARLIEST" else max(valid, key=lambda c: c.time)
    which = "First" if selection == "EARLIEST" else "Last"
    return CommencementDetermination(
        candidates=candidates,
        selected=chosen.time,
        selected_label=chosen.label,
        rule_applied=f"{chosen.rule_id} / Whichever Occurs {which}",
    )
