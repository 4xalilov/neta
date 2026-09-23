"""Uslub bilimlar bazasi API (docs/03-roadmap.md 2.8).

Endpointlar:
- ``GET /v1/styles?status=`` — katalog ro'yxati (standart: faqat ``approved``).
- ``GET /v1/styles/{name}`` — bitta tema (to'liq JSON + darvoza natijasi bilan).
- ``POST /v1/styles/propose`` — LLM (yoki URL ilhom) orqali yangi taklif:
  darhol ``candidate`` qator yaratadi, darvozani fonda ishga tushiradi.
- ``POST /v1/styles/{id}/gate`` — darvozani qo'lda qayta ishga tushiradi.
- ``POST /v1/styles/{id}/approve`` / ``/reject`` — ega tomonidan qo'lda
  tasdiqlash/rad etish (darvoza natijasidan qat'i nazar).
- ``POST /v1/styles/import-builtin`` — ``apps/render`` ning tayyor temalarini
  katalogga qo'shadi (idempotent).
- ``GET /v1/styles/{name}/still`` — katalog kadriga (``still_uri``) yo'naltiradi.
"""

from __future__ import annotations

import logging
import uuid
from typing import Annotated, Any

from fastapi import APIRouter, BackgroundTasks, Depends, HTTPException, Query
from fastapi.responses import RedirectResponse
from pydantic import BaseModel
from sqlalchemy.ext.asyncio import AsyncSession, async_sessionmaker

from engine.db import async_session, get_session
from engine.integrations import storage
from engine.models.style import StyleTheme
from engine.settings import settings
from engine.styles import proposer, registry

logger = logging.getLogger(__name__)

router = APIRouter(prefix="/v1/styles", tags=["styles"])

SessionDep = Annotated[AsyncSession, Depends(get_session)]


def get_session_factory() -> async_sessionmaker[AsyncSession]:
    """Fon vazifasi (``propose`` dan keyingi darvoza) uchun sessiya fabrikasi.

    ``get_session`` (bitta so'rov = bitta sessiya) dan farqli — so'rov javob
    qaytargach ham ishlaydi. Testlarda ``app.dependency_overrides[get_session_factory]``
    orqali almashtiriladi (``engine/api/vault_routes.py`` bilan bir xil pattern).
    """
    return async_session


class ProposeBody(BaseModel):
    inspiration: str = ""
    niche: str = ""
    mood: str = ""
    base: str | None = None
    url: str | None = None


class DecisionBody(BaseModel):
    reason: str | None = None


def _summary(row: StyleTheme) -> dict[str, Any]:
    return {
        "id": str(row.id),
        "name": row.name,
        "family": row.family,
        "status": row.status,
        "source": row.source,
        "judge_score": row.judge_score,
        "still_url": storage.public_url(row.still_uri) if row.still_uri else None,
        "updated_at": row.updated_at.isoformat() if row.updated_at else None,
    }


def _detail(row: StyleTheme) -> dict[str, Any]:
    return {
        **_summary(row),
        "workspace_id": str(row.workspace_id) if row.workspace_id else None,
        "theme_json": row.theme_json,
        "inspiration": row.inspiration,
        "judge_json": row.judge_json,
        "problems": list(row.problems or []),
        "approved_by": row.approved_by,
        "approved_at": row.approved_at.isoformat() if row.approved_at else None,
        "created_at": row.created_at.isoformat() if row.created_at else None,
    }


def _not_found(what: str) -> HTTPException:
    return HTTPException(status_code=404, detail=f"{what} topilmadi")


@router.get("")
async def list_styles(
    session: SessionDep,
    status: Annotated[str | None, Query()] = "approved",
) -> list[dict[str, Any]]:
    """``status=""``/``all`` — hamma holat; standart faqat ``approved`` (Writer shundan tanlaydi)."""
    effective_status = None if not status or status == "all" else status
    rows = await registry.list_themes(session, status=effective_status)
    return [_summary(r) for r in rows]


