import uuid
from datetime import datetime

from sqlalchemy import (
    BigInteger,
    Boolean,
    CheckConstraint,
    ForeignKey,
    Index,
    Integer,
    Text,
    UniqueConstraint,
)
from sqlalchemy import TIMESTAMP
from sqlalchemy.dialects.postgresql import JSONB, UUID

TIMESTAMPTZ = TIMESTAMP(timezone=True)
from sqlalchemy.orm import Mapped, mapped_column, relationship
from sqlalchemy.sql import func

from app.infra.db.base import Base


def uuid_pk() -> Mapped[uuid.UUID]:
    return mapped_column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)


def now_tz() -> Mapped[datetime]:
    return mapped_column(TIMESTAMPTZ, server_default=func.now(), nullable=False)


class Organization(Base):
    __tablename__ = "organization"

    id: Mapped[uuid.UUID] = uuid_pk()
    name: Mapped[str] = mapped_column(Text, nullable=False)
    industry: Mapped[str | None] = mapped_column(Text)
    metadata_: Mapped[dict] = mapped_column("metadata", JSONB, default=dict)
    created_at: Mapped[datetime] = now_tz()

    users: Mapped[list["UserAccount"]] = relationship(back_populates="org")
    projects: Mapped[list["Project"]] = relationship(back_populates="org")


class UserAccount(Base):
    __tablename__ = "user_account"

    id: Mapped[uuid.UUID] = uuid_pk()
    org_id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), ForeignKey("organization.id"), nullable=False)
    email: Mapped[str] = mapped_column(Text, unique=True, nullable=False)
    display_name: Mapped[str] = mapped_column(Text, nullable=False)
    role: Mapped[str] = mapped_column(Text, nullable=False)
    password_hash: Mapped[str] = mapped_column(Text, nullable=False)
    metadata_: Mapped[dict] = mapped_column("metadata", JSONB, default=dict)
    created_at: Mapped[datetime] = now_tz()

    __table_args__ = (
        CheckConstraint("role IN ('customer','engineer','senior_engineer','admin')", name="ck_user_role"),
        Index("idx_user_org", "org_id"),
    )

    org: Mapped["Organization"] = relationship(back_populates="users")


class Project(Base):
    __tablename__ = "project"

    id: Mapped[uuid.UUID] = uuid_pk()
    org_id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), ForeignKey("organization.id"), nullable=False)
    owner_id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), ForeignKey("user_account.id"), nullable=False)
    product_type: Mapped[str] = mapped_column(Text, nullable=False)
    task_level: Mapped[str] = mapped_column(Text, nullable=False)
    responsible_engineer_id: Mapped[uuid.UUID | None] = mapped_column(UUID(as_uuid=True), ForeignKey("user_account.id"))
    status: Mapped[str] = mapped_column(Text, nullable=False, default="draft")
    current_version_id: Mapped[uuid.UUID | None] = mapped_column(UUID(as_uuid=True))
    parent_project_id: Mapped[uuid.UUID | None] = mapped_column(UUID(as_uuid=True), ForeignKey("project.id"))
    metadata_: Mapped[dict] = mapped_column("metadata", JSONB, default=dict)
    created_at: Mapped[datetime] = now_tz()
    archived_at: Mapped[datetime | None] = mapped_column(TIMESTAMPTZ)

    __table_args__ = (
        CheckConstraint("product_type IN ('autoda','automl')", name="ck_project_product_type"),
        CheckConstraint("task_level IN ('L1','L2','L3')", name="ck_project_task_level"),
        Index("idx_project_owner", "owner_id"),
        Index("idx_project_org", "org_id"),
        Index("idx_project_status", "status"),
    )

    org: Mapped["Organization"] = relationship(back_populates="projects")
    owner: Mapped["UserAccount"] = relationship(foreign_keys=[owner_id])
    runcards: Mapped[list["RunCard"]] = relationship(back_populates="project")
    requirement: Mapped["Requirement | None"] = relationship(back_populates="project", uselist=False)
    versions: Mapped[list["ProjectVersion"]] = relationship(back_populates="project", foreign_keys="ProjectVersion.project_id")
    data_uploads: Mapped[list["DataUpload"]] = relationship(back_populates="project")
    lifecycle_logs: Mapped[list["LifecycleLog"]] = relationship(back_populates="project")
    analysis_packs: Mapped[list["AnalysisPack"]] = relationship(back_populates="project")
    solve_packs: Mapped[list["SolvePack"]] = relationship(back_populates="project")


