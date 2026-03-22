import argparse
import asyncio

from sqlalchemy import select

from config.settings import DATABASE_URL
from db.models import AdminUser, create_tables, get_engine, get_session_factory


def hash_password(password: str) -> str:
    bcrypt = __import__("bcrypt")
    return bcrypt.hashpw(password.encode("utf-8"), bcrypt.gensalt()).decode("utf-8")


async def main(args):
    engine = get_engine(DATABASE_URL)
    await create_tables(engine)
    Session = get_session_factory(engine)

    async with Session() as session:
        query = select(AdminUser).where(
            (AdminUser.email == args.email)
            | (AdminUser.phone == args.phone)
            | (AdminUser.telegram_id == args.telegram_id)
        )
        existing = (await session.execute(query)).scalar_one_or_none()

        if existing:
            existing.name = args.name
            existing.email = args.email
            existing.phone = args.phone
            existing.telegram_id = args.telegram_id
            existing.password_hash = hash_password(args.password)
            existing.is_active = True
            existing.failed_attempts = 0
            existing.locked_until = None
            action = "updated"
        else:
            session.add(
                AdminUser(
                    name=args.name,
                    email=args.email,
                    phone=args.phone,
                    telegram_id=args.telegram_id,
                    password_hash=hash_password(args.password),
                    is_active=True,
                    failed_attempts=0,
                )
            )
            action = "created"

        await session.commit()

    await engine.dispose()
    print(f"Admin {action} successfully")


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description="Create or update dashboard admin user")
    parser.add_argument("--email", required=True)
    parser.add_argument("--phone", required=True)
    parser.add_argument("--telegram-id", required=True, type=int)
    parser.add_argument("--password", required=True)
    parser.add_argument("--name", required=True)
    asyncio.run(main(parser.parse_args()))
