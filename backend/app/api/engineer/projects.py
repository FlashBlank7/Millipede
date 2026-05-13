from datetime import datetime
import uuid
from typing import Annotated

from fastapi import APIRouter, Depends, HTTPException
from pydantic import BaseModel
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.auth.deps import EngineerUser
from app.infra.db.base import get_db
from app.infra.db.models import Project, RunCard

router = APIRouter(prefix="/engineer/projects", tags=["engineer-projects"])


class ProjectCardResponse(BaseModel):
    id: uuid.UUID
    product_type: str
    task_level: str
    status: str
    owner_id: uuid.UUID
    current_state: str | None = None
    created_at: datetime

    model_config = {"from_attributes": True}


@router.get("", response_model=list[ProjectCardResponse])
async def list_all_projects(
    user: EngineerUser,
    db: Annotated[AsyncSession, Depends(get_db)],
    status: str | None = None,
    product_type: str | None = None,
):
    q = select(Project).where(Project.archived_at.is_(None))
    if status:
        q = q.where(Project.status == status)
    if product_type:
        q = q.where(Project.product_type == product_type)
    q = q.order_by(Project.created_at.desc())

    result = await db.execute(q)
    projects = result.scalars().all()

    cards = []
    for p in projects:
        runcard_result = await db.execute(
            select(RunCard)
            .where(RunCard.project_id == p.id, RunCard.kind == "main")
            .order_by(RunCard.created_at.desc())
            .limit(1)
        )
        runcard = runcard_result.scalar_one_or_none()
        cards.append(ProjectCardResponse(
            id=p.id,
            product_type=p.product_type,
            task_level=p.task_level,
            status=p.status,
            owner_id=p.owner_id,
            current_state=runcard.current_state if runcard else None,
            created_at=p.created_at.isoformat(),
        ))
    return cards