class Requirement(Base):
    __tablename__ = "requirement"

    id: Mapped[uuid.UUID] = uuid_pk()
    project_id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), ForeignKey("project.id"), unique=True, nullable=False)
    goal: Mapped[dict] = mapped_column(JSONB, nullable=False)
    expected_outputs: Mapped[list] = mapped_column(JSONB, default=list)
    success_metric: Mapped[dict | None] = mapped_column(JSONB)
    constraints: Mapped[dict] = mapped_column(JSONB, default=dict)
    raw_dialogue: Mapped[str | None] = mapped_column(Text)
    confirmed_at: Mapped[datetime | None] = mapped_column(TIMESTAMPTZ)

    project: Mapped["Project"] = relationship(back_populates="requirement")


class RequirementBlock(Base):
    __tablename__ = "requirement_block"

    id: Mapped[uuid.UUID] = uuid_pk()
    author_id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), ForeignKey("user_account.id"), nullable=False)
    visibility: Mapped[str] = mapped_column(Text, nullable=False)
    title: Mapped[str] = mapped_column(Text, nullable=False)
    content: Mapped[dict] = mapped_column(JSONB, nullable=False)
    metadata_: Mapped[dict] = mapped_column("metadata", JSONB, default=dict)
    created_at: Mapped[datetime] = now_tz()

    __table_args__ = (
        CheckConstraint("visibility IN ('private','org','public')", name="ck_req_block_visibility"),
        Index("idx_req_block_author", "author_id"),
        Index("idx_req_block_visibility", "visibility"),
    )


class DataUpload(Base):
    __tablename__ = "data_upload"

    id: Mapped[uuid.UUID] = uuid_pk()
    project_id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), ForeignKey("project.id"), nullable=False)
    original_filename: Mapped[str] = mapped_column(Text, nullable=False)
    mime_type: Mapped[str] = mapped_column(Text, nullable=False)
    size_bytes: Mapped[int] = mapped_column(BigInteger, nullable=False)
    storage_uri: Mapped[str] = mapped_column(Text, nullable=False)
    fingerprint: Mapped[str] = mapped_column(Text, nullable=False)
    schema_summary: Mapped[dict | None] = mapped_column(JSONB)
    metadata_: Mapped[dict] = mapped_column("metadata", JSONB, default=dict)
    uploaded_at: Mapped[datetime] = now_tz()

    __table_args__ = (
        Index("idx_data_upload_project", "project_id"),
        Index("idx_data_upload_fingerprint", "fingerprint"),
    )

    project: Mapped["Project"] = relationship(back_populates="data_uploads")


class ProjectVersion(Base):
    __tablename__ = "project_version"

    id: Mapped[uuid.UUID] = uuid_pk()
    project_id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), ForeignKey("project.id"), nullable=False)
    parent_version_id: Mapped[uuid.UUID | None] = mapped_column(UUID(as_uuid=True), ForeignKey("project_version.id"))
    version_number: Mapped[int] = mapped_column(Integer, nullable=False)
    modification_prompt: Mapped[str | None] = mapped_column(Text)
    snapshot_manifest: Mapped[dict] = mapped_column(JSONB, nullable=False)
    created_by: Mapped[uuid.UUID | None] = mapped_column(UUID(as_uuid=True), ForeignKey("user_account.id"))
    created_at: Mapped[datetime] = now_tz()

    __table_args__ = (
        UniqueConstraint("project_id", "version_number", name="uq_pv_project_version"),
        Index("idx_pv_project", "project_id"),
        Index("idx_pv_parent", "parent_version_id"),
    )

    project: Mapped["Project"] = relationship(back_populates="versions", foreign_keys=[project_id])
    runcards: Mapped[list["RunCard"]] = relationship(back_populates="project_version")


