"""Add telegram_id to admin_users.

Revision ID: 20260317_0002
Revises: 20260317_0001
Create Date: 2026-03-17 23:20:00
"""

from alembic import op
import sqlalchemy as sa


revision = "20260317_0002"
down_revision = "20260317_0001"
branch_labels = None
depends_on = None


def _has_table(table_name: str) -> bool:
    inspector = sa.inspect(op.get_bind())
    return inspector.has_table(table_name)


def _has_column(table_name: str, column_name: str) -> bool:
    inspector = sa.inspect(op.get_bind())
    cols = inspector.get_columns(table_name)
    return any(c.get("name") == column_name for c in cols)


def _has_index(table_name: str, index_name: str) -> bool:
    inspector = sa.inspect(op.get_bind())
    indexes = inspector.get_indexes(table_name)
    return any(i.get("name") == index_name for i in indexes)


def upgrade() -> None:
    if not _has_table("admin_users"):
        return

    if not _has_column("admin_users", "telegram_id"):
        op.add_column("admin_users", sa.Column("telegram_id", sa.BigInteger(), nullable=True))

    if not _has_index("admin_users", "ix_admin_users_telegram_id"):
        op.create_index("ix_admin_users_telegram_id", "admin_users", ["telegram_id"], unique=True)


def downgrade() -> None:
    if not _has_table("admin_users"):
        return

    if _has_index("admin_users", "ix_admin_users_telegram_id"):
        op.drop_index("ix_admin_users_telegram_id", table_name="admin_users")

    if _has_column("admin_users", "telegram_id"):
        op.drop_column("admin_users", "telegram_id")
