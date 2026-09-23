"""SQLAlchemy modellari uchun testlar — Postgres'siz ishlaydi (sqlite+aiosqlite).

docs/02-data-model.md dagi barcha jadvallar mavjudligini, ularni sqlite'da
yaratib bo'lishini va asosiy CRUD ishlashini tekshiradi.
"""

from __future__ import annotations

import importlib.util
import uuid
from pathlib import Path

import pytest
from sqlalchemy import select
from sqlalchemy.ext.asyncio import async_sessionmaker, create_async_engine

from engine.db import Base, init_models
from engine.models import BrandProfile, CostLog, Script, Workspace

# docs/02-data-model.md "Content Engine" + "CRM + Jarvis" bo'limlaridagi
# hamma jadval nomlari, shuningdek roadmap 0.3 qo'shimchalari (render_job, crm_link).
EXPECTED_TABLES = {
    # Content Engine
    "workspace",
    "brand_profile",
    "ig_audit",
    "reference_video",
    "taste_memory",
    "content_plan",
    "script",
    "critic_review",
    "asset",
    "post",
    "post_metrics",
    "cost_log",
    "render_job",
    # CRM + Jarvis
    "campaign",
    "lead",
    "contact_event",
    "deal",
    "staff",
    "task",
    "call_log",
    "jarvis_action",
    "daily_report",
    "crm_link",
}


def test_all_tables_registered():
    assert EXPECTED_TABLES <= set(Base.metadata.tables.keys())


@pytest.mark.asyncio
async def test_create_all_on_sqlite_and_roundtrip():
    sqlite_engine = create_async_engine("sqlite+aiosqlite:///:memory:")
    try:
        await init_models(bind=sqlite_engine)

        session_factory = async_sessionmaker(sqlite_engine, expire_on_commit=False)
        async with session_factory() as session:
            ws = Workspace(name="Test Brand", timezone="Asia/Tashkent")
            session.add(ws)
            await session.flush()

            bp = BrandProfile(workspace_id=ws.id, data={"tone": "do'stona"})
            session.add(bp)

            script = Script(
                workspace_id=ws.id,
                plan_id=uuid.uuid4(),
                day=1,
                body="Salom!",
                status="draft",
            )
            session.add(script)

            cost = CostLog(
                workspace_id=ws.id,
                node="writer",
                provider="gemini",
                tokens_in=100,
                tokens_out=50,
                usd=0.01,
            )
            session.add(cost)

            await session.commit()

        async with session_factory() as session:
            got_ws = (await session.execute(select(Workspace))).scalar_one()
            assert got_ws.name == "Test Brand"

            got_bp = (await session.execute(select(BrandProfile))).scalar_one()
            assert got_bp.data == {"tone": "do'stona"}
            assert got_bp.workspace_id == got_ws.id

            got_script = (await session.execute(select(Script))).scalar_one()
            assert got_script.body == "Salom!"

            got_cost = (await session.execute(select(CostLog))).scalar_one()
            assert got_cost.usd == 0.01
    finally:
        await sqlite_engine.dispose()


def _load_migration_module():
    path = Path(__file__).resolve().parents[1] / "alembic" / "versions" / "0001_initial.py"
    spec = importlib.util.spec_from_file_location("migration_0001_initial", path)
    assert spec and spec.loader
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


def test_migration_0001_shape():
    module = _load_migration_module()
    assert module.revision == "0001"
    assert module.down_revision is None
    assert callable(module.upgrade)
    assert callable(module.downgrade)
