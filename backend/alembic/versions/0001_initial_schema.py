"""initial schema

Revision ID: 0001
Revises:
Create Date: 2026-05-13

"""
from typing import Sequence, Union

import sqlalchemy as sa
from alembic import op
from sqlalchemy.dialects.postgresql import JSONB, UUID

TIMESTAMPTZ = sa.TIMESTAMP(timezone=True)

revision: str = "0001"
down_revision: Union[str, None] = None
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    # pgvector is only needed in Phase 2+ (vector search). Must run outside the main
    # transaction (AUTOCOMMIT) so a failure doesn't abort the rest of the migration.
    conn = op.get_bind()
    try:
        conn.execution_options(isolation_level="AUTOCOMMIT").execute(
            sa.text("CREATE EXTENSION IF NOT EXISTS pgvector")
        )
    except Exception:
        pass

    op.create_table(
        "organization",
        sa.Column("id", UUID(as_uuid=True), primary_key=True, server_default=sa.text("gen_random_uuid()")),
        sa.Column("name", sa.Text, nullable=False),
        sa.Column("industry", sa.Text),
        sa.Column("metadata", JSONB, server_default="{}"),
        sa.Column("created_at", TIMESTAMPTZ, server_default=sa.text("now()"), nullable=False),
    )

    op.create_table(
        "user_account",
        sa.Column("id", UUID(as_uuid=True), primary_key=True, server_default=sa.text("gen_random_uuid()")),
        sa.Column("org_id", UUID(as_uuid=True), sa.ForeignKey("organization.id"), nullable=False),
        sa.Column("email", sa.Text, unique=True, nullable=False),
        sa.Column("display_name", sa.Text, nullable=False),
        sa.Column("role", sa.Text, nullable=False),
        sa.Column("password_hash", sa.Text, nullable=False),
        sa.Column("metadata", JSONB, server_default="{}"),
        sa.Column("created_at", TIMESTAMPTZ, server_default=sa.text("now()"), nullable=False),
        sa.CheckConstraint("role IN ('customer','engineer','senior_engineer','admin')", name="ck_user_role"),
    )
    op.create_index("idx_user_org", "user_account", ["org_id"])

    op.create_table(
        "project",
        sa.Column("id", UUID(as_uuid=True), primary_key=True, server_default=sa.text("gen_random_uuid()")),
        sa.Column("org_id", UUID(as_uuid=True), sa.ForeignKey("organization.id"), nullable=False),
        sa.Column("owner_id", UUID(as_uuid=True), sa.ForeignKey("user_account.id"), nullable=False),
        sa.Column("product_type", sa.Text, nullable=False),
        sa.Column("task_level", sa.Text, nullable=False),
        sa.Column("responsible_engineer_id", UUID(as_uuid=True), sa.ForeignKey("user_account.id")),
        sa.Column("status", sa.Text, nullable=False, server_default="draft"),
        sa.Column("current_version_id", UUID(as_uuid=True)),
        sa.Column("parent_project_id", UUID(as_uuid=True), sa.ForeignKey("project.id")),
        sa.Column("metadata", JSONB, server_default="{}"),
        sa.Column("created_at", TIMESTAMPTZ, server_default=sa.text("now()"), nullable=False),
        sa.Column("archived_at", TIMESTAMPTZ),
        sa.CheckConstraint("product_type IN ('autoda','automl')", name="ck_project_product_type"),
        sa.CheckConstraint("task_level IN ('L1','L2','L3')", name="ck_project_task_level"),
    )
    op.create_index("idx_project_owner", "project", ["owner_id"])
    op.create_index("idx_project_org", "project", ["org_id"])
    op.create_index("idx_project_status", "project", ["status"])

    op.create_table(
        "requirement",
        sa.Column("id", UUID(as_uuid=True), primary_key=True, server_default=sa.text("gen_random_uuid()")),
        sa.Column("project_id", UUID(as_uuid=True), sa.ForeignKey("project.id"), unique=True, nullable=False),
        sa.Column("goal", JSONB, nullable=False),
        sa.Column("expected_outputs", JSONB, server_default="[]"),
        sa.Column("success_metric", JSONB),
        sa.Column("constraints", JSONB, server_default="{}"),
        sa.Column("raw_dialogue", sa.Text),
        sa.Column("confirmed_at", TIMESTAMPTZ),
    )

    op.create_table(
        "requirement_block",
        sa.Column("id", UUID(as_uuid=True), primary_key=True, server_default=sa.text("gen_random_uuid()")),
        sa.Column("author_id", UUID(as_uuid=True), sa.ForeignKey("user_account.id"), nullable=False),
        sa.Column("visibility", sa.Text, nullable=False),
        sa.Column("title", sa.Text, nullable=False),
        sa.Column("content", JSONB, nullable=False),
        sa.Column("metadata", JSONB, server_default="{}"),
        sa.Column("created_at", TIMESTAMPTZ, server_default=sa.text("now()"), nullable=False),
        sa.CheckConstraint("visibility IN ('private','org','public')", name="ck_req_block_visibility"),
    )
    op.create_index("idx_req_block_author", "requirement_block", ["author_id"])
    op.create_index("idx_req_block_visibility", "requirement_block", ["visibility"])

    op.create_table(
        "data_upload",
        sa.Column("id", UUID(as_uuid=True), primary_key=True, server_default=sa.text("gen_random_uuid()")),
        sa.Column("project_id", UUID(as_uuid=True), sa.ForeignKey("project.id"), nullable=False),
        sa.Column("original_filename", sa.Text, nullable=False),
        sa.Column("mime_type", sa.Text, nullable=False),
        sa.Column("size_bytes", sa.BigInteger, nullable=False),
        sa.Column("storage_uri", sa.Text, nullable=False),
        sa.Column("fingerprint", sa.Text, nullable=False),
        sa.Column("schema_summary", JSONB),
        sa.Column("metadata", JSONB, server_default="{}"),
        sa.Column("uploaded_at", TIMESTAMPTZ, server_default=sa.text("now()"), nullable=False),
    )
    op.create_index("idx_data_upload_project", "data_upload", ["project_id"])
    op.create_index("idx_data_upload_fingerprint", "data_upload", ["fingerprint"])

    op.create_table(
        "project_version",
        sa.Column("id", UUID(as_uuid=True), primary_key=True, server_default=sa.text("gen_random_uuid()")),
        sa.Column("project_id", UUID(as_uuid=True), sa.ForeignKey("project.id"), nullable=False),
        sa.Column("parent_version_id", UUID(as_uuid=True), sa.ForeignKey("project_version.id")),
        sa.Column("version_number", sa.Integer, nullable=False),
        sa.Column("modification_prompt", sa.Text),
        sa.Column("snapshot_manifest", JSONB, nullable=False),
        sa.Column("created_by", UUID(as_uuid=True), sa.ForeignKey("user_account.id")),
        sa.Column("created_at", TIMESTAMPTZ, server_default=sa.text("now()"), nullable=False),
        sa.UniqueConstraint("project_id", "version_number", name="uq_pv_project_version"),
    )
    op.create_index("idx_pv_project", "project_version", ["project_id"])
    op.create_index("idx_pv_parent", "project_version", ["parent_version_id"])

    # project.current_version_id FK (added after project_version exists)
    op.create_foreign_key(
        "fk_project_current_version",
        "project", "project_version",
        ["current_version_id"], ["id"],
    )

    op.create_table(
        "runcard",
        sa.Column("id", UUID(as_uuid=True), primary_key=True, server_default=sa.text("gen_random_uuid()")),
        sa.Column("project_id", UUID(as_uuid=True), sa.ForeignKey("project.id"), nullable=False),
        sa.Column("project_version_id", UUID(as_uuid=True), sa.ForeignKey("project_version.id"), nullable=False),
        sa.Column("parent_runcard_id", UUID(as_uuid=True), sa.ForeignKey("runcard.id")),
        sa.Column("kind", sa.Text, nullable=False),
        sa.Column("current_state", sa.Text, nullable=False),
        sa.Column("branch_strategy_name", sa.Text),
        sa.Column("data_context", JSONB, server_default="{}"),
        sa.Column("temporal_workflow_id", sa.Text),
        sa.Column("plan_steps", JSONB, server_default="[]"),
        sa.Column("plan_progress", sa.Integer, server_default="0"),
        sa.Column("metadata", JSONB, server_default="{}"),
        sa.Column("created_at", TIMESTAMPTZ, server_default=sa.text("now()"), nullable=False),
        sa.Column("completed_at", TIMESTAMPTZ),
        sa.CheckConstraint("kind IN ('main','branch')", name="ck_runcard_kind"),
    )
    op.create_index("idx_runcard_project", "runcard", ["project_id"])
    op.create_index("idx_runcard_version", "runcard", ["project_version_id"])
    op.create_index("idx_runcard_parent", "runcard", ["parent_runcard_id"])
    op.create_index("idx_runcard_state", "runcard", ["current_state"])

    op.create_table(
        "state_transition",
        sa.Column("id", UUID(as_uuid=True), primary_key=True, server_default=sa.text("gen_random_uuid()")),
        sa.Column("runcard_id", UUID(as_uuid=True), sa.ForeignKey("runcard.id"), nullable=False),
        sa.Column("from_state", sa.Text),
        sa.Column("to_state", sa.Text, nullable=False),
        sa.Column("trigger", sa.Text, nullable=False),
        sa.Column("actor_id", UUID(as_uuid=True), sa.ForeignKey("user_account.id")),
        sa.Column("payload", JSONB, server_default="{}"),
        sa.Column("transitioned_at", TIMESTAMPTZ, server_default=sa.text("now()"), nullable=False),
        sa.CheckConstraint(
            "trigger IN ('auto','review_pass','review_modify','review_reject','dispatch','pause','resume','rollback')",
            name="ck_st_trigger",
        ),
    )
    op.create_index("idx_st_runcard", "state_transition", ["runcard_id", "transitioned_at"])

    op.create_table(
        "stage_output",
        sa.Column("id", UUID(as_uuid=True), primary_key=True, server_default=sa.text("gen_random_uuid()")),
        sa.Column("runcard_id", UUID(as_uuid=True), sa.ForeignKey("runcard.id"), nullable=False),
        sa.Column("stage_name", sa.Text, nullable=False),
        sa.Column("output_type", sa.Text, nullable=False),
        sa.Column("content", JSONB, nullable=False),
        sa.Column("storage_uri", sa.Text),
        sa.Column("is_human_modified", sa.Boolean, server_default="false"),
        sa.Column("superseded_by", UUID(as_uuid=True), sa.ForeignKey("stage_output.id")),
        sa.Column("created_at", TIMESTAMPTZ, server_default=sa.text("now()"), nullable=False),
        sa.CheckConstraint(
            "output_type IN ('plan','data_summary','analysis_report','feature_strategy','ml_plan','train_result','other')",
            name="ck_so_output_type",
        ),
    )
    op.create_index("idx_so_runcard_stage", "stage_output", ["runcard_id", "stage_name"])

    op.create_table(
        "review_record",
        sa.Column("id", UUID(as_uuid=True), primary_key=True, server_default=sa.text("gen_random_uuid()")),
        sa.Column("runcard_id", UUID(as_uuid=True), sa.ForeignKey("runcard.id"), nullable=False),
        sa.Column("stage_output_id", UUID(as_uuid=True), sa.ForeignKey("stage_output.id"), nullable=False),
        sa.Column("review_node", sa.Text, nullable=False),
        sa.Column("action", sa.Text, nullable=False),
        sa.Column("reviewer_id", UUID(as_uuid=True), sa.ForeignKey("user_account.id"), nullable=False),
        sa.Column("comment", sa.Text),
        sa.Column("modifications", JSONB),
        sa.Column("reviewed_at", TIMESTAMPTZ, server_default=sa.text("now()"), nullable=False),
        sa.CheckConstraint("action IN ('accept','modify','reject','escalate')", name="ck_rr_action"),
    )
    op.create_index("idx_rr_runcard", "review_record", ["runcard_id"])

    op.create_table(
        "sandbox_snapshot",
        sa.Column("id", UUID(as_uuid=True), primary_key=True, server_default=sa.text("gen_random_uuid()")),
        sa.Column("runcard_id", UUID(as_uuid=True), sa.ForeignKey("runcard.id"), nullable=False),
        sa.Column("state_at_snapshot", sa.Text, nullable=False),
        sa.Column("storage_uri", sa.Text, nullable=False),
        sa.Column("size_bytes", sa.BigInteger),
        sa.Column("metadata", JSONB, server_default="{}"),
        sa.Column("created_at", TIMESTAMPTZ, server_default=sa.text("now()"), nullable=False),
    )
    op.create_index("idx_ss_runcard", "sandbox_snapshot", ["runcard_id", "created_at"])

    op.create_table(
        "execution_event",
        sa.Column("id", UUID(as_uuid=True), primary_key=True, server_default=sa.text("gen_random_uuid()")),
        sa.Column("runcard_id", UUID(as_uuid=True), sa.ForeignKey("runcard.id"), nullable=False),
        sa.Column("event_type", sa.Text, nullable=False),
        sa.Column("payload", JSONB, nullable=False),
        sa.Column("emitted_at", TIMESTAMPTZ, server_default=sa.text("now()"), nullable=False),
    )
    op.create_index("idx_ee_runcard_time", "execution_event", ["runcard_id", "emitted_at"])

    op.create_table(
        "lifecycle_log",
        sa.Column("id", UUID(as_uuid=True), primary_key=True, server_default=sa.text("gen_random_uuid()")),
        sa.Column("project_id", UUID(as_uuid=True), sa.ForeignKey("project.id"), nullable=False),
        sa.Column("runcard_id", UUID(as_uuid=True), sa.ForeignKey("runcard.id")),
        sa.Column("event", sa.Text, nullable=False),
        sa.Column("actor_id", UUID(as_uuid=True), sa.ForeignKey("user_account.id")),
        sa.Column("details", JSONB, server_default="{}"),
        sa.Column("recorded_at", TIMESTAMPTZ, server_default=sa.text("now()"), nullable=False),
    )
    op.create_index("idx_ll_project", "lifecycle_log", ["project_id", "recorded_at"])

    op.create_table(
        "analysis_pack",
        sa.Column("id", UUID(as_uuid=True), primary_key=True, server_default=sa.text("gen_random_uuid()")),
        sa.Column("project_id", UUID(as_uuid=True), sa.ForeignKey("project.id"), nullable=False),
        sa.Column("source_runcard_id", UUID(as_uuid=True), sa.ForeignKey("runcard.id"), nullable=False),
        sa.Column("storage_uri", sa.Text, nullable=False),
        sa.Column("data_fingerprint", sa.Text, nullable=False),
        sa.Column("data_report", JSONB, nullable=False),
        sa.Column("feature_hints", JSONB, server_default="[]"),
        sa.Column("visibility", sa.Text, nullable=False, server_default="private"),
        sa.Column("metadata", JSONB, server_default="{}"),
        sa.Column("created_at", TIMESTAMPTZ, server_default=sa.text("now()"), nullable=False),
        sa.CheckConstraint("visibility IN ('private','org','public')", name="ck_ap_visibility"),
    )
    op.create_index("idx_ap_project", "analysis_pack", ["project_id"])
    op.create_index("idx_ap_fingerprint", "analysis_pack", ["data_fingerprint"])
    op.create_index("idx_ap_visibility", "analysis_pack", ["visibility"])

    op.create_table(
        "solve_pack",
        sa.Column("id", UUID(as_uuid=True), primary_key=True, server_default=sa.text("gen_random_uuid()")),
        sa.Column("project_id", UUID(as_uuid=True), sa.ForeignKey("project.id"), nullable=False),
        sa.Column("source_runcard_id", UUID(as_uuid=True), sa.ForeignKey("runcard.id"), nullable=False),
        sa.Column("source_analysis_pack_id", UUID(as_uuid=True), sa.ForeignKey("analysis_pack.id")),
        sa.Column("solution_index", sa.Integer, nullable=False, server_default="1"),
        sa.Column("storage_uri", sa.Text, nullable=False),
        sa.Column("ml_report", JSONB, nullable=False),
        sa.Column("manifest", JSONB, nullable=False),
        sa.Column("metadata", JSONB, server_default="{}"),
        sa.Column("created_at", TIMESTAMPTZ, server_default=sa.text("now()"), nullable=False),
    )
    op.create_index("idx_sp_project", "solve_pack", ["project_id"])

    op.create_table(
        "model_registry_entry",
        sa.Column("id", UUID(as_uuid=True), primary_key=True, server_default=sa.text("gen_random_uuid()")),
        sa.Column("solve_pack_id", UUID(as_uuid=True), sa.ForeignKey("solve_pack.id")),
        sa.Column("model_name", sa.Text, nullable=False),
        sa.Column("version", sa.Text, nullable=False),
        sa.Column("model_uri", sa.Text, nullable=False),
        sa.Column("source", sa.Text, nullable=False),
        sa.Column("metrics", JSONB, server_default="{}"),
        sa.Column("share_scope", sa.Text, nullable=False, server_default="platform_only"),
        sa.Column("metadata", JSONB, server_default="{}"),
        sa.Column("registered_at", TIMESTAMPTZ, server_default=sa.text("now()"), nullable=False),
        sa.CheckConstraint("source IN ('automl','finetuned','external')", name="ck_mre_source"),
        sa.CheckConstraint("share_scope IN ('platform_only','org_internal','public')", name="ck_mre_share_scope"),
        sa.UniqueConstraint("model_name", "version", name="uq_mre_name_version"),
    )
    op.create_index("idx_mre_source", "model_registry_entry", ["source"])


def downgrade() -> None:
    op.drop_table("model_registry_entry")
    op.drop_table("solve_pack")
    op.drop_table("analysis_pack")
    op.drop_table("lifecycle_log")
    op.drop_table("execution_event")
    op.drop_table("sandbox_snapshot")
    op.drop_table("review_record")
    op.drop_table("stage_output")
    op.drop_table("state_transition")
    op.drop_table("runcard")
    op.drop_foreign_key("fk_project_current_version", "project")
    op.drop_table("project_version")
    op.drop_table("data_upload")
    op.drop_table("requirement_block")
    op.drop_table("requirement")
    op.drop_table("project")
    op.drop_table("user_account")
    op.drop_table("organization")
