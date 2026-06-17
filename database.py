"""
Verilay — Database Setup
Reads DATABASE_URL from config (SQLite for local dev, Postgres in production).
"""

from sqlalchemy.ext.asyncio import AsyncSession, create_async_engine, async_sessionmaker
from sqlalchemy.orm import DeclarativeBase

from config import get_settings

settings = get_settings()

DATABASE_URL = settings.DATABASE_URL

# check_same_thread is a SQLite-only connect argument.
connect_args = {"check_same_thread": False} if DATABASE_URL.startswith("sqlite") else {}

engine = create_async_engine(
    DATABASE_URL,
    echo=False,
    connect_args=connect_args,
)

async_session = async_sessionmaker(
    engine,
    class_=AsyncSession,
    expire_on_commit=False,
)


class Base(DeclarativeBase):
    pass


async def get_db():
    async with async_session() as session:
        try:
            yield session
            await session.commit()
        except Exception:
            await session.rollback()
            raise
        finally:
            await session.close()


async def create_tables():
    # Import models so every table is registered on Base.metadata before create_all.
    import models  # noqa: F401

    async with engine.begin() as conn:
        await conn.run_sync(Base.metadata.create_all)