class RunCard(Base):
    __tablename__ = "runcard"

    id: Mapped[uuid.UUID] = uuid_pk()
    project_id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), ForeignKey("project.id"), nullable=False)
    project_version_id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), ForeignKey("project_version.id"), nullable=False)
    parent_runcard_id: Mapped[uuid.UUID | None] = mapped_column(UUID(as_uuid=True), ForeignKey("runcard.id"))
    kind: Mapped[str] = mapped_column(Text, nullable=False)
    current_state: Mapped[str] = mapped_column(Text, nullable=False)
    branch_strategy_name: Mapped[str | None] = mapped_column(Text)
    data_context: Mapped[dict] = mapped_column(JSONB, default=dict)
    temporal_workflow_id: Mapped[str | None] = mapped_column(Text)
    plan_steps: Mapped[list] = mapped_column(JSONB, default=list)
    plan_progress: Mapped[int] = mapped_column(Integer, default=0)
    metadata_: Mapped[dict] = mapped_column("metadata", JSONB, default=dict)
    created_at: Mapped[datetime] = now_tz()
    completed_at: Mapped[datetime | None] = mapped_column(TIMESTAMPTZ)

    __table_args__ = (
        CheckConstraint("kind IN ('main','branch')", name="ck_runcard_kind"),
        Index("idx_runcard_project", "project_id"),
        Index("idx_runcard_version", "project_version_id"),
        Index("idx_runcard_parent", "parent_runcard_id"),
        Index("idx_runcard_state", "current_state"),
    )

    project: Mapped["Project"] = relationship(back_populates="runcards")
    project_version: Mapped["ProjectVersion"] = relationship(back_populates="runcards")
    state_transitions: Mapped[list["StateTransition"]] = relationship(back_populates="runcard")
    stage_outputs: Mapped[list["StageOutput"]] = relationship(back_populates="runcard")
    review_records: Mapped[list["ReviewRecord"]] = relationship(back_populates="runcard")
    sandbox_snapshots: Mapped[list["SandboxSnapshot"]] = relationship(back_populates="runcard")
    execution_events: Mapped[list["ExecutionEvent"]] = relationship(back_populates="runcard")
    lifecycle_logs: Mapped[list["LifecycleLog"]] = relationship(back_populates="runcard")


class StateTransition(Base):
    __tablename__ = "state_transition"

    id: Mapped[uuid.UUID] = uuid_pk()
    runcard_id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), ForeignKey("runcard.id"), nullable=False)
    from_state: Mapped[str | None] = mapped_column(Text)
    to_state: Mapped[str] = mapped_column(Text, nullable=False)
    trigger: Mapped[str] = mapped_column(Text, nullable=False)
    actor_id: Mapped[uuid.UUID | None] = mapped_column(UUID(as_uuid=True), ForeignKey("user_account.id"))
    payload: Mapped[dict] = mapped_column(JSONB, default=dict)
    transitioned_at: Mapped[datetime] = now_tz()

    __table_args__ = (
        CheckConstraint(
            "trigger IN ('auto','review_pass','review_modify','review_reject','dispatch','pause','resume','rollback')",
            name="ck_st_trigger",
        ),
        Index("idx_st_runcard", "runcard_id", "transitioned_at"),
    )

    runcard: Mapped["RunCard"] = relationship(back_populates="state_transitions")


