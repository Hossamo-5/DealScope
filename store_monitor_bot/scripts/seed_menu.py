#!/usr/bin/env python3
"""
Seed script to populate default bot menu buttons.
Runs the migration which includes default seeding.

Usage:
    python scripts/seed_menu.py

This script is mainly for reference. The actual seeding happens during
Alembic migration (alembic upgrade head).
"""

import asyncio
import sys
from pathlib import Path

# Add parent directory to path
sys.path.insert(0, str(Path(__file__).parent.parent))

from config.settings import DATABASE_URL
from db.models import get_engine, get_session_factory, BotMenuButton, BotMenuButtonActionType


async def main():
    """Seed default menu buttons to database."""
    engine = get_engine(DATABASE_URL)
    SessionLocal = get_session_factory(engine)
    
    async with SessionLocal() as session:
        # Check if menu already seeded
        existing = (await session.execute(
            "SELECT COUNT(*) FROM bot_menu_buttons LIMIT 1"
        )).scalar()
        
        if existing > 0:
            print("ℹ️ Menu buttons already exist in database. Skipping seed.")
            return
        
        print("🌱 Seeding default bot menu buttons...")
        
        buttons_data = [
            # Row 0
            ("➕ إضافة منتج", "➕", "handler", "add_product", 0, 0, True, "all", "reply", 0),
            ("📦 منتجاتي", "📦", "handler", "my_products", 0, 1, True, "all", "reply", 1),
            
            # Row 1
            ("📂 مراقبة فئة", "📂", "handler", "monitor_category", 1, 0, True, "all", "reply", 2),
            ("🏪 مراقبة متجر", "🏪", "handler", "monitor_store", 1, 1, True, "all", "reply", 3),
            
            # Row 2
            ("🔥 أفضل العروض", "🔥", "handler", "best_deals", 2, 0, True, "all", "reply", 4),
            ("📊 التقارير", "📊", "handler", "reports", 2, 1, True, "all", "reply", 5),
            
            # Row 3
            ("💳 الاشتراك", "💳", "handler", "subscription", 3, 0, True, "all", "reply", 6),
            ("⚙️ الإعدادات", "⚙️", "handler", "settings", 3, 1, True, "all", "reply", 7),
            
            # Row 4
            ("❓ المساعدة", "❓", "handler", "help", 4, 0, True, "all", "reply", 8),
            ("🏬 طلب إضافة متجر", "🏬", "handler", "request_store", 4, 1, True, "all", "reply", 9),
            
            # Row 5
            ("🎧 الدعم الفني", "🎧", "support", None, 5, 0, True, "all", "reply", 10),
        ]
        
        for label, emoji, action_type, action_value, row, col, is_active, visible_for, button_type, position in buttons_data:
            btn = BotMenuButton(
                label=label,
                emoji=emoji,
                action_type=BotMenuButtonActionType(action_type),
                action_value=action_value,
                row=row,
                col=col,
                position=position,
                is_active=is_active,
                visible_for=visible_for,
                button_type=button_type,
                menu_level=0,
                parent_id=None,
            )
            session.add(btn)
        
        await session.commit()
        print(f"✅ Seeded {len(buttons_data)} menu buttons successfully!")
        print("\nDefault menu structure:")
        print("Row 0: ➕ إضافة | 📦 منتجاتي")
        print("Row 1: 📂 فئة | 🏪 متجر")
        print("Row 2: 🔥 عروض | 📊 تقارير")
        print("Row 3: 💳 اشتراك | ⚙️ إعدادات")
        print("Row 4: ❓ مساعدة | 🏬 طلب متجر")
        print("Row 5: 🎧 دعم")


if __name__ == "__main__":
    try:
        asyncio.run(main())
    except Exception as e:
        print(f"❌ Error: {e}", file=sys.stderr)
        sys.exit(1)
