"""Alembic muhit sozlamasi — async, engine.settings.database_url'dan o'qiydi.

Migratsiyalardan oldin ``CREATE EXTENSION IF NOT EXISTS vector`` ishga
tushiriladi (pgvector embedding ustunlari uchun kerak).
"""

import asyncio
from logging.config import fileConfig

from sqlalchemy import pool, text
from sqlalchemy.ext.asyncio import async_engine_from_config

# `alembic.ini` dagi `prepend_sys_path = . src` orqali `engine` paketi topiladi.
import engine.models  # noqa: F401  (Base.metadata ni to'liq to'ldirish uchun)
from alembic import context
from engine.db import Base
from engine.settings import settings

config = context.config

if config.config_file_name is not None:
    fileConfig(config.config_file_name)

target_metadata = Base.metadata

# alembic.ini'dagi sqlalchemy.url bo'sh — settings.database_url ishlatiladi.
config.set_main_option("sqlalchemy.url", settings.database_url)


def run_migrations_offline() -> None:
    url = settings.database_url
    context.configure(
        url=url,
        target_metadata=target_metadata,
        literal_binds=True,
        dialect_opts={"paramstyle": "named"},
    )
    with context.begin_transaction():
        context.run_migrations()


def _do_run_migrations(connection) -> None:
    context.configure(connection=connection, target_metadata=target_metadata)
    with context.begin_transaction():
        context.run_migrations()


async def run_migrations_online() -> None:
    connectable = async_engine_from_config(
        config.get_section(config.config_ini_section, {}),
        prefix="sqlalchemy.",
        poolclass=pool.NullPool,
    )

    async with connectable.connect() as connection:
        await connection.execute(text("CREATE EXTENSION IF NOT EXISTS vector"))
        await connection.run_sync(_do_run_migrations)

    await connectable.dispose()


if context.is_offline_mode():
    run_migrations_offline()
else:
    asyncio.run(run_migrations_online())
