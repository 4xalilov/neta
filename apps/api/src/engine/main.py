"""FastAPI ilova: ``/health`` + ``/v1`` (bot kontrakti, apps/api/README.md)."""
from __future__ import annotations

import asyncio
import logging
from collections.abc import AsyncIterator
from contextlib import asynccontextmanager

from fastapi import FastAPI

from engine import cost_sink
from engine.api.routes import router as v1_router
from engine.integrations import storage

logger = logging.getLogger(__name__)


@asynccontextmanager
async def lifespan(app: FastAPI) -> AsyncIterator[None]:
    try:  # MinIO hali ko'tarilmagan bo'lishi mumkin — API baribir ishga tushsin
        await asyncio.wait_for(storage.ensure_bucket(), timeout=10)
    except Exception as exc:  # noqa: BLE001
        logger.warning("ensure_bucket o'tkazib yuborildi: %s", exc)
    cost_sink.install()
    try:
        yield
    finally:
        cost_sink.uninstall()
        pool = getattr(app.state, "arq", None)
        if pool is not None:
            await pool.aclose()


app = FastAPI(title="AI Marketing & Content Engine", lifespan=lifespan)
app.include_router(v1_router)

try:  # Jarvis agenti alohida yozmoqda; mavjud bo'lsa ulanadi
    from engine.api.jarvis_routes import router as jarvis_router
except ImportError:
    jarvis_router = None
if jarvis_router is not None:
    app.include_router(jarvis_router)

from engine.api.vault_routes import router as vault_router

app.include_router(vault_router)


@app.get("/health")
async def health() -> dict:
    return {"status": "ok"}
