"""
AutoDA L1 Celery task.

Entry point: run_autoda_l1(runcard_id, project_id)

Stages (L1 — no intermediate reviews):
  1. PRE_ANALYZING  — schema profiling, data quality check
  2. PREPROCESSING  — cleaning, type fixing, missing value handling
  3. DA_PLANNING    — LLM plans analysis steps
  4. DATA_ANALYZING — execute analysis plan step-by-step
  5. PACKAGING      — build and store analysis_pack
"""

import asyncio
import json
import uuid

import structlog
from celery import Task
from sqlalchemy import create_engine, select
from sqlalchemy.orm import Session

from app.config import get_settings
from app.domain.pack.autoda_packer import build_analysis_pack
from app.infra.db.models import Project, Requirement, RunCard, StageOutput
from app.infra.eventbus.redis_bus import publish_sync, runcard_channel
from app.infra.sandbox.docker_client import DockerSandboxClient
from app.infra.storage.client import StorageClient
from app.orchestration.agent_runner.runner import AgentRunner
from app.orchestration.state_machine.autoda import AutoDAStateMachine
from app.orchestration.state_machine.persistence import record_execution_event, record_transition
from app.workers.celery_app import celery_app

logger = structlog.get_logger()
settings = get_settings()

# States that are valid task entry points (either fresh or after a reset)
_RESUMABLE_STATES = {"REQ_READY", "DATA_ANALYZING", "DA_PLANNING", "PREPROCESSING", "PRE_ANALYZING"}


def _sync_db() -> Session:
    engine = create_engine(settings.database_url_sync)
    return Session(engine)


def _run(loop: asyncio.AbstractEventLoop, coro):
    return loop.run_until_complete(coro)


@celery_app.task(bind=True, max_retries=2, default_retry_delay=30)
def run_autoda_l1(self: Task, runcard_id: str, project_id: str) -> dict:
    log = logger.bind(runcard_id=runcard_id, project_id=project_id)
    log.info("autoda_l1.started")

    # Run in a dedicated thread so LiteLLM's async internals get their own event loop
    import concurrent.futures
    with concurrent.futures.ThreadPoolExecutor(max_workers=1) as executor:
        future = executor.submit(_run_autoda_l1_body, runcard_id, project_id, log)
        try:
            return future.result()
        except Exception as exc:
            raise self.retry(exc=exc)


def _run_autoda_l1_body(runcard_id: str, project_id: str, log) -> dict:
    loop = asyncio.new_event_loop()
    asyncio.set_event_loop(loop)

    db = _sync_db()
    sandbox = DockerSandboxClient()
    storage = StorageClient()
    session_id = None
    runcard = None
    project = None

    try:
        runcard = db.execute(select(RunCard).where(RunCard.id == uuid.UUID(runcard_id))).scalar_one()
        project = db.execute(select(Project).where(Project.id == uuid.UUID(project_id))).scalar_one()
        requirement = db.execute(select(Requirement).where(Requirement.project_id == project.id)).scalar_one()

        # Reset from FAILED state if retrying
        if runcard.current_state == "FAILED":
            runcard.current_state = "REQ_READY"
            project.status = "running"
            db.commit()

        sm = AutoDAStateMachine(runcard.current_state, task_level=project.task_level)

        def on_event(event_type: str, payload: dict):
            record_execution_event(db, runcard.id, event_type, payload)
            db.commit()
            try:
                publish_sync(runcard_channel(runcard_id), event_type, payload)
            except Exception as e:
                log.warning("event.publish_failed", error=str(e))

        session_id = _run(loop, sandbox.create(runcard_id))

        # Upload input files to sandbox
        _upload_inputs(db, project, sandbox, session_id, loop)

        # --- Stage: PRE_ANALYZING ---
        _transition(db, runcard, sm, "start_analysis", on_event)

        pre_goal = (
            "Profile the dataset: detect column types, missing values, outliers, "
            "and data quality issues. Save a JSON summary to /workspace/reports/pre_analysis.json"
        )
        pre_runner = AgentRunner(sandbox, session_id, on_event)
        pre_plan = _run(loop, pre_runner.plan(pre_goal, runcard.data_context))
        _save_plan_steps(db, runcard, "PRE_ANALYZING", pre_plan)

        # --- Stage: PREPROCESSING ---
        _transition(db, runcard, sm, "finish_pre_analysis", on_event)

        pre_result = _run(loop, pre_runner.execute(pre_plan, runcard.data_context))
        if not pre_result.overall_success:
            raise RuntimeError(f"PRE_ANALYZING failed: {pre_result.failure_reason}")

        _save_stage_output(db, runcard, "PRE_ANALYZING", "data_summary",
                           _collect_report(sandbox, session_id, "pre_analysis.json", loop))

        preproc_goal = (
            "Clean the dataset based on the profiling report at /workspace/reports/pre_analysis.json. "
            "Fix types, handle missing values, remove duplicates. "
            "Save cleaned data to /workspace/processing/cleaned.csv and a summary to "
            "/workspace/reports/preprocessing_impact.json"
        )
        preproc_runner = AgentRunner(sandbox, session_id, on_event)
        preproc_plan = _run(loop, preproc_runner.plan(preproc_goal, runcard.data_context))
        _save_plan_steps(db, runcard, "PREPROCESSING", preproc_plan)

        # --- Stage: DA_PLANNING ---
        _transition(db, runcard, sm, "finish_preprocessing", on_event)

        preproc_result = _run(loop, preproc_runner.execute(preproc_plan, runcard.data_context))
        if not preproc_result.overall_success:
            raise RuntimeError(f"PREPROCESSING failed: {preproc_result.failure_reason}")

        _save_stage_output(db, runcard, "PREPROCESSING", "data_summary",
                           _collect_report(sandbox, session_id, "preprocessing_impact.json", loop))

        goal_text = _goal_text(requirement)
        da_goal = (
            f"Perform comprehensive data analysis to answer: {goal_text}. "
            f"Use cleaned data at /workspace/processing/cleaned.csv. "
            f"Produce visualizations in /workspace/outputs/visualizations/ and "
            f"a full analysis report as JSON at /workspace/reports/da_report.json. "
            f"The JSON must include: overview, fields, statistics, advanced_analysis, "
            f"preprocessing_impact (load from preprocessing_impact.json), and feature_hints "
            f"(list of {{field, hint_type, description, suggested_transform}} dicts)."
        )
        da_runner = AgentRunner(sandbox, session_id, on_event)
        da_plan = _run(loop, da_runner.plan(da_goal, runcard.data_context))
        _save_plan_steps(db, runcard, "DA_PLANNING", da_plan)
        _save_stage_output(db, runcard, "DA_PLANNING", "plan",
                           {"steps": [s.model_dump() for s in da_plan.steps]})

        # --- Stage: DATA_ANALYZING ---
        _transition(db, runcard, sm, "finish_da_planning", on_event)

        da_result = _run(loop, da_runner.execute(da_plan, runcard.data_context))
        if not da_result.overall_success:
            raise RuntimeError(f"DATA_ANALYZING failed: {da_result.failure_reason}")

        da_report = _collect_report(sandbox, session_id, "da_report.json", loop) or {}
        _save_stage_output(db, runcard, "DATA_ANALYZING", "analysis_report", da_report)

        # --- Stage: AWAIT_REVIEW_DA_REPORT (L1: auto-advance) ---
        _transition(db, runcard, sm, "finish_data_analyzing", on_event)

        if project.task_level == "L1":
            _transition(db, runcard, sm, "dispatch_report", on_event)
            _transition(db, runcard, sm, "confirm_dispatch", on_event)

            # --- Stage: PACKAGING ---
            pack = _run(loop, build_analysis_pack(db, runcard, storage))
            db.commit()

            _transition(db, runcard, sm, "finish_packaging", on_event)
            project.status = "delivered"
            runcard.completed_at = _utcnow_dt()
            db.commit()

            log.info("autoda_l1.completed", analysis_pack_id=str(pack.id))
            return {"status": "delivered", "analysis_pack_id": str(pack.id)}

        # L2/L3: stop at AWAIT_REVIEW_DA_REPORT for engineer review
        project.status = "awaiting_review"
        db.commit()
        return {"status": "awaiting_review"}

    except Exception as exc:
        log.error("autoda_l1.failed", error=repr(exc))
        try:
            _mark_failed(db, runcard, project)
        except Exception:
            pass
        raise
    finally:
        if session_id:
            try:
                _run(loop, sandbox.destroy(session_id))
            except Exception:
                pass
        db.close()
        loop.close()


