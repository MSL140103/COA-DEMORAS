from __future__ import annotations

import itertools
from datetime import datetime

from app.domain.facts.models import SOFEvent, SOFEventStatus

_counter = itertools.count(1)


def make_event(
    category: str,
    start: datetime,
    end: datetime | None = None,
    *,
    status: SOFEventStatus = SOFEventStatus.CONFIRMED,
    port_call_id: str = "PC1",
    event_id: str | None = None,
) -> SOFEvent:
    return SOFEvent(
        id=event_id or f"EV{next(_counter)}",
        port_call_id=port_call_id,
        category=category,
        start_time=start,
        end_time=end,
        status=status,
    )
