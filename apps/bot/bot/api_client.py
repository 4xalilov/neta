"""Thin httpx wrapper over the FastAPI backend (`apps/api`).

Every method is tolerant of network/HTTP errors: it either returns the parsed
JSON payload (a plain ``dict``) or raises :class:`ApiError`, which handlers
catch to show a friendly Uzbek message instead of crashing. See
``apps/bot/README.md`` for the full `/v1/...` contract the API must expose.
"""
from __future__ import annotations

import logging
from typing import Any, Self

import httpx

from bot.settings import settings

log = logging.getLogger(__name__)


class ApiError(Exception):
    """Raised when the API call fails (network error or non-2xx response)."""


class ApiClient:
    def __init__(self, base_url: str | None = None, timeout: float = 15.0) -> None:
        self._base_url = base_url or settings.api_url
        self._timeout = timeout
        self._client: httpx.AsyncClient | None = None

    async def __aenter__(self) -> Self:
        self._client = httpx.AsyncClient(base_url=self._base_url, timeout=self._timeout)
        return self

    async def __aexit__(self, *exc: object) -> None:
        if self._client is not None:
            await self._client.aclose()
            self._client = None

    def _http(self) -> httpx.AsyncClient:
        if self._client is None:
            # Lazily create a client for callers that don't use `async with`.
            self._client = httpx.AsyncClient(base_url=self._base_url, timeout=self._timeout)
        return self._client

    async def aclose(self) -> None:
        if self._client is not None:
            await self._client.aclose()
            self._client = None

    async def _request(self, method: str, path: str, **kwargs: Any) -> Any:
        try:
            resp = await self._http().request(method, path, **kwargs)
            resp.raise_for_status()
        except httpx.HTTPStatusError as exc:
            log.warning("API %s %s -> HTTP %s", method, path, exc.response.status_code)
            raise ApiError(f"HTTP {exc.response.status_code} on {path}") from exc
        except httpx.HTTPError as exc:
            log.warning("API %s %s -> %s", method, path, exc)
            raise ApiError(str(exc)) from exc
        if not resp.content:
            return {}
        try:
            return resp.json()
        except ValueError as exc:
            raise ApiError("invalid JSON response") from exc

    # -- workspace ---------------------------------------------------
    async def create_workspace(self, owner_tg_id: int, name: str) -> dict:
        """POST /v1/workspaces {owner_tg_id, name} -> Workspace"""
        return await self._request(
            "POST", "/v1/workspaces", json={"owner_tg_id": owner_tg_id, "name": name}
        )

    async def get_workspace(self, owner_tg_id: int) -> dict | None:
        """GET /v1/workspaces?owner_tg_id=... -> Workspace | None (404)"""
        try:
            return await self._request(
                "GET", "/v1/workspaces", params={"owner_tg_id": owner_tg_id}
            )
        except ApiError as exc:
            if "404" in str(exc):
                return None
            raise

    # -- brief / job ---------------------------------------------------
    async def create_brief(self, workspace_id: str, text: str) -> str:
        """POST /v1/briefs {workspace_id, text} -> {job_id} ; returns job_id"""
        data = await self._request(
            "POST", "/v1/briefs", json={"workspace_id": workspace_id, "text": text}
        )
        return data["job_id"]

    async def get_job(self, job_id: str) -> dict:
        """GET /v1/jobs/{job_id} -> {status, stage, progress, result?, error?}"""
        return await self._request("GET", f"/v1/jobs/{job_id}")

    # -- script approval ---------------------------------------------------
    async def approve_script(self, script_id: str, hook_idx: int) -> dict:
        """POST /v1/scripts/{script_id}/approve {hook_idx} -> Script"""
        return await self._request(
            "POST", f"/v1/scripts/{script_id}/approve", json={"hook_idx": hook_idx}
        )

    async def reject(self, script_id: str, reason: str) -> dict:
        """POST /v1/scripts/{script_id}/reject {reason} -> {ok: true}"""
        return await self._request(
            "POST", f"/v1/scripts/{script_id}/reject", json={"reason": reason}
        )

    # -- video approval ---------------------------------------------------
    async def approve_video(self, script_id: str, action: str) -> dict:
        """POST /v1/scripts/{script_id}/video-approve {action: publish|schedule} -> {ok: true}"""
        return await self._request(
            "POST", f"/v1/scripts/{script_id}/video-approve", json={"action": action}
        )

    # -- jarvis ---------------------------------------------------
    async def daily_report(self, workspace_id: str) -> dict:
        """GET /v1/workspaces/{workspace_id}/daily-report -> Report"""
        return await self._request("GET", f"/v1/workspaces/{workspace_id}/daily-report")

    async def jarvis_decision(self, action_id: str, decision: str) -> dict:
        """POST /v1/jarvis-actions/{action_id}/decision {decision: yes|no|edit} -> {ok: true}"""
        return await self._request(
            "POST", f"/v1/jarvis-actions/{action_id}/decision", json={"decision": decision}
        )

    # -- settings ---------------------------------------------------
    async def update_brand_profile(self, workspace_id: str, **fields: Any) -> dict:
        """PATCH /v1/workspaces/{workspace_id}/brand-profile {...fields} -> BrandProfile"""
        return await self._request(
            "PATCH", f"/v1/workspaces/{workspace_id}/brand-profile", json=fields
        )

    # -- voice (roadmap 5.10) ---------------------------------------------------
    async def voice_command(
        self,
        chat_id: int,
        *,
        audio: bytes | None = None,
        text: str | None = None,
        workspace_id: str | None = None,
        role: str = "owner",
        fmt: str = "ogg",
    ) -> dict:
        """POST /v1/voice/command, multipart form.

        Exactly one of `audio` (raw ogg/opus bytes from Telegram) or `text`
        (typed command, or an owner's "✏️ Tuzatish" correction) is sent, plus
        `chat_id`, optional `workspace_id`, `fmt` ("ogg") and `role`
        ("owner"|"staff" -- staff voice/text goes through the same endpoint,
        distinguished only by this field). Returns a `VoiceResult`:
        `{transcript, intent, confidence, reply_text, needs_confirmation,
        actions: [{id, type, level, status, summary}], audio_url, audio_b64,
        job_id}`.
        """
        if audio is None and text is None:
            raise ValueError("voice_command requires audio or text")
        data: dict[str, str] = {"chat_id": str(chat_id), "fmt": fmt, "role": role}
        if workspace_id is not None:
            data["workspace_id"] = workspace_id
        if text is not None:
            data["text"] = text
        files = {"audio": ("voice.ogg", audio, "audio/ogg")} if audio is not None else None
        return await self._request("POST", "/v1/voice/command", data=data, files=files)

    async def voice_history(self, chat_id: int, n: int = 10) -> list[dict]:
        """GET /v1/voice/history?chat_id=&n= -> [{role: "user"|"jarvis", text, created_at}]"""
        result = await self._request("GET", "/v1/voice/history", params={"chat_id": chat_id, "n": n})
        return result if isinstance(result, list) else []

    # -- tasks (kind="task" tg:notify, roadmap 5.10) ---------------------------------------------------
    async def task_status(self, task_id: str, status: str) -> dict:
        """POST /v1/tasks/{task_id}/status {status: "done"|"delayed"} -> {ok: true}

        NOT YET IMPLEMENTED on the API side -- required so the ✅ Bajarildi /
        ⏳ Kechikadi buttons on the `kind="task"` notify screen (see
        `apps/bot/README.md`) can report a staff member's answer back.
        """
        return await self._request(
            "POST", f"/v1/tasks/{task_id}/status", json={"status": status}
        )