@router.get("/{name}")
async def get_style(name: str, session: SessionDep) -> dict[str, Any]:
    row = await registry.get_theme(session, name)
    if row is None:
        raise _not_found("uslub")
    return _detail(row)


async def _run_gate_in_background(
    session_factory: async_sessionmaker[AsyncSession], theme_id: uuid.UUID,
) -> None:
    """``propose`` javob qaytargandan keyin ishlaydi — o'z sessiyasi bilan (so'rov
    sessiyasi javobdan keyin yopiladi)."""
    async with session_factory() as bg_session:
        try:
            row = await registry.run_gate(bg_session, theme_id)
            if row.status == "approved":
                await registry.write_vault_doc(row, settings.vault_dir)
        except Exception:  # fon vazifasi — xato so'rovni buzmasin, faqat logga yoziladi
            logger.exception("style_routes: %s uchun fon darvozasi ishlamadi", theme_id)


@router.post("/propose", status_code=202)
async def propose_style(
    body: ProposeBody,
    background_tasks: BackgroundTasks,
    session: SessionDep,
    session_factory: Annotated[
        async_sessionmaker[AsyncSession], Depends(get_session_factory)
    ],
) -> dict[str, Any]:
    inspiration = body.inspiration.strip()
    if body.url:
        fetched = await proposer.propose_from_url(body.url)
        inspiration = f"{inspiration}\n\n{fetched}".strip() if inspiration else fetched
    if not inspiration:
        raise HTTPException(status_code=422, detail="'inspiration' yoki 'url' talab qilinadi")

    theme = await proposer.propose(inspiration, niche=body.niche, mood=body.mood, base=body.base)
    try:
        row = await registry.submit(session, theme, source="llm", inspiration=inspiration)
    except ValueError as exc:
        raise HTTPException(status_code=409, detail=str(exc)) from exc

    background_tasks.add_task(_run_gate_in_background, session_factory, row.id)
    return {"id": str(row.id), "name": row.name, "status": row.status}


@router.post("/{style_id}/gate")
async def gate_style(style_id: uuid.UUID, session: SessionDep) -> dict[str, Any]:
    """Darvozani sinxron (bloklovchi) qayta ishga tushiradi — natija darhol qaytadi."""
    try:
        row = await registry.run_gate(session, style_id)
    except ValueError as exc:
        raise HTTPException(status_code=404, detail=str(exc)) from exc
    if row.status == "approved":
        await registry.write_vault_doc(row, settings.vault_dir)
    return _detail(row)


@router.post("/{style_id}/approve")
async def approve_style(
    style_id: uuid.UUID, body: DecisionBody, session: SessionDep,
) -> dict[str, Any]:
    try:
        row = await registry.approve(session, style_id, reason=body.reason)
    except ValueError as exc:
        raise HTTPException(status_code=404, detail=str(exc)) from exc
    await registry.write_vault_doc(row, settings.vault_dir)
    return _detail(row)


@router.post("/{style_id}/reject")
async def reject_style(
    style_id: uuid.UUID, body: DecisionBody, session: SessionDep,
) -> dict[str, Any]:
    try:
        row = await registry.reject(session, style_id, reason=body.reason)
    except ValueError as exc:
        raise HTTPException(status_code=404, detail=str(exc)) from exc
    return _detail(row)


@router.post("/import-builtin")
async def import_builtin_styles(session: SessionDep) -> dict[str, int]:
    return await registry.import_builtin(session, settings.render_dir)


@router.get("/{name}/still")
async def style_still(name: str, session: SessionDep) -> RedirectResponse:
    row = await registry.get_theme(session, name)
    if row is None or not row.still_uri:
        raise _not_found("kadr")
    return RedirectResponse(storage.public_url(row.still_uri))


__all__ = ["get_session_factory", "router"]
