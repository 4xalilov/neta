"""Async SQLAlchemy engine, session factory va umumiy Base/mixin'lar.

Har bir model shu yerdagi ``Base`` dan meros oladi. ``TimestampMixin`` va
``UUIDPkMixin`` orqali ``id``, ``created_at``, ``updated_at`` ustunlari
avtomatik qo'shiladi (docs/02-data-model.md: "Hamma jadvalda id uuid,
created_at, updated_at").
"""

from __future__ import annotations

import uuid
from collections.abc import AsyncIterator
from datetime import datetime

from sqlalchemy import DateTime, func
from sqlalchemy.ext.asyncio import (
    AsyncEngine,
    AsyncSession,
    async_sessionmaker,
    create_async_engine,
)
from sqlalchemy.orm import DeclarativeBase, Mapped, mapped_column

from engine.settings import settings


class Base(DeclarativeBase):
    """Barcha modellar uchun umumiy asos."""


class UUIDPkMixin:
    """``id: uuid`` primary key, default ``uuid4()``."""

    id: Mapped[uuid.UUID] = mapped_column(primary_key=True, default=uuid.uuid4)


class TimestampMixin:
    """``created_at`` / ``updated_at`` — server tomonida boshqariladi."""

    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now(), nullable=False
    )
    updated_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True),
        server_default=func.now(),
        onupdate=func.now(),
        nullable=False,
    )


engine: AsyncEngine = create_async_engine(settings.database_url, echo=settings.sql_echo)

async_session = async_sessionmaker(engine, expire_on_commit=False, class_=AsyncSession)


async def get_session() -> AsyncIterator[AsyncSession]:
    """FastAPI dependency: har so'rov uchun bitta ``AsyncSession``."""
    async with async_session() as session:
        yield session


async def init_models(bind: AsyncEngine | None = None) -> None:
    """Testlar uchun: barcha jadvallarni yaratadi (``Base.metadata.create_all``).

    Ishlab chiqarishda jadvallar Alembic migratsiyalari orqali yaratiladi —
    bu funksiya faqat sqlite/in-memory testlar uchun.
    """
    import importlib

    importlib.import_module("engine.models")  # jadvallar metadata'ga ro'yxatdan o'tsin

    target = bind or engine
    dialect_name = target.dialect.name

    # Faqat postgresga xos indekslar (ivfflat va h.k.) sqlite kabi boshqa
    # dialektlarda create_all paytida xatolik beradi — vaqtincha olib tashlaymiz.
    removed: list[tuple] = []
    if dialect_name != "postgresql":
        for table in Base.metadata.tables.values():
            for index in list(table.indexes):
                if index.info.get("postgres_only"):
                    table.indexes.discard(index)
                    removed.append((table, index))

    try:
        async with target.begin() as conn:
            await conn.run_sync(Base.metadata.create_all)
    finally:
        for table, index in removed:
            table.indexes.add(index)