# ── helpers ──────────────────────────────────────────────────────────────────

def _mark_failed(db: Session, runcard, project) -> None:
    if runcard:
        sm = AutoDAStateMachine(runcard.current_state, task_level=project.task_level if project else "L1")
        try:
            sm.fail()
            runcard.current_state = sm.state
        except Exception:
            runcard.current_state = "FAILED"
    if project:
        project.status = "failed"
    db.commit()


def _transition(db: Session, runcard: RunCard, sm: AutoDAStateMachine, trigger: str, on_event) -> None:
    from_state = sm.state
    getattr(sm, trigger)()
    to_state = sm.state
    runcard.current_state = to_state
    record_transition(db, runcard.id, from_state, to_state, trigger="auto")
    db.commit()
    on_event("runcard.state_changed", {"from": from_state, "to": to_state, "trigger": trigger})


def _upload_inputs(db: Session, project: Project, sandbox: DockerSandboxClient,
                   session_id: str, loop: asyncio.AbstractEventLoop) -> None:
    from app.infra.db.models import DataUpload
    storage = StorageClient()
    uploads = db.execute(select(DataUpload).where(DataUpload.project_id == project.id)).scalars().all()
    for upload in uploads:
        bucket, key = upload.storage_uri.split("/", 1)
        content = _run(loop, storage.get_object(key))
        _run(loop, sandbox.write_file(session_id, f"/workspace/inputs/{upload.original_filename}", content))


def _save_plan_steps(db: Session, runcard: RunCard, stage: str, plan) -> None:
    runcard.plan_steps = [s.model_dump() for s in plan.steps]
    runcard.plan_progress = 0
    db.flush()


def _save_stage_output(db: Session, runcard: RunCard, stage: str, output_type: str, content: dict) -> None:
    # Sanitize NaN/Inf which are valid Python floats but invalid JSON/Postgres
    sanitized = json.loads(json.dumps(content or {}, default=lambda v: None))
    out = StageOutput(
        runcard_id=runcard.id,
        stage_name=stage,
        output_type=output_type,
        content=sanitized,
    )
    db.add(out)
    db.flush()


def _collect_report(sandbox: DockerSandboxClient, session_id: str, filename: str,
                    loop: asyncio.AbstractEventLoop) -> dict | None:
    try:
        raw = _run(loop, sandbox.read_file(session_id, f"/workspace/reports/{filename}"))
        # Use allow_nan=False round-trip to replace NaN/Inf with null
        parsed = json.loads(raw)
        return json.loads(json.dumps(parsed, allow_nan=False, default=lambda v: None))
    except Exception:
        return None


def _goal_text(requirement: Requirement) -> str:
    goal = requirement.goal
    if isinstance(goal, dict):
        return goal.get("text") or goal.get("description") or str(goal)
    return str(goal)


def _utcnow_dt():
    from datetime import datetime, timezone
    return datetime.now(timezone.utc)
