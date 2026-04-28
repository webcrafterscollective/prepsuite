"""prep live main backend

Revision ID: 202604280011
Revises: 202604280010
Create Date: 2026-04-28 11:00:00.000000
"""
# ruff: noqa: E501

from collections.abc import Sequence

import sqlalchemy as sa
from sqlalchemy.dialects import postgresql

from alembic import op

revision: str = "202604280011"
down_revision: str | None = "202604280010"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None

TENANT_POLICY_EXPRESSION = (
    "tenant_id = NULLIF(current_setting('app.current_tenant_id', true), '')::uuid"
)

RLS_TABLES = (
    "live_classes",
    "live_class_participants",
    "live_class_invites",
    "live_class_attendance_snapshots",
    "live_class_recordings",
    "live_class_events",
)


def enable_rls(table_name: str) -> None:
    op.execute(f"ALTER TABLE {table_name} ENABLE ROW LEVEL SECURITY")
    op.execute(f"ALTER TABLE {table_name} FORCE ROW LEVEL SECURITY")
    op.execute(
        f"""
        CREATE POLICY {table_name}_tenant_isolation
        ON {table_name}
        USING ({TENANT_POLICY_EXPRESSION})
        WITH CHECK ({TENANT_POLICY_EXPRESSION})
        """
    )


def disable_rls(table_name: str) -> None:
    op.execute(f"DROP POLICY IF EXISTS {table_name}_tenant_isolation ON {table_name}")
    op.execute(f"ALTER TABLE {table_name} DISABLE ROW LEVEL SECURITY")


def grant_app_role() -> None:
    op.execute(
        """
        DO
        $$
        BEGIN
            IF EXISTS (SELECT FROM pg_roles WHERE rolname = 'prepsuite_app') THEN
                GRANT USAGE ON SCHEMA public TO prepsuite_app;
                GRANT SELECT, INSERT, UPDATE, DELETE ON ALL TABLES IN SCHEMA public TO prepsuite_app;
            END IF;
        END
        $$;
        """
    )


