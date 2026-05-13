import hashlib
import io
import uuid
from typing import Annotated

import pandas as pd
from fastapi import APIRouter, Depends, File, HTTPException, UploadFile, status
from pydantic import BaseModel
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.auth.deps import CurrentUser
from app.infra.db.base import get_db
from app.infra.db.models import DataUpload, Project
from app.infra.storage.client import get_storage

router = APIRouter(prefix="/projects/{project_id}/uploads", tags=["uploads"])

ALLOWED_MIME_TYPES = {
    "text/csv",
    "application/vnd.ms-excel",
    "application/vnd.openxmlformats-officedocument.spreadsheetml.sheet",
    "application/pdf",
}
MAX_SIZE_BYTES = 500 * 1024 * 1024  # 500MB


class UploadResponse(BaseModel):
    id: uuid.UUID
    original_filename: str
    mime_type: str
    size_bytes: int
    fingerprint: str
    storage_uri: str

    model_config = {"from_attributes": True}


def _compute_fingerprint(content: bytes, schema_summary: dict | None) -> str:
    file_hash = hashlib.sha256(content).hexdigest()[:16]
    schema_hash = hashlib.sha256(str(schema_summary).encode()).hexdigest()[:8] if schema_summary else "unknown"
    row_count = schema_summary.get("row_count", 0) if schema_summary else 0
    return f"{file_hash}:{schema_hash}:{row_count}"


def _extract_schema_summary(content: bytes, mime_type: str) -> dict | None:
    try:
        if mime_type == "text/csv":
            df = pd.read_csv(io.BytesIO(content), nrows=0)
            full_df = pd.read_csv(io.BytesIO(content))
            return {
                "columns": [{"name": c, "dtype": str(t)} for c, t in zip(df.columns, full_df.dtypes)],
                "row_count": len(full_df),
                "column_count": len(df.columns),
            }
        elif mime_type in (
            "application/vnd.ms-excel",
            "application/vnd.openxmlformats-officedocument.spreadsheetml.sheet",
        ):
            full_df = pd.read_excel(io.BytesIO(content))
            return {
                "columns": [{"name": c, "dtype": str(t)} for c, t in zip(full_df.columns, full_df.dtypes)],
                "row_count": len(full_df),
                "column_count": len(full_df.columns),
            }
    except Exception:
        pass
    return None


@router.post("", response_model=UploadResponse, status_code=status.HTTP_201_CREATED)
async def upload_file(
    project_id: uuid.UUID,
    file: Annotated[UploadFile, File(...)],
    user: CurrentUser,
    db: Annotated[AsyncSession, Depends(get_db)],
    storage=Depends(get_storage),
):
    result = await db.execute(select(Project).where(Project.id == project_id, Project.owner_id == user.id))
    project = result.scalar_one_or_none()
    if not project:
        raise HTTPException(status_code=404, detail="Project not found")

    content = await file.read()
    if len(content) > MAX_SIZE_BYTES:
        raise HTTPException(status_code=413, detail="File too large (max 500MB)")

    mime_type = file.content_type or "application/octet-stream"
    if mime_type not in ALLOWED_MIME_TYPES:
        raise HTTPException(status_code=415, detail="Unsupported file type. Allowed: csv, xlsx, xls, pdf")

    schema_summary = _extract_schema_summary(content, mime_type)
    fingerprint = _compute_fingerprint(content, schema_summary)

    object_key = f"{project.org_id}/{project_id}/{uuid.uuid4()}/{file.filename}"
    storage_uri = await storage.put_object(object_key, content, mime_type)

    upload = DataUpload(
        project_id=project_id,
        original_filename=file.filename or "upload",
        mime_type=mime_type,
        size_bytes=len(content),
        storage_uri=storage_uri,
        fingerprint=fingerprint,
        schema_summary=schema_summary,
    )
    db.add(upload)
    await db.flush()

    return upload