class StageOutput(Base):
    __tablename__ = "stage_output"

    id: Mapped[uuid.UUID] = uuid_pk()
    runcard_id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), ForeignKey("runcard.id"), nullable=False)
    stage_name: Mapped[str] = mapped_column(Text, nullable=False)
    output_type: Mapped[str] = mapped_column(Text, nullable=False)
    content: Mapped[dict] = mapped_column(JSONB, nullable=False)
    storage_uri: Mapped[str | None] = mapped_column(Text)
    is_human_modified: Mapped[bool] = mapped_column(Boolean, default=False)
    superseded_by: Mapped[uuid.UUID | None] = mapped_column(UUID(as_uuid=True), ForeignKey("stage_output.id"))
    created_at: Mapped[datetime] = now_tz()

    __table_args__ = (
        CheckConstraint(
            "output_type IN ('plan','data_summary','analysis_report','feature_strategy','ml_plan','train_result','other')",
            name="ck_so_output_type",
        ),
        Index("idx_so_runcard_stage", "runcard_id", "stage_name"),
    )

    runcard: Mapped["RunCard"] = relationship(back_populates="stage_outputs")


class ReviewRecord(Base):
    __tablename__ = "review_record"

    id: Mapped[uuid.UUID] = uuid_pk()
    runcard_id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), ForeignKey("runcard.id"), nullable=False)
    stage_output_id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), ForeignKey("stage_output.id"), nullable=False)
    review_node: Mapped[str] = mapped_column(Text, nullable=False)
    action: Mapped[str] = mapped_column(Text, nullable=False)
    reviewer_id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), ForeignKey("user_account.id"), nullable=False)
    comment: Mapped[str | None] = mapped_column(Text)
    modifications: Mapped[dict | None] = mapped_column(JSONB)
    reviewed_at: Mapped[datetime] = now_tz()

    __table_args__ = (
        CheckConstraint("action IN ('accept','modify','reject','escalate')", name="ck_rr_action"),
        Index("idx_rr_runcard", "runcard_id"),
    )

    runcard: Mapped["RunCard"] = relationship(back_populates="review_records")


class SandboxSnapshot(Base):
    __tablename__ = "sandbox_snapshot"

    id: Mapped[uuid.UUID] = uuid_pk()
    runcard_id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), ForeignKey("runcard.id"), nullable=False)
    state_at_snapshot: Mapped[str] = mapped_column(Text, nullable=False)
    storage_uri: Mapped[str] = mapped_column(Text, nullable=False)
    size_bytes: Mapped[int | None] = mapped_column(BigInteger)
    metadata_: Mapped[dict] = mapped_column("metadata", JSONB, default=dict)
    created_at: Mapped[datetime] = now_tz()

    __table_args__ = (
        Index("idx_ss_runcard", "runcard_id", "created_at"),
    )

    runcard: Mapped["RunCard"] = relationship(back_populates="sandbox_snapshots")


class ExecutionEvent(Base):
    __tablename__ = "execution_event"

    id: Mapped[uuid.UUID] = uuid_pk()
    runcard_id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), ForeignKey("runcard.id"), nullable=False)
    event_type: Mapped[str] = mapped_column(Text, nullable=False)
    payload: Mapped[dict] = mapped_column(JSONB, nullable=False)
    emitted_at: Mapped[datetime] = now_tz()

    __table_args__ = (
        Index("idx_ee_runcard_time", "runcard_id", "emitted_at"),
    )

    runcard: Mapped["RunCard"] = relationship(back_populates="execution_events")


class LifecycleLog(Base):
    __tablename__ = "lifecycle_log"

    id: Mapped[uuid.UUID] = uuid_pk()
    project_id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), ForeignKey("project.id"), nullable=False)
    runcard_id: Mapped[uuid.UUID | None] = mapped_column(UUID(as_uuid=True), ForeignKey("runcard.id"))
    event: Mapped[str] = mapped_column(Text, nullable=False)
    actor_id: Mapped[uuid.UUID | None] = mapped_column(UUID(as_uuid=True), ForeignKey("user_account.id"))
    details: Mapped[dict] = mapped_column(JSONB, default=dict)
    recorded_at: Mapped[datetime] = now_tz()

    __table_args__ = (
        Index("idx_ll_project", "project_id", "recorded_at"),
    )

    project: Mapped["Project"] = relationship(back_populates="lifecycle_logs")
    runcard: Mapped["RunCard | None"] = relationship(back_populates="lifecycle_logs")


