"""Alembic: database migrations for the tables in models/.

The URL comes from .env, never alembic.ini: DATABASE_URL_DIRECT (Neon's direct, non-pooler host;
recommended for migrations) or else DATABASE_URL. Run from fastapi-app/:
    uv run alembic upgrade head                                  # apply
    uv run alembic revision --autogenerate -m "what changed"     # after editing models/, then review it
"""
import asyncio
import os
from logging.config import fileConfig

from alembic import context
from dotenv import load_dotenv
from sqlalchemy.engine import Connection
from sqlmodel import SQLModel

import models  # noqa: F401  (registers every table on SQLModel.metadata)
from db import make_engine

load_dotenv()
config = context.config
if config.config_file_name is not None:
    fileConfig(config.config_file_name)

target_metadata = SQLModel.metadata


def _database_url() -> str:
    url = os.getenv("DATABASE_URL_DIRECT") or os.getenv("DATABASE_URL")
    if not url:
        raise SystemExit("Set DATABASE_URL (or DATABASE_URL_DIRECT) in fastapi-app/.env first")
    return url


def run_migrations_offline() -> None:
    """`alembic upgrade head --sql`: print the SQL instead of running it."""
    context.configure(url=_database_url(), target_metadata=target_metadata, literal_binds=True,
                      dialect_opts={"paramstyle": "named"}, compare_type=True)
    with context.begin_transaction():
        context.run_migrations()


def do_run_migrations(connection: Connection) -> None:
    context.configure(connection=connection, target_metadata=target_metadata, compare_type=True)
    with context.begin_transaction():
        context.run_migrations()


async def run_async_migrations() -> None:
    engine = make_engine(_database_url(), null_pool=True)
    async with engine.connect() as connection:
        await connection.run_sync(do_run_migrations)
    await engine.dispose()


if context.is_offline_mode():
    run_migrations_offline()
else:
    asyncio.run(run_async_migrations())
