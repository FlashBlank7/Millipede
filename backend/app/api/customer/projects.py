from datetime import datetime
import uuid
from typing import Annotated

from fastapi import APIRouter, Depends, HTTPException, status
from pydantic import BaseModel
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.auth.deps import CurrentUser
from app.infra.db.base import get_db
from app.infra.db.models import Project, ProjectVersion, Requirement, RunCard

router = APIRouter(prefix="/projects", tags=["customer-projects"])


class CreateProjectRequest(BaseModel):
    product_type: str  # autoda | automl
    task_level: str = "L2"
    goal: dict
    expected_outputs: list = []
    success_metric: dict | None = None
    constraints: dict = {}
    raw_dialogue: str | None = None


class ProjectResponse(BaseModel):
    id: uuid.UUID
    product_type: str
    task_level: str
    status: str
    current_version_id: uuid.UUID | None
    created_at: datetime

    model_config = {"from_attributes": True}


@router.post("", response_model=ProjectResponse, status_code=status.HTTP_201_CREATED)
async def create_project(
    body: CreateProjectRequest,
    user: CurrentUser,
    db: Annotated[AsyncSession, Depends(get_db)],
):
    if body.product_type not in ("autoda", "automl"):
        raise HTTPException(status_code=400, detail="Invalid product_type")
    if body.task_level not in ("L1", "L2", "L3"):
        raise HTTPException(status_code=400, detail="Invalid task_level")

    project = Project(
        org_id=user.org_id,
        owner_id=user.id,
        product_type=body.product_type,
        task_level=body.task_level,
        status="draft",
    )
    db.add(project)
    await db.flush()

    version = ProjectVersion(
        project_id=project.id,
        version_number=1,
        snapshot_manifest={},
        created_by=user.id,
    )
    db.add(version)
    await db.flush()

    project.current_version_id = version.id

    requirement = Requirement(
        project_id=project.id,
        goal=body.goal,
        expected_outputs=body.expected_outputs,
        success_metric=body.success_metric,
        constraints=body.constraints,
        raw_dialogue=body.raw_dialogue,
    )
    db.add(requirement)

    return project


@router.get("", response_model=list[ProjectResponse])
async def list_projects(user: CurrentUser, db: Annotated[AsyncSession, Depends(get_db)]):
    result = await db.execute(
        select(Project)
        .where(Project.owner_id == user.id, Project.archived_at.is_(None))
        .order_by(Project.created_at.desc())
    )
    return result.scalars().all()


@router.get("/{project_id}", response_model=ProjectResponse)
async def get_project(project_id: uuid.UUID, user: CurrentUser, db: Annotated[AsyncSession, Depends(get_db)]):
    result = await db.execute(select(Project).where(Project.id == project_id, Project.owner_id == user.id))
    project = result.scalar_one_or_none()
    if not project:
        raise HTTPException(status_code=404, detail="Project not found")
    return project
