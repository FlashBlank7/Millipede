"""
Build and store an analysis_pack from a completed AutoDA RunCard.

feature_hints schema (pre-defined for AutoML Phase 2 compatibility):
[
  {
    "field": "column_name",
    "hint_type": "target" | "high_cardinality" | "leakage_risk" | "low_variance" | "datetime" | "text",
    "description": "human-readable explanation",
    "suggested_transform": "label_encode" | "one_hot" | "drop" | "log" | "bin" | "tfidf" | null
  }
]
"""

import json
import uuid

from sqlalchemy.orm import Session

from app.infra.db.models import AnalysisPack, RunCard, StageOutput
from app.infra.storage.client import StorageClient


FEATURE_HINT_SCHEMA_VERSION = "1.0"


async def build_analysis_pack(
    db: Session,
    runcard: RunCard,
    storage: StorageClient,
) -> AnalysisPack:
    # Collect stage outputs
    da_report_output = _get_latest_output(db, runcard.id, "analysis_report")
    pre_output = _get_latest_output(db, runcard.id, "data_summary")

    data_report = _assemble_data_report(da_report_output, pre_output)
    feature_hints = _extract_feature_hints(da_report_output)

    fingerprint = _get_fingerprint(db, runcard)

    # Build manifest
    manifest = {
        "source_runcard_id": str(runcard.id),
        "source_project_id": str(runcard.project_id),
        "data_fingerprint": fingerprint,
        "created_at": _utcnow(),
        "version": "1.0",
        "compatible_automl_versions": ["1.x"],
        "feature_hints_schema_version": FEATURE_HINT_SCHEMA_VERSION,
    }

    pack_content = json.dumps({
        "manifest": manifest,
        "data_report": data_report,
        "feature_hints": feature_hints,
    }).encode()

    storage_key = f"analysis_packs/{runcard.project_id}/{runcard.id}/pack.json"
    storage_uri = await storage.put_object(storage_key, pack_content, "application/json")

    pack = AnalysisPack(
        project_id=runcard.project_id,
        source_runcard_id=runcard.id,
        storage_uri=storage_uri,
        data_fingerprint=fingerprint,
        data_report=data_report,
        feature_hints=feature_hints,
        visibility="private",
    )
    db.add(pack)
    db.flush()

    return pack


def _get_latest_output(db: Session, runcard_id: uuid.UUID, output_type: str) -> dict | None:
    from sqlalchemy import select
    result = db.execute(
        select(StageOutput)
        .where(
            StageOutput.runcard_id == runcard_id,
            StageOutput.output_type == output_type,
            StageOutput.superseded_by.is_(None),
        )
        .order_by(StageOutput.created_at.desc())
        .limit(1)
    )
    row = result.scalar_one_or_none()
    return row.content if row else None


def _assemble_data_report(da_report: dict | None, pre_output: dict | None) -> dict:
    return {
        "overview": (da_report or {}).get("overview", {}),
        "fields": (da_report or {}).get("fields", []),
        "statistics": (da_report or {}).get("statistics", {}),
        "advanced_analysis": (da_report or {}).get("advanced_analysis", {}),
        "preprocessing_impact": (pre_output or {}).get("preprocessing_impact", {}),
        "feature_hints": [],  # populated separately
    }


def _extract_feature_hints(da_report: dict | None) -> list[dict]:
    if not da_report:
        return []
    raw_hints = da_report.get("feature_hints", [])
    validated = []
    for h in raw_hints:
        if not isinstance(h, dict):
            continue
        validated.append({
            "field": str(h.get("field", "")),
            "hint_type": str(h.get("hint_type", "other")),
            "description": str(h.get("description", "")),
            "suggested_transform": h.get("suggested_transform"),
        })
    return validated


def _get_fingerprint(db: Session, runcard: RunCard) -> str:
    from sqlalchemy import select
    from app.infra.db.models import DataUpload
    result = db.execute(
        select(DataUpload)
        .where(DataUpload.project_id == runcard.project_id)
        .order_by(DataUpload.uploaded_at.desc())
        .limit(1)
    )
    upload = result.scalar_one_or_none()
    return upload.fingerprint if upload else "unknown:unknown:0"


def _utcnow() -> str:
    from datetime import datetime, timezone
    return datetime.now(timezone.utc).isoformat()
