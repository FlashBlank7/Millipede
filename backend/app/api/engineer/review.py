from datetime import datetime
"""
Engineer review API — Phase 1 scope:
  - List runcards awaiting review (AWAIT_REVIEW_DA_REPORT)
  - GET stage output for a runcard
  - POST review action: accept | modify | reject
  - POST dispatch: advance from AWAIT_DISPATCH_DA_REPORT → PACKAGING
"""

import uuid
from typing import Annotated

from fastapi import APIRouter, Depends, HTTPException
from pydantic import BaseModel
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.auth.deps import EngineerUser
from app.infra.db.base import get_db
from app.infra.db.models import (
    Project,
    ReviewRecord,
    RunCard,
    StageOutput,
    StateTransition,
)
from app.infra.eventbus.redis_bus import publish, project_channel, runcard_channel
from app.orchestration.state_machine.autoda import AutoDAStateMachine

router = APIRouter(prefix="/engineer/reviews", tags=["engineer-reviews"])


class StageOutputResponse(BaseModel):
    id: uuid.UUID
    stage_name: str
    output_type: str
    content: dict
    is_human_modified: bool
    created_at: datetime

    model_config = {"from_attributes": True}


class ReviewActionRequest(BaseModel):
    action: str  # accept | modify | reject
    comment: str | None = None
    modifications: dict | None = None  # for modify action


class RunCardReviewResponse(BaseModel):
    id: uuid.UUID
    project_id: uuid.UUID
    current_state: str
    kind: str
    created_at: datetime

    model_config = {"from_attributes": True}


@router.get("", response_model=list[RunCardReviewResponse])
async def list_pending_reviews(
    user: EngineerUser,
    db: Annotated[AsyncSession, Depends(get_db)],
):
    """List all runcards currently in an AWAIT_REVIEW_* state."""
    result = await db.execute(
        select(RunCard).where(
            RunCard.current_state.like("AWAIT_REVIEW_%")
        ).order_by(RunCard.created_at.asc())
    )
    return result.scalars().all()


@router.get("/{runcard_id}/outputs", response_model=list[StageOutputResponse])
async def get_stage_outputs(
    runcard_id: uuid.UUID,
    user: EngineerUser,
    db: Annotated[AsyncSession, Depends(get_db)],
):
    """Get all stage outputs for a runcard (for review)."""
    result = await db.execute(
        select(StageOutput)
        .where(
            StageOutput.runcard_id == runcard_id,
            StageOutput.superseded_by.is_(None),
        )
        .order_by(StageOutput.created_at.asc())
    )
    return result.scalars().all()


@router.post("/{runcard_id}/action")
async def submit_review_action(
    runcard_id: uuid.UUID,
    body: ReviewActionRequest,
    user: EngineerUser,
    db: Annotated[AsyncSession, Depends(get_db)],
):
    """Submit a review decision for a runcard in AWAIT_REVIEW_* state."""
    if body.action not in ("accept", "modify", "reject"):
        raise HTTPException(status_code=400, detail="action must be accept | modify | reject")

    runcard = await _get_runcard(runcard_id, db)
    if not runcard.current_state.startswith("AWAIT_REVIEW_"):
        raise HTTPException(status_code=409, detail=f"RunCard is in state {runcard.current_state}, not awaiting review")

    project = await db.get(Project, runcard.project_id)

    # Get the latest stage output to attach the review record to
    output_result = await db.execute(
        select(StageOutput)
        .where(StageOutput.runcard_id == runcard_id, StageOutput.superseded_by.is_(None))
        .order_by(StageOutput.created_at.desc())
        .limit(1)
    )
    latest_output = output_result.scalar_one_or_none()
    if not latest_output:
        raise HTTPException(status_code=422, detail="No stage output found to review")

    # Handle modify: create new output, mark old as superseded
    if body.action == "modify" and body.modifications:
        new_output = StageOutput(
            runcard_id=runcard_id,
            stage_name=latest_output.stage_name,
            output_type=latest_output.output_type,
            content={**latest_output.content, **body.modifications},
            is_human_modified=True,
        )
        db.add(new_output)
        await db.flush()
        latest_output.superseded_by = new_output.id
        review_output_id = new_output.id
    else:
        review_output_id = latest_output.id

    # Write review record
    review = ReviewRecord(
        runcard_id=runcard_id,
        stage_output_id=review_output_id,
        review_node=runcard.current_state,
        action=body.action,
        reviewer_id=user.id,
        comment=body.comment,
        modifications=body.modifications,
    )
    db.add(review)

    sm = AutoDAStateMachine(runcard.current_state, task_level=project.task_level)
    from_state = runcard.current_state

    if body.action in ("accept", "modify"):
        # Accept/modify → advance to AWAIT_DISPATCH_*
        sm.dispatch_report()
        trigger = "review_pass" if body.action == "accept" else "review_modify"
    else:
        # Reject → back to DATA_ANALYZING (re-run)
        # For Phase 1 we simply mark failed and let engineer resubmit
        # Full rollback + re-run is Phase 2
        sm._sm_state = "DATA_ANALYZING"
        trigger = "review_reject"

    runcard.current_state = sm.state
    transition = StateTransition(
        runcard_id=runcard_id,
        from_state=from_state,
        to_state=sm.state,
        trigger=trigger,
        actor_id=user.id,
        payload={"comment": body.comment},
    )
    db.add(transition)
    await db.commit()

    await publish(runcard_channel(str(runcard_id)), "runcard.state_changed", {
        "from": from_state, "to": sm.state, "trigger": trigger, "actor": str(user.id),
    })
    await publish(project_channel(str(runcard.project_id)), "project.runcard_updated", {
        "runcard_id": str(runcard_id), "state": sm.state,
    })

    return {"status": "ok", "new_state": sm.state}


@router.post("/{runcard_id}/dispatch")
async def dispatch_runcard(
    runcard_id: uuid.UUID,
    user: EngineerUser,
    db: Annotated[AsyncSession, Depends(get_db)],
):
    """Confirm dispatch — advance from AWAIT_DISPATCH_* → PACKAGING (triggers Celery packaging task)."""
    runcard = await _get_runcard(runcard_id, db)
    if not runcard.current_state.startswith("AWAIT_DISPATCH_"):
        raise HTTPException(status_code=409, detail=f"RunCard is in state {runcard.current_state}, not awaiting dispatch")

    project = await db.get(Project, runcard.project_id)
    sm = AutoDAStateMachine(runcard.current_state, task_level=project.task_level)
    from_state = runcard.current_state

    sm.confirm_dispatch()

    runcard.current_state = sm.state  # PACKAGING
    transition = StateTransition(
        runcard_id=runcard_id,
        from_state=from_state,
        to_state=sm.state,
        trigger="dispatch",
        actor_id=user.id,
    )
    db.add(transition)
    await db.commit()

    # Trigger packaging via Celery
    from app.workers.tasks.packaging import run_packaging
    run_packaging.delay(str(runcard_id), str(runcard.project_id))

    await publish(runcard_channel(str(runcard_id)), "runcard.state_changed", {
        "from": from_state, "to": sm.state, "trigger": "dispatch",
    })

    return {"status": "ok", "new_state": sm.state}


async def _get_runcard(runcard_id: uuid.UUID, db: AsyncSession) -> RunCard:
    runcard = await db.get(RunCard, runcard_id)
    if not runcard:
        raise HTTPException(status_code=404, detail="RunCard not found")
    return runcard
