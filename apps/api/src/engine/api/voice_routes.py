"""Ovozli boshqaruv HTTP marshruti (roadmap 5.10) — Telegram bot kontrakti (apps/api/README.md
"Ovozli boshqaruv").

- ``POST /v1/voice/command`` (multipart): ``audio`` fayl YOKI ``text``; ``chat_id``,
  ``workspace_id``, ``fmt`` ixtiyoriy → ``jarvis.voice.handle_owner_utterance``. Javob ovozi
  MinIO'ga (``ws/<ws>/audio/<uuid>.ogg``) yoziladi va ``audio_url`` qaytadi; storage ishlamasa
  ``audio_b64``. ``create_brief`` niyatida arq ``run_brief`` navbatga qo'yiladi → ``job_id``.
- ``GET /v1/voice/history?chat_id=&n=`` — ``owner_memory`` oxirgi qatorlari.
"""
from __future__ import annotations

import asyncio
import base64
import logging
import uuid
from typing import Annotated, Any

from fastapi import APIRouter, Depends, File, Form, HTTPException, Query, Request, UploadFile

from engine.api.jarvis_routes import get_deps
from engine.api.routes import _enqueue_brief, get_arq_pool
from engine.integrations import storage
from engine.jarvis import owner_memory
from engine.jarvis.deps import JarvisDeps
from engine.jarvis.voice import VoiceReply, handle_owner_utterance
from engine.models import Workspace
from engine.settings import settings

logger = logging.getLogger(__name__)

router = APIRouter(prefix="/v1/voice")

DepsDep = Annotated[JarvisDeps, Depends(get_deps)]
MAX_AUDIO_BYTES = 20 * 1024 * 1024  # Telegram bot API yuklab olish chegarasi (20 MB)
STORAGE_TIMEOUT_S = 10.0
AUDIO_CONTENT_TYPES = {"ogg": "audio/ogg", "mp3": "audio/mpeg", "wav": "audio/wav"}


async def _store_reply_audio(reply: VoiceReply) -> tuple[str | None, str | None]:
    """``(audio_url, audio_b64)`` — MinIO ishlasa URL, aks holda base64."""
    if not reply.reply_audio:
        return None, None
    fmt = reply.reply_audio_fmt or "ogg"
    try:
        key = storage.key_for(reply.workspace_id or "shared", "audio", fmt)
        uri = await asyncio.wait_for(
            storage.put_bytes(key, reply.reply_audio,
                              AUDIO_CONTENT_TYPES.get(fmt, "application/octet-stream")),
            STORAGE_TIMEOUT_S,
        )
        return storage.public_url(uri), None
    except Exception:
        logger.warning("voice_routes: javob ovozini MinIO'ga yozib bo'lmadi, base64 qaytadi",
                       exc_info=True)
        return None, base64.b64encode(reply.reply_audio).decode("ascii")


@router.post("/command")
async def voice_command(
    request: Request,
    deps: DepsDep,
    audio: Annotated[UploadFile | None, File()] = None,
    text: Annotated[str | None, Form()] = None,
    chat_id: Annotated[int | None, Form()] = None,
    workspace_id: Annotated[str | None, Form()] = None,
    fmt: Annotated[str | None, Form()] = None,
) -> dict[str, Any]:
    audio_bytes: bytes | None = None
    if audio is not None:
        audio_bytes = await audio.read()
        if len(audio_bytes) > MAX_AUDIO_BYTES:
            raise HTTPException(413, "audio juda katta (20 MB dan oshmasin)")
        if not fmt:  # "voice.oga" → "oga"; bo'lmasa content-type; baytlar baribir tekshiriladi
            name = audio.filename or ""
            fmt = name.rsplit(".", 1)[-1] if "." in name else audio.content_type
    if not audio_bytes and not (text or "").strip():
        raise HTTPException(422, "audio yoki text kerak")
    if workspace_id:
        try:
            uuid.UUID(workspace_id)
        except ValueError:
            raise HTTPException(404, "workspace topilmadi") from None

    reply = await handle_owner_utterance(
        deps,
        chat_id=chat_id or settings.owner_tg_id,
        workspace_id=workspace_id or None,
        text=text,
        audio=audio_bytes or None,
        audio_fmt=fmt,
    )

    job_id: str | None = None
    if reply.enqueue_brief and reply.workspace_id:
        async with deps.session_factory() as s:
            ws = await s.get(Workspace, uuid.UUID(reply.workspace_id))
        if ws is not None:  # arq pool faqat kerak bo'lganda (Redis'siz ham ovoz ishlasin)
            pool = await get_arq_pool(request)
            job_id = await _enqueue_brief(pool, ws, reply.enqueue_brief, None)

    audio_url, audio_b64 = await _store_reply_audio(reply)
    intent = reply.intent
    return {
        "transcript": reply.transcript,
        "intent": intent.intent,
        "confidence": intent.confidence,
        "entities": intent.entities.model_dump(exclude_none=True, exclude_defaults=True),
        "reply_text": reply.reply_text,
        "needs_confirmation": reply.needs_confirmation,
        "clarify": reply.clarify,
        "actions": reply.actions,
        "audio_url": audio_url,
        "audio_b64": audio_b64,
        "audio_fmt": reply.reply_audio_fmt if reply.reply_audio else None,
        "job_id": job_id,
        "workspace_id": reply.workspace_id,
        "stt_provider": reply.stt_provider,
        "cost_usd": reply.cost_usd,
    }


@router.get("/history")
async def voice_history(
    deps: DepsDep,
    chat_id: Annotated[int, Query()],
    n: Annotated[int, Query(ge=1, le=100)] = 20,
) -> list[dict[str, Any]]:
    async with deps.session_factory() as s:
        rows = await owner_memory.recent(s, chat_id, n)
    return [
        {
            "id": str(r.id),
            "role": r.role,
            "text": r.text,
            "intent": (r.intent_json or {}).get("intent"),
            "intent_json": r.intent_json,
            "workspace_id": str(r.workspace_id) if r.workspace_id else None,
            "created_at": r.created_at.isoformat() if r.created_at else None,
        }
        for r in rows
    ]
