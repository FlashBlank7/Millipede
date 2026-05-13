"""
Persist state transitions to Postgres and publish events to Redis.
"""

import uuid
from datetime import datetime, timezone

from sqlalchemy import select
from sqlalchemy.orm import Session

from app.infra.db.models import ExecutionEvent, RunCard, StateTransition


def record_transition(
    db: Session,
    runcard_id: uuid.UUID,
    from_state: str | None,
    to_state: str,
    trigger: str,
    actor_id: uuid.UUID | None = None,
    payload: dict | None = None,
) -> None:
    transition = StateTransition(
        runcard_id=runcard_id,
        from_state=from_state,
        to_state=to_state,
        trigger=trigger,
        actor_id=actor_id,
        payload=payload or {},
    )
    db.add(transition)

    runcard = db.execute(select(RunCard).where(RunCard.id == runcard_id)).scalar_one()
    runcard.current_state = to_state
    db.flush()


def record_execution_event(
    db: Session,
    runcard_id: uuid.UUID,
    event_type: str,
    payload: dict,
) -> None:
    event = ExecutionEvent(
        runcard_id=runcard_id,
        event_type=event_type,
        payload=payload,
    )
    db.add(event)
    db.flush()
