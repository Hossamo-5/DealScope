"""Add user onboarding flag and bot settings table.

Revision ID: 20260318_0004
Revises: 20260317_0003
Create Date: 2026-03-18 05:30:00
"""

from __future__ import annotations

from alembic import op
import sqlalchemy as sa


# revision identifiers, used by Alembic.
revision = "20260318_0004"
down_revision = "20260317_0003"
branch_labels = None
depends_on = None


setting_value_type = sa.Enum(
    "string",
    "integer",
    "float",
    "boolean",
    "json",
    name="settingvaluetype",
)


def _inspector():
    return sa.inspect(op.get_bind())


def _has_table(table_name: str) -> bool:
    return _inspector().has_table(table_name)


def _has_column(table_name: str, column_name: str) -> bool:
    return any(col.get("name") == column_name for col in _inspector().get_columns(table_name))


def _seed_defaults() -> None:
    defaults = {
        "bot.bot_name": ("DealScope", "string", "bot", "اسم البوت"),
        "bot.welcome_message": ("👋 أهلاً بك في بوت مراقبة الأسعار والعروض!", "string", "bot", "رسالة الترحيب"),
        "bot.maintenance_mode": ("false", "boolean", "bot", "تشغيل وضع الصيانة"),
        "bot.maintenance_message": ("🔧 البوت قيد الصيانة حالياً، نعود قريباً.", "string", "bot", "رسالة الصيانة"),
        "bot.test_mode": ("false", "boolean", "bot", "وضع الاختبار"),
        "monitoring.min_discount_percent": ("10", "integer", "monitoring", "الحد الأدنى للخصم"),
        "monitoring.scraping_delay": ("2", "integer", "monitoring", "التأخير بين الطلبات"),
        "monitoring.max_requests_per_minute": ("10", "integer", "monitoring", "أقصى طلبات في الدقيقة"),
        "monitoring.max_products_per_cycle": ("50", "integer", "monitoring", "أقصى منتجات في كل دورة"),
        "monitoring.retry_attempts": ("3", "integer", "monitoring", "محاولات إعادة المحاولة"),
        "plans.free.max_products": ("3", "integer", "plans", "حد منتجات الخطة المجانية"),
        "plans.free.scan_interval": ("60", "integer", "plans", "تردد الفحص للخطة المجانية"),
        "plans.basic.price": ("10", "integer", "plans", "سعر الخطة الأساسية"),
        "plans.basic.max_products": ("50", "integer", "plans", "حد منتجات الخطة الأساسية"),
        "plans.basic.scan_interval": ("30", "integer", "plans", "تردد الفحص للخطة الأساسية"),
        "plans.professional.price": ("49", "integer", "plans", "سعر الخطة الاحترافية"),
        "plans.professional.max_products": ("300", "integer", "plans", "حد منتجات الخطة الاحترافية"),
        "plans.professional.scan_interval": ("15", "integer", "plans", "تردد الفحص للخطة الاحترافية"),
        "templates.price_drop": ("📉 انخفاض في السعر!\n{product_name}\nالسعر: {old_price} ← {new_price}\nخصم: {discount}%", "string", "templates", "قالب انخفاض السعر"),
        "templates.deal_approved": ("🔥 عرض قوي!\n{product_name}\nخصم {discount}% 🎯", "string", "templates", "قالب العروض"),
        "templates.back_in_stock": ("🟢 عاد المنتج للمخزون: {product_name}", "string", "templates", "قالب عودة المخزون"),
        "affiliate.default_tag": ("", "string", "affiliate", "وسم الأفلييت الافتراضي"),
        "affiliate.auto_tag": ("false", "boolean", "affiliate", "تفعيل إضافة الوسم تلقائياً"),
        "security.max_login_attempts": ("5", "integer", "security", "عدد محاولات تسجيل الدخول"),
        "security.lockout_minutes": ("15", "integer", "security", "مدة القفل بالدقائق"),
        "security.jwt_expire_hours": ("8", "integer", "security", "مدة JWT بالساعات"),
    }

    for key, (value, value_type, category, description) in defaults.items():
        op.execute(
            sa.text(
                """
                INSERT INTO bot_settings (key, value, value_type, category, description)
                VALUES (:key, :value, :value_type, :category, :description)
                ON CONFLICT (key) DO NOTHING
                """
            ).bindparams(
                key=key,
                value=value,
                value_type=value_type,
                category=category,
                description=description,
            )
        )


def upgrade() -> None:
    bind = op.get_bind()
    if bind.dialect.name == "postgresql":
        setting_value_type.create(bind, checkfirst=True)

    if _has_table("users") and not _has_column("users", "is_onboarded"):
        with op.batch_alter_table("users") as batch_op:
            batch_op.add_column(sa.Column("is_onboarded", sa.Boolean(), nullable=False, server_default=sa.false()))

    if not _has_table("bot_settings"):
        op.create_table(
            "bot_settings",
            sa.Column("key", sa.String(length=100), primary_key=True),
            sa.Column("value", sa.Text(), nullable=False),
            sa.Column("value_type", setting_value_type, nullable=False, server_default="string"),
            sa.Column("category", sa.String(length=50), nullable=False),
            sa.Column("description", sa.Text(), nullable=True),
            sa.Column("updated_at", sa.DateTime(timezone=True), nullable=True, server_default=sa.func.now()),
            sa.Column("updated_by", sa.Integer(), sa.ForeignKey("admin_users.id"), nullable=True),
        )
        op.create_index("ix_bot_settings_category", "bot_settings", ["category"])

    _seed_defaults()


def downgrade() -> None:
    if _has_table("bot_settings"):
        op.drop_table("bot_settings")

    if _has_table("users") and _has_column("users", "is_onboarded"):
        with op.batch_alter_table("users") as batch_op:
            batch_op.drop_column("is_onboarded")

    bind = op.get_bind()
    if bind.dialect.name == "postgresql":
        setting_value_type.drop(bind, checkfirst=True)