def upgrade() -> None:
    op.create_table(
        "live_classes",
        sa.Column("tenant_id", postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column("class_code", sa.String(length=80), nullable=False),
        sa.Column("title", sa.String(length=240), nullable=False),
        sa.Column("description", sa.Text(), nullable=True),
        sa.Column("course_id", postgresql.UUID(as_uuid=True), nullable=True),
        sa.Column("batch_id", postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column("instructor_id", postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column("starts_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("ends_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("duration_minutes", sa.Integer(), nullable=False),
        sa.Column("join_before_minutes", sa.Integer(), server_default=sa.text("15"), nullable=False),
        sa.Column("join_after_minutes", sa.Integer(), server_default=sa.text("15"), nullable=False),
        sa.Column("capacity", sa.Integer(), nullable=False),
        sa.Column("status", sa.String(length=32), server_default="scheduled", nullable=False),
        sa.Column("live_provider", sa.String(length=32), server_default="mediasoup", nullable=False),
        sa.Column("live_room_id", sa.String(length=160), nullable=True),
        sa.Column("link", sa.Text(), nullable=False),
        sa.Column("settings", postgresql.JSONB(astext_type=sa.Text()), server_default=sa.text("'{}'::jsonb"), nullable=False),
        sa.Column("created_by", postgresql.UUID(as_uuid=True), nullable=True),
        sa.Column("id", postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False),
        sa.Column("updated_at", sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False),
        sa.ForeignKeyConstraint(["batch_id"], ["batches.id"], name=op.f("fk_live_classes_batch_id_batches"), ondelete="CASCADE"),
        sa.ForeignKeyConstraint(["course_id"], ["courses.id"], name=op.f("fk_live_classes_course_id_courses"), ondelete="SET NULL"),
        sa.ForeignKeyConstraint(["instructor_id"], ["employees.id"], name=op.f("fk_live_classes_instructor_id_employees"), ondelete="RESTRICT"),
        sa.ForeignKeyConstraint(["tenant_id"], ["tenants.id"], name=op.f("fk_live_classes_tenant_id_tenants"), ondelete="CASCADE"),
        sa.PrimaryKeyConstraint("id", name=op.f("pk_live_classes")),
        sa.UniqueConstraint("class_code", name="uq_live_classes_class_code"),
    )
    op.create_index(op.f("ix_live_classes_tenant_id"), "live_classes", ["tenant_id"])
    op.create_index("ix_live_classes_tenant_batch", "live_classes", ["tenant_id", "batch_id"])
    op.create_index("ix_live_classes_tenant_instructor", "live_classes", ["tenant_id", "instructor_id"])
    op.create_index("ix_live_classes_tenant_starts", "live_classes", ["tenant_id", "starts_at"])
    op.create_index("ix_live_classes_tenant_status", "live_classes", ["tenant_id", "status"])

    op.create_table(
        "live_class_participants",
        sa.Column("tenant_id", postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column("live_class_id", postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column("user_id", postgresql.UUID(as_uuid=True), nullable=True),
        sa.Column("student_id", postgresql.UUID(as_uuid=True), nullable=True),
        sa.Column("employee_id", postgresql.UUID(as_uuid=True), nullable=True),
        sa.Column("participant_role", sa.String(length=32), server_default="student", nullable=False),
        sa.Column("join_status", sa.String(length=32), server_default="allowed", nullable=False),
        sa.Column("joined_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("left_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("total_duration_seconds", sa.Integer(), server_default=sa.text("0"), nullable=False),
        sa.Column("id", postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False),
        sa.Column("updated_at", sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False),
        sa.ForeignKeyConstraint(["employee_id"], ["employees.id"], name=op.f("fk_live_class_participants_employee_id_employees"), ondelete="SET NULL"),
        sa.ForeignKeyConstraint(["live_class_id"], ["live_classes.id"], name=op.f("fk_live_class_participants_live_class_id_live_classes"), ondelete="CASCADE"),
        sa.ForeignKeyConstraint(["student_id"], ["students.id"], name=op.f("fk_live_class_participants_student_id_students"), ondelete="SET NULL"),
        sa.ForeignKeyConstraint(["tenant_id"], ["tenants.id"], name=op.f("fk_live_class_participants_tenant_id_tenants"), ondelete="CASCADE"),
        sa.PrimaryKeyConstraint("id", name=op.f("pk_live_class_participants")),
    )
    op.create_index(op.f("ix_live_class_participants_tenant_id"), "live_class_participants", ["tenant_id"])
    op.create_index("ix_live_class_participants_tenant_class", "live_class_participants", ["tenant_id", "live_class_id"])
    op.create_index("ix_live_class_participants_tenant_employee", "live_class_participants", ["tenant_id", "employee_id"])
    op.create_index("ix_live_class_participants_tenant_student", "live_class_participants", ["tenant_id", "student_id"])
    op.create_index("ix_live_class_participants_tenant_user", "live_class_participants", ["tenant_id", "user_id"])

    op.create_table(
        "live_class_invites",
        sa.Column("tenant_id", postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column("live_class_id", postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column("email", sa.String(length=320), nullable=False),
        sa.Column("token_hash", sa.String(length=128), nullable=True),
        sa.Column("participant_role", sa.String(length=32), server_default="guest", nullable=False),
        sa.Column("status", sa.String(length=32), server_default="pending", nullable=False),
        sa.Column("expires_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("accepted_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("id", postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False),
        sa.Column("updated_at", sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False),
        sa.ForeignKeyConstraint(["live_class_id"], ["live_classes.id"], name=op.f("fk_live_class_invites_live_class_id_live_classes"), ondelete="CASCADE"),
        sa.ForeignKeyConstraint(["tenant_id"], ["tenants.id"], name=op.f("fk_live_class_invites_tenant_id_tenants"), ondelete="CASCADE"),
        sa.PrimaryKeyConstraint("id", name=op.f("pk_live_class_invites")),
        sa.UniqueConstraint("tenant_id", "live_class_id", "email", name="uq_live_class_invites_email"),
    )
    op.create_index(op.f("ix_live_class_invites_tenant_id"), "live_class_invites", ["tenant_id"])
    op.create_index("ix_live_class_invites_tenant_class", "live_class_invites", ["tenant_id", "live_class_id"])

    op.create_table(
        "live_class_attendance_snapshots",
        sa.Column("tenant_id", postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column("live_class_id", postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column("captured_at", sa.DateTime(timezone=True), server_default=sa.text("now()"), nullable=False),
        sa.Column("participant_count", sa.Integer(), nullable=False),
        sa.Column("payload", postgresql.JSONB(astext_type=sa.Text()), server_default=sa.text("'{}'::jsonb"), nullable=False),
        sa.Column("id", postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False),
        sa.Column("updated_at", sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False),
        sa.ForeignKeyConstraint(["live_class_id"], ["live_classes.id"], name=op.f("fk_live_class_attendance_snapshots_live_class_id_live_classes"), ondelete="CASCADE"),
        sa.ForeignKeyConstraint(["tenant_id"], ["tenants.id"], name=op.f("fk_live_class_attendance_snapshots_tenant_id_tenants"), ondelete="CASCADE"),
        sa.PrimaryKeyConstraint("id", name=op.f("pk_live_class_attendance_snapshots")),
    )
    op.create_index(op.f("ix_live_class_attendance_snapshots_tenant_id"), "live_class_attendance_snapshots", ["tenant_id"])
    op.create_index("ix_live_class_attendance_snapshots_tenant_class", "live_class_attendance_snapshots", ["tenant_id", "live_class_id"])

    op.create_table(
        "live_class_recordings",
        sa.Column("tenant_id", postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column("live_class_id", postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column("provider_recording_id", sa.String(length=160), nullable=True),
        sa.Column("storage_key", sa.Text(), nullable=True),
        sa.Column("playback_url", sa.Text(), nullable=True),
        sa.Column("duration_seconds", sa.Integer(), nullable=True),
        sa.Column("status", sa.String(length=32), server_default="processing", nullable=False),
        sa.Column("metadata", postgresql.JSONB(astext_type=sa.Text()), server_default=sa.text("'{}'::jsonb"), nullable=False),
        sa.Column("id", postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False),
        sa.Column("updated_at", sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False),
        sa.ForeignKeyConstraint(["live_class_id"], ["live_classes.id"], name=op.f("fk_live_class_recordings_live_class_id_live_classes"), ondelete="CASCADE"),
        sa.ForeignKeyConstraint(["tenant_id"], ["tenants.id"], name=op.f("fk_live_class_recordings_tenant_id_tenants"), ondelete="CASCADE"),
        sa.PrimaryKeyConstraint("id", name=op.f("pk_live_class_recordings")),
    )
    op.create_index(op.f("ix_live_class_recordings_tenant_id"), "live_class_recordings", ["tenant_id"])
    op.create_index("ix_live_class_recordings_tenant_class", "live_class_recordings", ["tenant_id", "live_class_id"])

    op.create_table(
        "live_class_events",
        sa.Column("tenant_id", postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column("live_class_id", postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column("participant_id", postgresql.UUID(as_uuid=True), nullable=True),
        sa.Column("event_type", sa.String(length=80), nullable=False),
        sa.Column("occurred_at", sa.DateTime(timezone=True), server_default=sa.text("now()"), nullable=False),
        sa.Column("payload", postgresql.JSONB(astext_type=sa.Text()), server_default=sa.text("'{}'::jsonb"), nullable=False),
        sa.Column("id", postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False),
        sa.Column("updated_at", sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False),
        sa.ForeignKeyConstraint(["live_class_id"], ["live_classes.id"], name=op.f("fk_live_class_events_live_class_id_live_classes"), ondelete="CASCADE"),
        sa.ForeignKeyConstraint(["participant_id"], ["live_class_participants.id"], name=op.f("fk_live_class_events_participant_id_live_class_participants"), ondelete="SET NULL"),
        sa.ForeignKeyConstraint(["tenant_id"], ["tenants.id"], name=op.f("fk_live_class_events_tenant_id_tenants"), ondelete="CASCADE"),
        sa.PrimaryKeyConstraint("id", name=op.f("pk_live_class_events")),
    )
    op.create_index(op.f("ix_live_class_events_tenant_id"), "live_class_events", ["tenant_id"])
    op.create_index("ix_live_class_events_tenant_class", "live_class_events", ["tenant_id", "live_class_id"])
    op.create_index("ix_live_class_events_tenant_type", "live_class_events", ["tenant_id", "event_type"])

    for table_name in RLS_TABLES:
        enable_rls(table_name)
    grant_app_role()


def downgrade() -> None:
    for table_name in reversed(RLS_TABLES):
        disable_rls(table_name)

    op.drop_index("ix_live_class_events_tenant_type", table_name="live_class_events")
    op.drop_index("ix_live_class_events_tenant_class", table_name="live_class_events")
    op.drop_index(op.f("ix_live_class_events_tenant_id"), table_name="live_class_events")
    op.drop_table("live_class_events")

    op.drop_index("ix_live_class_recordings_tenant_class", table_name="live_class_recordings")
    op.drop_index(op.f("ix_live_class_recordings_tenant_id"), table_name="live_class_recordings")
    op.drop_table("live_class_recordings")

    op.drop_index("ix_live_class_attendance_snapshots_tenant_class", table_name="live_class_attendance_snapshots")
    op.drop_index(op.f("ix_live_class_attendance_snapshots_tenant_id"), table_name="live_class_attendance_snapshots")
    op.drop_table("live_class_attendance_snapshots")

    op.drop_index("ix_live_class_invites_tenant_class", table_name="live_class_invites")
    op.drop_index(op.f("ix_live_class_invites_tenant_id"), table_name="live_class_invites")
    op.drop_table("live_class_invites")

    op.drop_index("ix_live_class_participants_tenant_user", table_name="live_class_participants")
    op.drop_index("ix_live_class_participants_tenant_student", table_name="live_class_participants")
    op.drop_index("ix_live_class_participants_tenant_employee", table_name="live_class_participants")
    op.drop_index("ix_live_class_participants_tenant_class", table_name="live_class_participants")
    op.drop_index(op.f("ix_live_class_participants_tenant_id"), table_name="live_class_participants")
    op.drop_table("live_class_participants")

    op.drop_index("ix_live_classes_tenant_status", table_name="live_classes")
    op.drop_index("ix_live_classes_tenant_starts", table_name="live_classes")
    op.drop_index("ix_live_classes_tenant_instructor", table_name="live_classes")
    op.drop_index("ix_live_classes_tenant_batch", table_name="live_classes")
    op.drop_index(op.f("ix_live_classes_tenant_id"), table_name="live_classes")
    op.drop_table("live_classes")
