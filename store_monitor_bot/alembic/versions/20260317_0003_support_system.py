"""Add support system tables and timezone-aware timestamp columns.

Revision ID: 20260317_0003
Revises: 20260317_0002
Create Date: 2026-03-18 03:10:00
"""

from __future__ import annotations

from alembic import op
import sqlalchemy as sa


# revision identifiers, used by Alembic.
revision = "20260317_0003"
down_revision = "20260317_0002"
branch_labels = None
depends_on = None


support_ticket_status = sa.Enum(
    "open",
    "in_progress",
    "waiting_user",
    "resolved",
    "closed",
    name="supportticketstatus",
)
support_ticket_priority = sa.Enum(
    "low",
    "normal",
    "high",
    "urgent",
    name="supportticketpriority",
)
support_department = sa.Enum(
    "support",
    "billing",
    "technical",
    "general",
    "management",
    name="supportdepartment",
)
support_sender_type = sa.Enum(
    "user",
    "admin",
    "system",
    "bot",
    name="supportsendertype",
)
support_message_type = sa.Enum(
    "text",
    "image",
    "file",
    "voice",
    "system",
    name="supportmessagetype",
)


def _inspector():
    return sa.inspect(op.get_bind())


def _has_table(table_name: str) -> bool:
    return _inspector().has_table(table_name)


def _has_index(table_name: str, index_name: str) -> bool:
    return any(idx.get("name") == index_name for idx in _inspector().get_indexes(table_name))


def _create_enums() -> None:
    bind = op.get_bind()
    if bind.dialect.name == "postgresql":
        support_ticket_status.create(bind, checkfirst=True)
        support_ticket_priority.create(bind, checkfirst=True)
        support_department.create(bind, checkfirst=True)
        support_sender_type.create(bind, checkfirst=True)
        support_message_type.create(bind, checkfirst=True)


def _drop_enums() -> None:
    bind = op.get_bind()
    if bind.dialect.name == "postgresql":
        support_message_type.drop(bind, checkfirst=True)
        support_sender_type.drop(bind, checkfirst=True)
        support_department.drop(bind, checkfirst=True)
        support_ticket_priority.drop(bind, checkfirst=True)
        support_ticket_status.drop(bind, checkfirst=True)


def _alter_timestamp_columns() -> None:
    if _has_table("admin_notifications"):
        with op.batch_alter_table("admin_notifications") as batch_op:
            batch_op.alter_column(
                "created_at",
                existing_type=sa.DateTime(),
                type_=sa.DateTime(timezone=True),
                existing_nullable=False,
                existing_server_default=sa.func.now(),
            )

    if _has_table("user_activities"):
        with op.batch_alter_table("user_activities") as batch_op:
            batch_op.alter_column(
                "created_at",
                existing_type=sa.DateTime(),
                type_=sa.DateTime(timezone=True),
                existing_nullable=False,
                existing_server_default=sa.func.now(),
            )

    if _has_table("user_sessions"):
        with op.batch_alter_table("user_sessions") as batch_op:
            batch_op.alter_column(
                "started_at",
                existing_type=sa.DateTime(),
                type_=sa.DateTime(timezone=True),
                existing_nullable=False,
                existing_server_default=sa.func.now(),
            )
            batch_op.alter_column(
                "last_active",
                existing_type=sa.DateTime(),
                type_=sa.DateTime(timezone=True),
                existing_nullable=False,
                existing_server_default=sa.func.now(),
            )


