"""prepaccess auth rbac

Revision ID: 202604280003
Revises: 202604280002
Create Date: 2026-04-28 02:00:00.000000
"""
# ruff: noqa: E501

from collections.abc import Sequence

import sqlalchemy as sa
from sqlalchemy.dialects import postgresql

from alembic import op

revision: str = "202604280003"
down_revision: str | None = "202604280002"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None

TENANT_POLICY_EXPRESSION = (
    "tenant_id = NULLIF(current_setting('app.current_tenant_id', true), '')::uuid"
)
USER_POLICY_EXPRESSION = "user_id = NULLIF(current_setting('app.current_user_id', true), '')::uuid"
CURRENT_USER_ID = "NULLIF(current_setting('app.current_user_id', true), '')::uuid"

RLS_TABLES = (
    "users",
    "user_profiles",
    "roles",
    "role_permissions",
    "user_roles",
    "refresh_tokens",
    "login_sessions",
    "login_history",
    "password_reset_tokens",
    "invitation_tokens",
)


def enable_rls(table_name: str, expression: str, check_expression: str | None = None) -> None:
    op.execute(f"ALTER TABLE {table_name} ENABLE ROW LEVEL SECURITY")
    op.execute(f"ALTER TABLE {table_name} FORCE ROW LEVEL SECURITY")
    op.execute(
        f"""
        CREATE POLICY {table_name}_tenant_access
        ON {table_name}
        USING ({expression})
        WITH CHECK ({check_expression or expression})
        """
    )


