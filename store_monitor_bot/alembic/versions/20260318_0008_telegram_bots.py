"""Add telegram bots table for dashboard bot asset management.

Revision ID: 20260318_0008
Revises: 20260318_0007
Create Date: 2026-03-18 12:00:00
"""

from __future__ import annotations

from alembic import op
import sqlalchemy as sa


revision = "20260318_0008"
down_revision = "20260318_0007"
branch_labels = None
depends_on = None


def _inspector():
    return sa.inspect(op.get_bind())


def _has_table(table_name: str) -> bool:
    return _inspector().has_table(table_name)


def _has_index(table_name: str, index_name: str) -> bool:
    return index_name in {idx.get("name") for idx in _inspector().get_indexes(table_name)}


def upgrade() -> None:
    if _has_table("telegram_bots"):
        return

    op.create_table(
        "telegram_bots",
        sa.Column("id", sa.Integer(), primary_key=True, nullable=False),
        sa.Column("name", sa.String(length=200), nullable=False),
        sa.Column("username", sa.String(length=100), nullable=True),
        sa.Column("token", sa.String(length=255), nullable=True),
        sa.Column("purpose", sa.String(length=50), nullable=False, server_default="custom"),
        sa.Column("description", sa.Text(), nullable=True),
        sa.Column("is_active", sa.Boolean(), nullable=False, server_default=sa.true()),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False, server_default=sa.func.now()),
        sa.UniqueConstraint("username", name="uq_telegram_bots_username"),
    )

    op.create_index("ix_telegram_bots_username", "telegram_bots", ["username"])
    op.create_index("ix_telegram_bots_purpose_active", "telegram_bots", ["purpose", "is_active"])


def downgrade() -> None:
    if not _has_table("telegram_bots"):
        return

    if _has_index("telegram_bots", "ix_telegram_bots_purpose_active"):
        op.drop_index("ix_telegram_bots_purpose_active", table_name="telegram_bots")
    if _has_index("telegram_bots", "ix_telegram_bots_username"):
        op.drop_index("ix_telegram_bots_username", table_name="telegram_bots")

    op.drop_table("telegram_bots")
