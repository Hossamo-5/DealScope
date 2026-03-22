import sys
import asyncio
from sqlalchemy.ext.asyncio import create_async_engine, AsyncSession
from sqlalchemy.orm import sessionmaker
from sqlalchemy import text

sys.path.insert(0, '.')
from config.settings import DATABASE_URL

async def diagnose():
    if DATABASE_URL.startswith('sqlite:///'):
        url = DATABASE_URL.replace('sqlite:///', 'sqlite+aiosqlite:///')
    elif DATABASE_URL.startswith('postgresql://'):
        url = DATABASE_URL.replace('postgresql://', 'postgresql+asyncpg://')
    else:
        url = DATABASE_URL

    print(f'DATABASE_URL={DATABASE_URL}')
    print(f'ASYNC_URL={url}')

    engine = create_async_engine(url)
    Session = sessionmaker(engine, class_=AsyncSession, expire_on_commit=False)

    async with Session() as session:
        for sql, label in [
            ('SELECT COUNT(*) FROM support_tickets', 'support_tickets'),
            ('SELECT COUNT(*) FROM support_messages', 'support_messages'),
        ]:
            try:
                result = await session.execute(text(sql))
                print(f'{label}: {result.scalar()} rows')
            except Exception as e:
                print(f'ERROR {label}: {e}')

        try:
            if 'postgresql' in url:
                result = await session.execute(text("SELECT table_name FROM information_schema.tables WHERE table_schema = 'public' ORDER BY table_name"))
            else:
                result = await session.execute(text("SELECT name FROM sqlite_master WHERE type='table' ORDER BY name"))
            tables = [row[0] for row in result.all()]
            print('All DB tables:')
            for t in tables:
                print('  ' + t)
        except Exception as e:
            print(f'ERROR checking tables: {e}')

    await engine.dispose()

asyncio.run(diagnose())
