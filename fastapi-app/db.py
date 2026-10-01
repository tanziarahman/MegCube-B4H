"""Database connection (PostgreSQL on Neon). Optional: without DATABASE_URL the portal still works,
but alarms are off and /api/alarms answers 503.

DATABASE_URL is the connection string Neon shows, e.g.
  postgresql://user:password@ep-xxx-pooler.ap-southeast-1.aws.neon.tech/neondb?sslmode=require
The app uses the pooled host (-pooler); Alembic migrations use DATABASE_URL_DIRECT when set.
"""
import os
import uuid
from collections.abc import AsyncIterator

from dotenv import load_dotenv
from fastapi import HTTPException
from sqlalchemy.engine import URL, make_url
from sqlalchemy.ext.asyncio import AsyncEngine, async_sessionmaker, create_async_engine
from sqlalchemy.pool import NullPool
from sqlmodel.ext.asyncio.session import AsyncSession

load_dotenv()
DATABASE_URL = os.getenv("DATABASE_URL", "")


def asyncpg_url(raw: str) -> tuple[URL, dict]:
    """Turn a Neon/libpq connection string into an asyncpg URL plus connect_args.

    asyncpg refuses libpq-only options such as ?sslmode=require and ?channel_binding=..., so they are
    taken out of the URL and SSL is passed as a connect argument instead.
    """
    url = make_url(raw)
    if url.drivername in ("postgres", "postgresql", "postgresql+psycopg2", "postgresql+psycopg"):
        url = url.set(drivername="postgresql+asyncpg")
    query = dict(url.query)
    sslmode = query.pop("sslmode", None)
    query.pop("channel_binding", None)
    connect_args: dict = {}
    if sslmode and sslmode not in ("disable", "allow", "prefer"):
        connect_args["ssl"] = "require"
    if url.host and "-pooler" in url.host:
        # Neon's pooler (PgBouncer, transaction mode) can hand each statement a different server
        # connection, so asyncpg must not cache prepared statements by a reused name.
        connect_args["statement_cache_size"] = 0
        connect_args["prepared_statement_name_func"] = lambda: f"__asyncpg_{uuid.uuid4()}__"
    return url.set(query=query), connect_args


def make_engine(raw_url: str, *, null_pool: bool = False) -> AsyncEngine:
    url, connect_args = asyncpg_url(raw_url)
    if null_pool:
        # One connection per session, closed after: safe across event loops (tests, scripts).
        return create_async_engine(url, connect_args=connect_args, poolclass=NullPool)
    # pool_pre_ping: Neon closes idle connections when the database scales to zero.
    return create_async_engine(url, connect_args=connect_args, pool_size=5, max_overflow=5,
                               pool_pre_ping=True, pool_recycle=300)


_engine: AsyncEngine | None = None
_sessions: async_sessionmaker[AsyncSession] | None = None


def enabled() -> bool:
    return bool(DATABASE_URL) or _sessions is not None


def configure(engine: AsyncEngine) -> None:
    """Use this engine for every session (called lazily from DATABASE_URL, or by tests)."""
    global _engine, _sessions
    _engine = engine
    _sessions = async_sessionmaker(engine, class_=AsyncSession, expire_on_commit=False)


def sessions() -> async_sessionmaker[AsyncSession]:
    if _sessions is None:
        if not DATABASE_URL:
            raise HTTPException(503, "The database isn't configured: set DATABASE_URL in fastapi-app/.env")
        configure(make_engine(DATABASE_URL))
    return _sessions


async def get_session() -> AsyncIterator[AsyncSession]:
    """FastAPI dependency: one session per request."""
    async with sessions()() as session:
        yield session


async def dispose() -> None:
    if _engine is not None:
        await _engine.dispose()
