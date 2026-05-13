"""
Celery task: PACKAGING → DELIVERED
Builds the analysis_pack from existing stage outputs and stores it.
Triggered after an engineer confirms dispatch from AWAIT_DISPATCH_DA_REPORT.
"""

import asyncio
import uuid

import structlog
from sqlalchemy import create_engine, select
from sqlalchemy.orm import Session

from app.config import get_settings
from app.domain.pack.autoda_packer import build_analysis_pack
from app.infra.db.models import Project, RunCard, StateTransition
from app.infra.eventbus.redis_bus import publish_sync, runcard_channel
from app.infra.storage.client import StorageClient
from app.orchestration.state_machine.autoda import AutoDAStateMachine
from app.workers.celery_app import celery_app

logger = structlog.get_logger()
settings = get_settings()


def _sync_db() -> Session:
    engine = create_engine(settings.database_url_sync)
    return Session(engine)



@celery_app.task(bind=True, max_retries=3, default_retry_delay=30)
def run_packaging(self, runcard_id: str, project_id: str) -> dict:
    log = logger.bind(runcard_id=runcard_id, task_id=self.request.id)
    log.info("packaging.started")

    loop = asyncio.new_event_loop()
    asyncio.set_event_loop(loop)
    db = _sync_db()
    storage = StorageClient()

    try:
        runcard = db.execute(select(RunCard).where(RunCard.id == uuid.UUID(runcard_id))).scalar_one()
        project = db.execute(select(Project).where(Project.id == uuid.UUID(project_id))).scalar_one()

        from_state = runcard.current_state

        # Build and store analysis_pack (async packer, run in event loop)
        pack = loop.run_until_complete(build_analysis_pack(db=db, runcard=runcard, storage=storage))

        # Advance PACKAGING → DELIVERED
        sm = AutoDAStateMachine(runcard.current_state, task_level=project.task_level)
        sm.finish_packaging()

        runcard.current_state = sm.state
        db.add(StateTransition(
            runcard_id=runcard_id,
            from_state=from_state,
            to_state=sm.state,
            trigger="packaging_complete",
        ))
        db.commit()

        log.info("packaging.delivered", new_state=sm.state, pack_id=str(pack.id))

        try:
            publish_sync(runcard_channel(runcard_id), "runcard.state_changed", {
                "from": from_state, "to": sm.state, "trigger": "packaging_complete",
            })
        except Exception:
            pass

        return {"status": "delivered", "pack_id": str(pack.id)}

    except Exception as exc:
        log.error("packaging.failed", error=str(exc))
        db.rollback()
        raise self.retry(exc=exc)
    finally:
        db.close()
        loop.close()
