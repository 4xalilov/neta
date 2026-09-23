"""Vault API + jonli bilim grafi (docs/10-obsidian-vault.md, roadmap 3.6-3.7).

Endpointlar:
- ``GET /vault/graph`` — HTML sahifa (``engine/static/vault/graph.html``).
- ``GET /vault/static/{file}`` — shu sahifaning JS/CSS fayllari.
- ``GET /v1/vault/graph`` — graf snapshot JSON (``{"nodes": [...], "links": [...]}``).
- ``GET /v1/vault/notes/{path:path}`` — bitta faylning xom Markdown + metama'lumoti.
- ``POST /v1/vault/reindex`` — qo'lda qayta indekslash.
- ``GET /v1/vault/search`` — semantik qidiruv.
- ``WS /ws/vault`` — ``{"event": "snapshot", ...}`` bilan boshlanadi, keyin
  ``VaultBus`` orqali ``added``/``updated``/``removed`` hodisalarini oqim qiladi.
"""

from __future__ import annotations

from pathlib import Path
from typing import Annotated, Any

from fastapi import APIRouter, Depends, HTTPException, Query, WebSocket, WebSocketDisconnect
from fastapi.responses import HTMLResponse, JSONResponse, Response
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession, async_sessionmaker

from engine.db import async_session, get_session
from engine.models.vault import VAULT_NOTE_TYPES, VaultNote
from engine.settings import settings
from engine.vault import indexer
from engine.vault.events import vault_bus
from engine.vault.parser import parse

router = APIRouter()

_STATIC_DIR = Path(__file__).resolve().parent.parent / "static" / "vault"
_STATIC_CONTENT_TYPES = {
    ".js": "application/javascript; charset=utf-8",
    ".css": "text/css; charset=utf-8",
    ".html": "text/html; charset=utf-8",
}


def get_session_factory() -> async_sessionmaker[AsyncSession]:
    """Bulk operatsiyalar (reindex, WS snapshot) uchun sessiya fabrikasi.

    ``get_session`` (bitta so'rov = bitta sessiya) dan farqli, testlarda
    ``app.dependency_overrides[get_session_factory]`` orqali almashtiriladi.
    """
    return async_session


def _note_summary(note: VaultNote) -> dict[str, Any]:
    return {
        "id": str(note.id),
        "path": note.path,
        "title": note.title,
        "type": note.type,
        "tags": list(note.tags or []),
        "updated": note.updated_at.isoformat() if note.updated_at else None,
    }


@router.get("/vault/graph", response_class=HTMLResponse)
async def vault_graph_page() -> HTMLResponse:
    """Jonli bilim grafi sahifasi (roadmap 3.7)."""
    html_path = _STATIC_DIR / "graph.html"
    if not html_path.exists():
        raise HTTPException(status_code=404, detail="graph.html topilmadi")
    return HTMLResponse(html_path.read_text(encoding="utf-8"))


@router.get("/vault/static/{file_name}")
async def vault_static_file(file_name: str) -> Response:
    """``graph.html`` uchun JS/CSS — bitta darajali, ``..`` ga yo'l qo'yilmaydi."""
    if "/" in file_name or "\\" in file_name or file_name in {"..", "."}:
        raise HTTPException(status_code=404, detail="fayl topilmadi")
    candidate = (_STATIC_DIR / file_name).resolve()
    if _STATIC_DIR.resolve() not in candidate.parents or not candidate.is_file():
        raise HTTPException(status_code=404, detail="fayl topilmadi")
    content_type = _STATIC_CONTENT_TYPES.get(candidate.suffix.lower(), "application/octet-stream")
    return Response(candidate.read_bytes(), media_type=content_type)


@router.get("/v1/vault/graph")
async def vault_graph_json(
    session: Annotated[AsyncSession, Depends(get_session)],
) -> JSONResponse:
    """Graf snapshot: ``{"nodes": [...], "links": [...]}`` (docs/10)."""
    snapshot = await indexer.graph_snapshot(session)
    return JSONResponse(snapshot)


@router.get("/v1/vault/notes/{path:path}")
async def vault_note_detail(
    path: str,
    session: Annotated[AsyncSession, Depends(get_session)],
) -> dict[str, Any]:
    """Bitta faylning xom Markdown matni + metama'lumoti (client ``marked`` bilan render qiladi)."""
    note = (
        await session.execute(select(VaultNote).where(VaultNote.path == path))
    ).scalar_one_or_none()
    if note is None:
        raise HTTPException(status_code=404, detail="yozuv topilmadi")

    vault_root = Path(settings.vault_dir).resolve()
    file_path = (vault_root / path).resolve()
    if vault_root not in file_path.parents or not file_path.is_file():
        raise HTTPException(status_code=404, detail="fayl diskda topilmadi")

    text = file_path.read_text(encoding="utf-8")
    parsed = parse(text, fallback_title=Path(path).stem)

    return {
        "path": note.path,
        "title": parsed.title,
        "type": note.type,
        "tags": parsed.tags,
        "frontmatter": parsed.frontmatter,
        "links": list(note.links or []),
        "markdown": parsed.body,
    }


@router.post("/v1/vault/reindex")
async def vault_reindex(
    session_factory: Annotated[
        async_sessionmaker[AsyncSession], Depends(get_session_factory)
    ],
) -> dict[str, int]:
    """Qo'lda qayta indekslash (odatda ``engine.vault.cron.reindex_job`` har
    ``settings.vault_reindex_minutes`` daqiqada avtomatik chaqiradi)."""
    report = await indexer.reindex(session_factory, settings.vault_dir)
    return {
        "added": report.added,
        "updated": report.updated,
        "removed": report.removed,
        "unchanged": report.unchanged,
    }


@router.get("/v1/vault/search")
async def vault_search(
    session: Annotated[AsyncSession, Depends(get_session)],
    q: str = Query(default=""),
    note_type: str | None = Query(default=None, alias="type"),
    k: int = Query(default=5, ge=1, le=50),
) -> list[dict[str, Any]]:
    """Semantik qidiruv (``?q=narx&type=brand,sop&k=5``)."""
    types: list[str] | None = None
    if note_type:
        types = [t.strip() for t in note_type.split(",") if t.strip() in VAULT_NOTE_TYPES]
        types = types or None
    rows = await indexer.search(session, q, types=types, k=k)
    return [_note_summary(row) for row in rows]


@router.websocket("/ws/vault")
async def ws_vault(
    websocket: WebSocket,
    session_factory: Annotated[
        async_sessionmaker[AsyncSession], Depends(get_session_factory)
    ],
) -> None:
    """Ulanganda ``{"event": "snapshot", "nodes": [...], "links": [...]}``,
    keyin ``VaultBus`` orqali har indekslash hodisasi."""
    await websocket.accept()

    async with session_factory() as session:
        snapshot = await indexer.graph_snapshot(session)
    await websocket.send_json({"event": "snapshot", **snapshot})

    queue = vault_bus.subscribe()
    try:
        while True:
            payload = await queue.get()
            await websocket.send_json(payload)
    except WebSocketDisconnect:
        pass
    finally:
        vault_bus.unsubscribe(queue)


__all__ = ["get_session_factory", "router"]