def disable_rls(table_name: str) -> None:
    op.execute(f"DROP POLICY IF EXISTS {table_name}_tenant_access ON {table_name}")
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
        "users",
        sa.Column("tenant_id", postgresql.UUID(as_uuid=True), nullable=True),
        sa.Column("email", sa.String(length=320), nullable=False),
        sa.Column("phone", sa.String(length=32), nullable=True),
        sa.Column("password_hash", sa.Text(), nullable=False),
        sa.Column("status", sa.String(length=32), server_default="active", nullable=False),
        sa.Column("user_type", sa.String(length=40), server_default="employee", nullable=False),
        sa.Column("last_login_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("deleted_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("id", postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False),
        sa.Column("updated_at", sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False),
        sa.ForeignKeyConstraint(["tenant_id"], ["tenants.id"], name=op.f("fk_users_tenant_id_tenants"), ondelete="CASCADE"),
        sa.PrimaryKeyConstraint("id", name=op.f("pk_users")),
        sa.UniqueConstraint("tenant_id", "email", name="uq_users_tenant_id_email"),
    )
    op.create_index("ix_users_email", "users", ["email"])
    op.create_index(op.f("ix_users_tenant_id"), "users", ["tenant_id"])
    op.create_index("ix_users_tenant_status", "users", ["tenant_id", "status"])
    op.create_index(op.f("ix_users_deleted_at"), "users", ["deleted_at"])

    op.create_table(
        "user_profiles",
        sa.Column("tenant_id", postgresql.UUID(as_uuid=True), nullable=True),
        sa.Column("user_id", postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column("first_name", sa.String(length=120), nullable=True),
        sa.Column("last_name", sa.String(length=120), nullable=True),
        sa.Column("display_name", sa.String(length=240), nullable=True),
        sa.Column("avatar_url", sa.Text(), nullable=True),
        sa.Column("profile_data", postgresql.JSONB(astext_type=sa.Text()), server_default=sa.text("'{}'::jsonb"), nullable=False),
        sa.Column("id", postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False),
        sa.Column("updated_at", sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False),
        sa.ForeignKeyConstraint(["tenant_id"], ["tenants.id"], name=op.f("fk_user_profiles_tenant_id_tenants"), ondelete="CASCADE"),
        sa.ForeignKeyConstraint(["user_id"], ["users.id"], name=op.f("fk_user_profiles_user_id_users"), ondelete="CASCADE"),
        sa.PrimaryKeyConstraint("id", name=op.f("pk_user_profiles")),
        sa.UniqueConstraint("user_id", name="uq_user_profiles_user_id"),
    )
    op.create_index(op.f("ix_user_profiles_tenant_id"), "user_profiles", ["tenant_id"])
    op.create_index(op.f("ix_user_profiles_user_id"), "user_profiles", ["user_id"])

    op.create_table(
        "permissions",
        sa.Column("code", sa.String(length=180), nullable=False),
        sa.Column("app_code", sa.String(length=80), nullable=False),
        sa.Column("resource", sa.String(length=80), nullable=False),
        sa.Column("action", sa.String(length=80), nullable=False),
        sa.Column("description", sa.Text(), nullable=True),
        sa.Column("is_active", sa.Boolean(), nullable=False),
        sa.Column("id", postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False),
        sa.Column("updated_at", sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False),
        sa.PrimaryKeyConstraint("id", name=op.f("pk_permissions")),
        sa.UniqueConstraint("code", name="uq_permissions_code"),
    )
    op.create_index("ix_permissions_app_resource_action", "permissions", ["app_code", "resource", "action"])

    op.create_table(
        "roles",
        sa.Column("tenant_id", postgresql.UUID(as_uuid=True), nullable=True),
        sa.Column("code", sa.String(length=120), nullable=False),
        sa.Column("name", sa.String(length=160), nullable=False),
        sa.Column("description", sa.Text(), nullable=True),
        sa.Column("is_system", sa.Boolean(), nullable=False),
        sa.Column("is_default", sa.Boolean(), nullable=False),
        sa.Column("deleted_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("id", postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False),
        sa.Column("updated_at", sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False),
        sa.ForeignKeyConstraint(["tenant_id"], ["tenants.id"], name=op.f("fk_roles_tenant_id_tenants"), ondelete="CASCADE"),
        sa.PrimaryKeyConstraint("id", name=op.f("pk_roles")),
        sa.UniqueConstraint("tenant_id", "code", name="uq_roles_tenant_id_code"),
    )
    op.create_index("ix_roles_tenant_id", "roles", ["tenant_id"])
    op.create_index(op.f("ix_roles_deleted_at"), "roles", ["deleted_at"])

    op.create_table(
        "role_permissions",
        sa.Column("tenant_id", postgresql.UUID(as_uuid=True), nullable=True),
        sa.Column("role_id", postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column("permission_id", postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column("id", postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False),
        sa.Column("updated_at", sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False),
        sa.ForeignKeyConstraint(["permission_id"], ["permissions.id"], name=op.f("fk_role_permissions_permission_id_permissions"), ondelete="CASCADE"),
        sa.ForeignKeyConstraint(["role_id"], ["roles.id"], name=op.f("fk_role_permissions_role_id_roles"), ondelete="CASCADE"),
        sa.ForeignKeyConstraint(["tenant_id"], ["tenants.id"], name=op.f("fk_role_permissions_tenant_id_tenants"), ondelete="CASCADE"),
        sa.PrimaryKeyConstraint("id", name=op.f("pk_role_permissions")),
        sa.UniqueConstraint("role_id", "permission_id", name="uq_role_permissions_role_permission"),
    )
    op.create_index("ix_role_permissions_tenant_id", "role_permissions", ["tenant_id"])

    op.create_table(
        "user_roles",
        sa.Column("tenant_id", postgresql.UUID(as_uuid=True), nullable=True),
        sa.Column("user_id", postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column("role_id", postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column("assigned_by", postgresql.UUID(as_uuid=True), nullable=True),
        sa.Column("assigned_at", sa.DateTime(timezone=True), server_default=sa.text("now()"), nullable=False),
        sa.Column("expires_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("id", postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False),
        sa.Column("updated_at", sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False),
        sa.ForeignKeyConstraint(["role_id"], ["roles.id"], name=op.f("fk_user_roles_role_id_roles"), ondelete="CASCADE"),
        sa.ForeignKeyConstraint(["tenant_id"], ["tenants.id"], name=op.f("fk_user_roles_tenant_id_tenants"), ondelete="CASCADE"),
        sa.ForeignKeyConstraint(["user_id"], ["users.id"], name=op.f("fk_user_roles_user_id_users"), ondelete="CASCADE"),
        sa.PrimaryKeyConstraint("id", name=op.f("pk_user_roles")),
        sa.UniqueConstraint("tenant_id", "user_id", "role_id", name="uq_user_roles_tenant_user_role"),
    )
    op.create_index(op.f("ix_user_roles_tenant_id"), "user_roles", ["tenant_id"])
    op.create_index("ix_user_roles_user_id", "user_roles", ["user_id"])

    op.create_table(
        "refresh_tokens",
        sa.Column("tenant_id", postgresql.UUID(as_uuid=True), nullable=True),
        sa.Column("user_id", postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column("token_hash", sa.String(length=128), nullable=False),
        sa.Column("family_id", postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column("parent_token_id", postgresql.UUID(as_uuid=True), nullable=True),
        sa.Column("status", sa.String(length=32), server_default="active", nullable=False),
        sa.Column("expires_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("revoked_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("replaced_by_token_id", postgresql.UUID(as_uuid=True), nullable=True),
        sa.Column("id", postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False),
        sa.Column("updated_at", sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False),
        sa.ForeignKeyConstraint(["parent_token_id"], ["refresh_tokens.id"], name=op.f("fk_refresh_tokens_parent_token_id_refresh_tokens"), ondelete="SET NULL"),
        sa.ForeignKeyConstraint(["tenant_id"], ["tenants.id"], name=op.f("fk_refresh_tokens_tenant_id_tenants"), ondelete="CASCADE"),
        sa.ForeignKeyConstraint(["user_id"], ["users.id"], name=op.f("fk_refresh_tokens_user_id_users"), ondelete="CASCADE"),
        sa.PrimaryKeyConstraint("id", name=op.f("pk_refresh_tokens")),
        sa.UniqueConstraint("token_hash", name="uq_refresh_tokens_token_hash"),
    )
    op.create_index(op.f("ix_refresh_tokens_tenant_id"), "refresh_tokens", ["tenant_id"])
    op.create_index("ix_refresh_tokens_family_id", "refresh_tokens", ["family_id"])
    op.create_index("ix_refresh_tokens_user_status", "refresh_tokens", ["user_id", "status"])

    op.create_table(
        "login_sessions",
        sa.Column("tenant_id", postgresql.UUID(as_uuid=True), nullable=True),
        sa.Column("user_id", postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column("refresh_token_id", postgresql.UUID(as_uuid=True), nullable=True),
        sa.Column("ip_address", postgresql.INET(), nullable=True),
        sa.Column("user_agent", sa.Text(), nullable=True),
        sa.Column("last_seen_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("ended_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("status", sa.String(length=32), server_default="active", nullable=False),
        sa.Column("id", postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False),
        sa.Column("updated_at", sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False),
        sa.ForeignKeyConstraint(["refresh_token_id"], ["refresh_tokens.id"], name=op.f("fk_login_sessions_refresh_token_id_refresh_tokens"), ondelete="SET NULL"),
        sa.ForeignKeyConstraint(["tenant_id"], ["tenants.id"], name=op.f("fk_login_sessions_tenant_id_tenants"), ondelete="CASCADE"),
        sa.ForeignKeyConstraint(["user_id"], ["users.id"], name=op.f("fk_login_sessions_user_id_users"), ondelete="CASCADE"),
        sa.PrimaryKeyConstraint("id", name=op.f("pk_login_sessions")),
    )
    op.create_index(op.f("ix_login_sessions_tenant_id"), "login_sessions", ["tenant_id"])
    op.create_index(op.f("ix_login_sessions_user_id"), "login_sessions", ["user_id"])

    op.create_table(
        "login_history",
        sa.Column("tenant_id", postgresql.UUID(as_uuid=True), nullable=True),
        sa.Column("user_id", postgresql.UUID(as_uuid=True), nullable=True),
        sa.Column("email", sa.String(length=320), nullable=False),
        sa.Column("success", sa.Boolean(), nullable=False),
        sa.Column("failure_reason", sa.String(length=120), nullable=True),
        sa.Column("ip_address", postgresql.INET(), nullable=True),
        sa.Column("user_agent", sa.Text(), nullable=True),
        sa.Column("id", postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False),
        sa.Column("updated_at", sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False),
        sa.ForeignKeyConstraint(["tenant_id"], ["tenants.id"], name=op.f("fk_login_history_tenant_id_tenants"), ondelete="CASCADE"),
        sa.ForeignKeyConstraint(["user_id"], ["users.id"], name=op.f("fk_login_history_user_id_users"), ondelete="SET NULL"),
        sa.PrimaryKeyConstraint("id", name=op.f("pk_login_history")),
    )
    op.create_index(op.f("ix_login_history_tenant_id"), "login_history", ["tenant_id"])
    op.create_index(op.f("ix_login_history_user_id"), "login_history", ["user_id"])
    op.create_index("ix_login_history_email_created_at", "login_history", ["email", "created_at"])

    op.create_table(
        "password_reset_tokens",
        sa.Column("tenant_id", postgresql.UUID(as_uuid=True), nullable=True),
        sa.Column("user_id", postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column("token_hash", sa.String(length=128), nullable=False),
        sa.Column("expires_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("used_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("id", postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False),
        sa.Column("updated_at", sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False),
        sa.ForeignKeyConstraint(["tenant_id"], ["tenants.id"], name=op.f("fk_password_reset_tokens_tenant_id_tenants"), ondelete="CASCADE"),
        sa.ForeignKeyConstraint(["user_id"], ["users.id"], name=op.f("fk_password_reset_tokens_user_id_users"), ondelete="CASCADE"),
        sa.PrimaryKeyConstraint("id", name=op.f("pk_password_reset_tokens")),
        sa.UniqueConstraint("token_hash", name="uq_password_reset_tokens_token_hash"),
    )
    op.create_index(op.f("ix_password_reset_tokens_tenant_id"), "password_reset_tokens", ["tenant_id"])
    op.create_index(op.f("ix_password_reset_tokens_user_id"), "password_reset_tokens", ["user_id"])

    op.create_table(
        "invitation_tokens",
        sa.Column("tenant_id", postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column("email", sa.String(length=320), nullable=False),
        sa.Column("role_id", postgresql.UUID(as_uuid=True), nullable=True),
        sa.Column("token_hash", sa.String(length=128), nullable=False),
        sa.Column("invited_by", postgresql.UUID(as_uuid=True), nullable=True),
        sa.Column("accepted_user_id", postgresql.UUID(as_uuid=True), nullable=True),
        sa.Column("status", sa.String(length=32), server_default="pending", nullable=False),
        sa.Column("expires_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("accepted_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("revoked_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("id", postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False),
        sa.Column("updated_at", sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False),
        sa.ForeignKeyConstraint(["role_id"], ["roles.id"], name=op.f("fk_invitation_tokens_role_id_roles"), ondelete="SET NULL"),
        sa.ForeignKeyConstraint(["tenant_id"], ["tenants.id"], name=op.f("fk_invitation_tokens_tenant_id_tenants"), ondelete="CASCADE"),
        sa.PrimaryKeyConstraint("id", name=op.f("pk_invitation_tokens")),
        sa.UniqueConstraint("token_hash", name="uq_invitation_tokens_token_hash"),
    )
    op.create_index(op.f("ix_invitation_tokens_tenant_id"), "invitation_tokens", ["tenant_id"])

    op.create_foreign_key(
        "fk_tenant_users_user_id_users",
        "tenant_users",
        "users",
        ["user_id"],
        ["id"],
        ondelete="CASCADE",
    )

    nullable_tenant_expression = f"tenant_id IS NULL OR {TENANT_POLICY_EXPRESSION}"
    user_visible_expression = (
        f"tenant_id IS NULL OR {TENANT_POLICY_EXPRESSION} OR id = {CURRENT_USER_ID}"
    )
    user_child_expression = (
        f"tenant_id IS NULL OR {TENANT_POLICY_EXPRESSION} OR {USER_POLICY_EXPRESSION}"
    )

    enable_rls("users", user_visible_expression, f"tenant_id IS NULL OR {TENANT_POLICY_EXPRESSION}")
    enable_rls("user_profiles", user_child_expression, f"tenant_id IS NULL OR {TENANT_POLICY_EXPRESSION}")
    enable_rls("roles", nullable_tenant_expression)
    enable_rls("role_permissions", nullable_tenant_expression)
    enable_rls("user_roles", user_child_expression)
    enable_rls("refresh_tokens", user_child_expression)
    enable_rls("login_sessions", user_child_expression)
    enable_rls("login_history", nullable_tenant_expression)
    enable_rls("password_reset_tokens", user_child_expression)
    enable_rls("invitation_tokens", TENANT_POLICY_EXPRESSION)
    grant_app_role()


def downgrade() -> None:
    for table_name in reversed(RLS_TABLES):
        disable_rls(table_name)

    op.drop_constraint("fk_tenant_users_user_id_users", "tenant_users", type_="foreignkey")
    op.drop_index(op.f("ix_invitation_tokens_tenant_id"), table_name="invitation_tokens")
    op.drop_table("invitation_tokens")
    op.drop_index(op.f("ix_password_reset_tokens_user_id"), table_name="password_reset_tokens")
    op.drop_index(op.f("ix_password_reset_tokens_tenant_id"), table_name="password_reset_tokens")
    op.drop_table("password_reset_tokens")
    op.drop_index("ix_login_history_email_created_at", table_name="login_history")
    op.drop_index(op.f("ix_login_history_user_id"), table_name="login_history")
    op.drop_index(op.f("ix_login_history_tenant_id"), table_name="login_history")
    op.drop_table("login_history")
    op.drop_index(op.f("ix_login_sessions_user_id"), table_name="login_sessions")
    op.drop_index(op.f("ix_login_sessions_tenant_id"), table_name="login_sessions")
    op.drop_table("login_sessions")
    op.drop_index("ix_refresh_tokens_user_status", table_name="refresh_tokens")
    op.drop_index("ix_refresh_tokens_family_id", table_name="refresh_tokens")
    op.drop_index(op.f("ix_refresh_tokens_tenant_id"), table_name="refresh_tokens")
    op.drop_table("refresh_tokens")
    op.drop_index("ix_user_roles_user_id", table_name="user_roles")
    op.drop_index(op.f("ix_user_roles_tenant_id"), table_name="user_roles")
    op.drop_table("user_roles")
    op.drop_index("ix_role_permissions_tenant_id", table_name="role_permissions")
    op.drop_table("role_permissions")
    op.drop_index(op.f("ix_roles_deleted_at"), table_name="roles")
    op.drop_index("ix_roles_tenant_id", table_name="roles")
    op.drop_table("roles")
    op.drop_index("ix_permissions_app_resource_action", table_name="permissions")
    op.drop_table("permissions")
    op.drop_index(op.f("ix_user_profiles_user_id"), table_name="user_profiles")
    op.drop_index(op.f("ix_user_profiles_tenant_id"), table_name="user_profiles")
    op.drop_table("user_profiles")
    op.drop_index(op.f("ix_users_deleted_at"), table_name="users")
    op.drop_index("ix_users_tenant_status", table_name="users")
    op.drop_index(op.f("ix_users_tenant_id"), table_name="users")
    op.drop_index("ix_users_email", table_name="users")
    op.drop_table("users")
