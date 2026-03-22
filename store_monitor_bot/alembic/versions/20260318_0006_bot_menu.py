"""Add bot menu buttons table with dynamic menu structure.

Revision ID: 20260318_0006
Revises: 20260318_0004
Create Date: 2026-03-18 06:00:00
"""

from __future__ import annotations

from alembic import op
import sqlalchemy as sa


# revision identifiers, used by Alembic.
revision = "20260318_0006"
down_revision = "20260318_0004"
branch_labels = None
depends_on = None


# Define enums
action_type_enum = sa.Enum(
    "menu",
    "message",
    "url",
    "command",
    "handler",
    "support",
    "subscribe",
    name="botmenubuttonactiontype",
)

button_type_enum = sa.Enum(
    "reply",
    "inline",
    name="botmenubuttontype",
)

visibility_enum = sa.Enum(
    "all",
    "free",
    "basic",
    "professional",
    "admin",
    name="botmenuvisibility",
)


def _inspector():
    return sa.inspect(op.get_bind())


def _has_table(table_name: str) -> bool:
    return _inspector().has_table(table_name)


def _seed_default_menu() -> None:
    """Seeds the default main menu buttons."""
    default_buttons = [
        # Row 0
        ("➕ إضافة منتج", "➕", "handler", "add_product", 0, 0, True, "all", "reply", 0, None, 0),
        ("📦 منتجاتي", "📦", "handler", "my_products", 0, 1, True, "all", "reply", 1, None, 0),
        
        # Row 1
        ("📂 مراقبة فئة", "📂", "handler", "monitor_category", 1, 0, True, "all", "reply", 2, None, 0),
        ("🏪 مراقبة متجر", "🏪", "handler", "monitor_store", 1, 1, True, "all", "reply", 3, None, 0),
        
        # Row 2
        ("🔥 أفضل العروض", "🔥", "handler", "best_deals", 2, 0, True, "all", "reply", 4, None, 0),
        ("📊 التقارير", "📊", "handler", "reports", 2, 1, True, "all", "reply", 5, None, 0),
        
        # Row 3
        ("💳 الاشتراك", "💳", "handler", "subscription", 3, 0, True, "all", "reply", 6, None, 0),
        ("⚙️ الإعدادات", "⚙️", "handler", "settings", 3, 1, True, "all", "reply", 7, None, 0),
        
        # Row 4
        ("❓ المساعدة", "❓", "handler", "help", 4, 0, True, "all", "reply", 8, None, 0),
        ("🏬 طلب إضافة متجر", "🏬", "handler", "request_store", 4, 1, True, "all", "reply", 9, None, 0),
        
        # Row 5
        ("🎧 الدعم الفني", "🎧", "support", None, 5, 0, True, "all", "reply", 10, None, 0),
    ]
    
    insert_stmt = sa.text("""
        INSERT INTO bot_menu_buttons
        (label, emoji, action_type, action_value, row, col, is_active, visible_for, button_type, position, parent_id, menu_level)
        VALUES
        (:label, :emoji, :action_type, :action_value, :row, :col, :is_active, :visible_for, :button_type, :position, :parent_id, :menu_level)
        ON CONFLICT DO NOTHING
    """)
    
    for btn in default_buttons:
        op.execute(
            insert_stmt.bindparams(
                label=btn[0],
                emoji=btn[1],
                action_type=btn[2],
                action_value=btn[3],
                row=btn[4],
                col=btn[5],
                is_active=btn[6],
                visible_for=btn[7],
                button_type=btn[8],
                position=btn[9],
                parent_id=btn[10],
                menu_level=btn[11],
            )
        )


def upgrade() -> None:
    bind = op.get_bind()
    
    # Create enums (PostgreSQL)
    if bind.dialect.name == "postgresql":
        action_type_enum.create(bind, checkfirst=True)
        button_type_enum.create(bind, checkfirst=True)
        visibility_enum.create(bind, checkfirst=True)
    
    # Skip if table already exists
    if _has_table("bot_menu_buttons"):
        return
    
    # Create the bot_menu_buttons table
    op.create_table(
        "bot_menu_buttons",
        sa.Column("id", sa.Integer(), nullable=False),
        sa.Column("label", sa.String(100), nullable=False),
        sa.Column("emoji", sa.String(10), nullable=True),
        sa.Column("action_type", action_type_enum, nullable=False, server_default="message"),
        sa.Column("action_value", sa.Text(), nullable=True),
        sa.Column("position", sa.Integer(), nullable=False, server_default="0"),
        sa.Column("row", sa.Integer(), nullable=False, server_default="0"),
        sa.Column("col", sa.Integer(), nullable=False, server_default="0"),
        sa.Column("is_active", sa.Boolean(), nullable=False, server_default=sa.true()),
        sa.Column("visible_for", visibility_enum, nullable=False, server_default="all"),
        sa.Column("parent_id", sa.Integer(), nullable=True),
        sa.Column("menu_level", sa.Integer(), nullable=False, server_default="0"),
        sa.Column("button_type", button_type_enum, nullable=False, server_default="reply"),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False, server_default=sa.func.now()),
        sa.Column("updated_at", sa.DateTime(timezone=True), nullable=False, server_default=sa.func.now()),
        sa.PrimaryKeyConstraint("id"),
        sa.ForeignKeyConstraint(["parent_id"], ["bot_menu_buttons.id"], ),
    )
    
    # Create indexes
    op.create_index(
        "ix_bot_menu_active_row_col",
        "bot_menu_buttons",
        ["is_active", "row", "col"],
    )
    op.create_index(
        "ix_bot_menu_parent",
        "bot_menu_buttons",
        ["parent_id", "is_active"],
    )
    op.create_index(
        "ix_bot_menu_buttons_created_at",
        "bot_menu_buttons",
        ["created_at"],
    )
    
    # Seed default menu
    _seed_default_menu()


def downgrade() -> None:
    bind = op.get_bind()
    
    # Drop the table
    op.drop_table("bot_menu_buttons", if_exists=True)
    
    # Drop enums (PostgreSQL)
    if bind.dialect.name == "postgresql":
        op.execute(sa.text("DROP TYPE IF EXISTS botmenubuttonactiontype CASCADE"))
        op.execute(sa.text("DROP TYPE IF EXISTS botmenubuttontype CASCADE"))
        op.execute(sa.text("DROP TYPE IF EXISTS botmenuvisibility CASCADE"))