def upgrade() -> None:
    _create_enums()
    _alter_timestamp_columns()

    if not _has_table("support_tickets"):
        op.create_table(
            "support_tickets",
            sa.Column("id", sa.Integer(), primary_key=True, autoincrement=True),
            sa.Column("ticket_number", sa.String(length=20), nullable=False, unique=True),
            sa.Column("user_id", sa.Integer(), sa.ForeignKey("users.id"), nullable=False),
            sa.Column("subject", sa.String(length=300), nullable=True),
            sa.Column("status", support_ticket_status, nullable=False, server_default="open"),
            sa.Column("priority", support_ticket_priority, nullable=False, server_default="normal"),
            sa.Column("department", support_department, nullable=False, server_default="general"),
            sa.Column("assigned_to", sa.Integer(), sa.ForeignKey("admin_users.id"), nullable=True),
            sa.Column("messages_count", sa.Integer(), nullable=False, server_default="0"),
            sa.Column("last_message_at", sa.DateTime(timezone=True), nullable=True),
            sa.Column("first_response_at", sa.DateTime(timezone=True), nullable=True),
            sa.Column("resolved_at", sa.DateTime(timezone=True), nullable=True),
            sa.Column("created_at", sa.DateTime(timezone=True), nullable=False, server_default=sa.func.now()),
            sa.Column("updated_at", sa.DateTime(timezone=True), nullable=False, server_default=sa.func.now()),
        )
        op.create_index("ix_support_tickets_user_id", "support_tickets", ["user_id"])
        op.create_index("ix_support_tickets_status", "support_tickets", ["status"])
        op.create_index("ix_support_tickets_created_at", "support_tickets", ["created_at"])
        op.create_index(
            "ix_support_tickets_user_status_created",
            "support_tickets",
            ["user_id", "status", "created_at"],
        )

    if not _has_table("support_messages"):
        op.create_table(
            "support_messages",
            sa.Column("id", sa.Integer(), primary_key=True, autoincrement=True),
            sa.Column("ticket_id", sa.Integer(), sa.ForeignKey("support_tickets.id"), nullable=False),
            sa.Column("sender_type", support_sender_type, nullable=False),
            sa.Column("sender_user_id", sa.Integer(), sa.ForeignKey("users.id"), nullable=True),
            sa.Column("sender_admin_id", sa.Integer(), sa.ForeignKey("admin_users.id"), nullable=True),
            sa.Column("sender_name", sa.String(length=200), nullable=True),
            sa.Column("message_type", support_message_type, nullable=False, server_default="text"),
            sa.Column("content", sa.Text(), nullable=False),
            sa.Column("telegram_message_id", sa.Integer(), nullable=True),
            sa.Column("read_by_admin", sa.Boolean(), nullable=False, server_default=sa.false()),
            sa.Column("read_by_user", sa.Boolean(), nullable=False, server_default=sa.false()),
            sa.Column("created_at", sa.DateTime(timezone=True), nullable=False, server_default=sa.func.now()),
        )
        op.create_index("ix_support_messages_ticket_id", "support_messages", ["ticket_id"])
        op.create_index("ix_support_messages_created_at", "support_messages", ["created_at"])
        op.create_index(
            "ix_support_messages_ticket_created",
            "support_messages",
            ["ticket_id", "created_at"],
        )

    if not _has_table("team_members"):
        op.create_table(
            "team_members",
            sa.Column("id", sa.Integer(), primary_key=True, autoincrement=True),
            sa.Column("admin_id", sa.Integer(), sa.ForeignKey("admin_users.id"), nullable=True, unique=True),
            sa.Column("display_name", sa.String(length=200), nullable=False),
            sa.Column("avatar_color", sa.String(length=7), nullable=False, server_default="#2563EB"),
            sa.Column("role", sa.String(length=100), nullable=True),
            sa.Column("department", support_department, nullable=False, server_default="support"),
            sa.Column("is_available", sa.Boolean(), nullable=False, server_default=sa.true()),
            sa.Column("is_online", sa.Boolean(), nullable=False, server_default=sa.false()),
            sa.Column("last_seen", sa.DateTime(timezone=True), nullable=True),
            sa.Column("tickets_handled", sa.Integer(), nullable=False, server_default="0"),
            sa.Column("avg_response_time", sa.Integer(), nullable=False, server_default="0"),
        )


def downgrade() -> None:
    if _has_table("team_members"):
        op.drop_table("team_members")

    if _has_table("support_messages"):
        op.drop_table("support_messages")

    if _has_table("support_tickets"):
        op.drop_table("support_tickets")

    _drop_enums()