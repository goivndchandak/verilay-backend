"""
Verilay — Database Setup
Works with SQLite (local/dev) and Postgres (production) automatically.

Render/Heroku hand out 'postgres://' or 'postgresql://' URLs, which make
SQLAlchemy pick the sync psycopg2 driver. This app is async, so we rewrite the
scheme to 'postgresql+asyncpg://' and strip libpq-only query params that asyncpg
rejects. asyncpg is already in requirements.txt — psycopg2 is never needed.
"""

import ssl as ssl_lib
from urllib.parse import urlsplit, urlunsplit, parse_qsl, urlencode

from sqlalchemy.ext.asyncio import AsyncSession, create_async_engine, async_sessionmaker
from sqlalchemy.orm import DeclarativeBase

from config import get_settings

settings = get_settings()


def _normalize_db_url(url: str) -> tuple[str, dict]:
    """Return (async-safe url, connect_args)."""
    connect_args: dict = {}

    # Force an async driver so psycopg2 is never imported.
    if url.startswith("postgres://"):
        url = "postgresql+asyncpg://" + url[len("postgres://"):]
    elif url.startswith("postgresql://"):
        url = "postgresql+asyncpg://" + url[len("postgresql://"):]

    if url.startswith("postgresql+asyncpg://"):
        # asyncpg doesn't understand libpq params like sslmode / channel_binding.
        parts = urlsplit(url)
        kept = [(k, v) for k, v in parse_qsl(parts.query)
                if k not in ("sslmode", "channel_binding")]
        url = urlunsplit((parts.scheme, parts.netloc, parts.path,
                          urlencode(kept), parts.fragment))
        # Render Postgres requires SSL. Use an encrypting context that doesn't
        # fail on hostname/CA mismatches (fine for a managed provider; can be
        # tightened later).
        ctx = ssl_lib.create_default_context()
        ctx.check_hostname = False
        ctx.verify_mode = ssl_lib.CERT_NONE
        connect_args["ssl"] = ctx

    elif url.startswith("sqlite"):
        connect_args["check_same_thread"] = False

    return url, connect_args


DATABASE_URL, connect_args = _normalize_db_url(settings.DATABASE_URL)

engine = create_async_engine(
    DATABASE_URL,
    echo=False,
    pool_pre_ping=True,
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
    # Import models so every table registers on Base.metadata before create_all.
    import models  # noqa: F401

    async with engine.begin() as conn:
        await conn.run_sync(Base.metadata.create_all)

    # ── Additive migrations (safe, idempotent) ──
    # create_all does NOT add new columns to existing tables, so on persistent
    # Postgres we add them explicitly. Each runs in its own transaction so one
    # failing (e.g. SQLite, which lacks IF NOT EXISTS) never blocks the others.
    migrations = [
        "ALTER TABLE mentions ADD COLUMN IF NOT EXISTS image_url VARCHAR(1000)",
        "ALTER TABLE truth_cards ADD COLUMN IF NOT EXISTS image_url VARCHAR(1000)",
        "ALTER TABLE users ADD COLUMN IF NOT EXISTS social_links JSON",
    ]
    for stmt in migrations:
        try:
            async with engine.begin() as conn:
                await conn.exec_driver_sql(stmt)
        except Exception as e:
            print(f"[migrate] skipped ({stmt[:45]}...): {e}")
