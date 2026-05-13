from datetime import datetime
"""Customer-facing API to submit a project for execution and poll RunCard status."""

import uuid
from typing import Annotated

from fastapi import APIRouter, Depends, HTTPException, status
from pydantic import BaseModel
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.auth.deps import CurrentUser
from app.infra.db.base import get_db
from app.infra.db.models import Project, ProjectVersion, RunCard, StateTransition

router = APIRouter(prefix="/projects/{project_id}/runcards", tags=["runcards"])


class RunCardResponse(BaseModel):
    id: uuid.UUID
    kind: str
    current_state: str
    plan_steps: list
    plan_progress: int
    created_at: datetime

    model_config = {"from_attributes": True}


@router.post("", response_model=RunCardResponse, status_code=status.HTTP_201_CREATED)
async def submit_project(
    project_id: uuid.UUID,
    user: CurrentUser,
    db: Annotated[AsyncSession, Depends(get_db)],
):
    result = await db.execute(select(Project).where(Project.id == project_id, Project.owner_id == user.id))
    project = result.scalar_one_or_none()
    if not project:
        raise HTTPException(status_code=404, detail="Project not found")
    if project.status not in ("draft", "req_ready"):
        raise HTTPException(status_code=409, detail="Project already submitted")

    version_result = await db.execute(
        select(ProjectVersion).where(ProjectVersion.id == project.current_version_id)
    )
    version = version_result.scalar_one_or_none()
    if not version:
        raise HTTPException(status_code=422, detail="No project version found")

    runcard = RunCard(
        project_id=project_id,
        project_version_id=version.id,
        kind="main",
        current_state="REQ_READY",
        data_context={},
    )
    db.add(runcard)
    project.status = "running"
    await db.flush()

    # Dispatch to Celery
    from app.workers.tasks.autoda import run_autoda_l1
    run_autoda_l1.delay(str(runcard.id), str(project_id))

    return runcard


@router.get("", response_model=list[RunCardResponse])
async def list_runcards(
    project_id: uuid.UUID,
    user: CurrentUser,
    db: Annotated[AsyncSession, Depends(get_db)],
):
    proj = await db.execute(select(Project).where(Project.id == project_id, Project.owner_id == user.id))
    if not proj.scalar_one_or_none():
        raise HTTPException(status_code=404, detail="Project not found")

    result = await db.execute(
        select(RunCard)
        .where(RunCard.project_id == project_id)
        .order_by(RunCard.created_at.desc())
    )
    return result.scalars().all()


@router.get("/{runcard_id}", response_model=RunCardResponse)
async def get_runcard(
    project_id: uuid.UUID,
    runcard_id: uuid.UUID,
    user: CurrentUser,
    db: Annotated[AsyncSession, Depends(get_db)],
):
    result = await db.execute(
        select(RunCard).where(RunCard.id == runcard_id, RunCard.project_id == project_id)
    )
    runcard = result.scalar_one_or_none()
    if not runcard:
        raise HTTPException(status_code=404, detail="RunCard not found")
    return runcard
