"""Phase 5: Database tables audit"""
import asyncio, sys
sys.path.insert(0, '.')

async def check_db():
    from config.settings import DATABASE_URL
    from sqlalchemy.ext.asyncio import create_async_engine
    from sqlalchemy import text

    url = DATABASE_URL
    if 'sqlite' in url and '+aiosqlite' not in url:
        url = url.replace('sqlite://', 'sqlite+aiosqlite://')
    elif 'postgresql' in url and '+asyncpg' not in url:
        url = url.replace('postgresql://', 'postgresql+asyncpg://')

    engine = create_async_engine(url)
    try:
        async with engine.connect() as conn:
            try:
                result = await conn.execute(text(
                    "SELECT table_name FROM information_schema.tables WHERE table_schema='public' ORDER BY table_name"
                ))
                tables = [r[0] for r in result.all()]
            except Exception:
                result = await conn.execute(text(
                    "SELECT name FROM sqlite_master WHERE type='table' ORDER BY name"
                ))
                tables = [r[0] for r in result.all()]
    finally:
        await engine.dispose()

    required = [
        'users', 'products', 'user_products',
        'opportunities', 'price_history', 'stock_history',
        'store_requests', 'stores',
        'support_tickets', 'support_messages', 'team_members',
        'admin_notifications', 'user_activities', 'user_stats',
        'admin_users', 'audit_logs', 'bot_settings',
        'bot_menu_buttons',
    ]

    print('='*60)
    print('DATABASE TABLES AUDIT')
    print('='*60)
    print(f'Tables found: {len(tables)}')
    for t in tables:
        print(f'  FOUND: {t}')

    print('\nRequired tables check:')
    missing = []
    for t in required:
        if t in tables:
            print(f'OK:      {t}')
        else:
            print(f'MISSING: {t}')
            missing.append(t)

    print(f'\nMissing tables: {len(missing)}')
    for t in missing:
        print(f'  MISSING: {t}')

asyncio.run(check_db())
