"""Add telegram groups table for dashboard group management.

Revision ID: 20260318_0007
Revises: 20260318_0006
Create Date: 2026-03-18 08:10:00
"""

from __future__ import annotations

from alembic import op
import sqlalchemy as sa


revision = "20260318_0007"
down_revision = "20260318_0006"
branch_labels = None
depends_on = None


purpose_enum = sa.Enum(
    "admin_alerts",
    "support_team",
    "deals",
    "announcements",
    "developers",
    "accounting",
    "custom",
    name="telegramgrouppurpose",
)


def _inspector():
    return sa.inspect(op.get_bind())


def _has_table(table_name: str) -> bool:
    return _inspector().has_table(table_name)


def upgrade() -> None:
    bind = op.get_bind()

    if bind.dialect.name == "postgresql":
        purpose_enum.create(bind, checkfirst=True)

    if _has_table("telegram_groups"):
        return

    op.create_table(
        "telegram_groups",
        sa.Column("id", sa.Integer(), primary_key=True, nullable=False),
        sa.Column("name", sa.String(length=200), nullable=False),
        sa.Column("chat_id", sa.BigInteger(), nullable=False),
        sa.Column("purpose", purpose_enum, nullable=False, server_default="custom"),
        sa.Column("description", sa.Text(), nullable=True),
        sa.Column("is_active", sa.Boolean(), nullable=False, server_default=sa.true()),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False, server_default=sa.func.now()),
        sa.UniqueConstraint("chat_id", name="uq_telegram_groups_chat_id"),
    )

    op.create_index("ix_telegram_groups_chat_id", "telegram_groups", ["chat_id"])
    op.create_index("ix_telegram_groups_purpose_active", "telegram_groups", ["purpose", "is_active"])


def downgrade() -> None:
    bind = op.get_bind()

    if _has_table("telegram_groups"):
        op.drop_table("telegram_groups")

    if bind.dialect.name == "postgresql":
        op.execute(sa.text("DROP TYPE IF EXISTS telegramgrouppurpose CASCADE"))