class AnalysisPack(Base):
    __tablename__ = "analysis_pack"

    id: Mapped[uuid.UUID] = uuid_pk()
    project_id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), ForeignKey("project.id"), nullable=False)
    source_runcard_id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), ForeignKey("runcard.id"), nullable=False)
    storage_uri: Mapped[str] = mapped_column(Text, nullable=False)
    data_fingerprint: Mapped[str] = mapped_column(Text, nullable=False)
    data_report: Mapped[dict] = mapped_column(JSONB, nullable=False)
    feature_hints: Mapped[list] = mapped_column(JSONB, default=list)
    visibility: Mapped[str] = mapped_column(Text, nullable=False, default="private")
    metadata_: Mapped[dict] = mapped_column("metadata", JSONB, default=dict)
    created_at: Mapped[datetime] = now_tz()

    __table_args__ = (
        CheckConstraint("visibility IN ('private','org','public')", name="ck_ap_visibility"),
        Index("idx_ap_project", "project_id"),
        Index("idx_ap_fingerprint", "data_fingerprint"),
        Index("idx_ap_visibility", "visibility"),
    )

    project: Mapped["Project"] = relationship(back_populates="analysis_packs")


class SolvePack(Base):
    __tablename__ = "solve_pack"

    id: Mapped[uuid.UUID] = uuid_pk()
    project_id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), ForeignKey("project.id"), nullable=False)
    source_runcard_id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), ForeignKey("runcard.id"), nullable=False)
    source_analysis_pack_id: Mapped[uuid.UUID | None] = mapped_column(UUID(as_uuid=True), ForeignKey("analysis_pack.id"))
    solution_index: Mapped[int] = mapped_column(Integer, nullable=False, default=1)
    storage_uri: Mapped[str] = mapped_column(Text, nullable=False)
    ml_report: Mapped[dict] = mapped_column(JSONB, nullable=False)
    manifest: Mapped[dict] = mapped_column(JSONB, nullable=False)
    metadata_: Mapped[dict] = mapped_column("metadata", JSONB, default=dict)
    created_at: Mapped[datetime] = now_tz()

    __table_args__ = (
        Index("idx_sp_project", "project_id"),
    )

    project: Mapped["Project"] = relationship(back_populates="solve_packs")


class ModelRegistryEntry(Base):
    __tablename__ = "model_registry_entry"

    id: Mapped[uuid.UUID] = uuid_pk()
    solve_pack_id: Mapped[uuid.UUID | None] = mapped_column(UUID(as_uuid=True), ForeignKey("solve_pack.id"))
    model_name: Mapped[str] = mapped_column(Text, nullable=False)
    version: Mapped[str] = mapped_column(Text, nullable=False)
    model_uri: Mapped[str] = mapped_column(Text, nullable=False)
    source: Mapped[str] = mapped_column(Text, nullable=False)
    metrics: Mapped[dict] = mapped_column(JSONB, default=dict)
    share_scope: Mapped[str] = mapped_column(Text, nullable=False, default="platform_only")
    metadata_: Mapped[dict] = mapped_column("metadata", JSONB, default=dict)
    registered_at: Mapped[datetime] = now_tz()

    __table_args__ = (
        CheckConstraint("source IN ('automl','finetuned','external')", name="ck_mre_source"),
        CheckConstraint("share_scope IN ('platform_only','org_internal','public')", name="ck_mre_share_scope"),
        UniqueConstraint("model_name", "version", name="uq_mre_name_version"),
        Index("idx_mre_source", "source"),
    )
