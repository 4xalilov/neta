"""Uslub darvozasi (docs/03-roadmap.md 2.8): sxema+kontrast → render CLI (katalog
kadri) → kuchli model VisionQA rubrikasi → ``GateResult``.

Render CLI: ``npm run theme:validate -- <theme.json> --still <out.png>``
(``apps/render``, boshqa agent yozmoqda) — kontrakt: stdout'ning oxirgi qatori
``{"ok": true, "still": "<path>"}`` yoki ``{"ok": false, "problems": [...]}``.
Har chaqiriq alohida vaqtinchalik papkada ishlaydi, 180s timeout bilan.
"""

from __future__ import annotations

import asyncio
import json
import logging
import tempfile
from dataclasses import dataclass, field
from pathlib import Path
from typing import Any, Protocol

from engine import llm
from engine.agents import prompt_loader
from engine.integrations import storage
from engine.settings import settings

from . import schema as style_schema

logger = logging.getLogger(__name__)

__all__ = [
    "CliRenderValidator",
    "FakeRenderValidator",
    "GateResult",
    "RenderValidator",
    "ValidatorOutcome",
    "evaluate",
]

RENDER_CLI_TIMEOUT_S = 180.0


@dataclass(slots=True)
class ValidatorOutcome:
    ok: bool
    problems: list[str] = field(default_factory=list)
    still: bytes | None = None


class RenderValidator(Protocol):
    async def validate(self, theme: dict[str, Any]) -> ValidatorOutcome: ...


class CliRenderValidator:
    """Haqiqiy ``npm run theme:validate`` CLI'ni ``settings.render_dir`` ichida ishga tushiradi."""

    async def validate(self, theme: dict[str, Any]) -> ValidatorOutcome:
        render_dir = Path(settings.render_dir)
        with tempfile.TemporaryDirectory() as td:
            theme_path = Path(td) / "theme.json"
            still_path = Path(td) / "still.png"
            theme_path.write_text(json.dumps(theme, ensure_ascii=False), encoding="utf-8")

            try:
                proc = await asyncio.create_subprocess_exec(
                    "npm", "run", "theme:validate", "--",
                    str(theme_path), "--still", str(still_path),
                    cwd=str(render_dir),
                    stdout=asyncio.subprocess.PIPE,
                    stderr=asyncio.subprocess.PIPE,
                )
            except (FileNotFoundError, NotADirectoryError, PermissionError) as exc:
                logger.warning("gate: render validator CLI topilmadi: %s", exc)
                return ValidatorOutcome(ok=False, problems=["render validator unavailable"])

            try:
                stdout, stderr = await asyncio.wait_for(
                    proc.communicate(), timeout=RENDER_CLI_TIMEOUT_S
                )
            except TimeoutError:
                proc.kill()
                await proc.wait()
                return ValidatorOutcome(ok=False, problems=["render validator timeout (180s)"])

            data = self._parse_output(stdout, stderr, proc.returncode)
            if data is None:
                return ValidatorOutcome(ok=False, problems=["render validator unavailable"])

            problems = [str(p) for p in (data.get("problems") or [])]
            still_bytes = still_path.read_bytes() if still_path.is_file() else None
            return ValidatorOutcome(ok=bool(data.get("ok")), problems=problems, still=still_bytes)

    @staticmethod
    def _parse_output(stdout: bytes, stderr: bytes, returncode: int | None) -> dict[str, Any] | None:
        text = stdout.decode("utf-8", "ignore").strip()
        for line in reversed(text.splitlines()):
            line = line.strip()
            if not line.startswith("{"):
                continue
            try:
                data = json.loads(line)
            except ValueError:
                continue
            if isinstance(data, dict):
                return data
        logger.warning(
            "gate: render validator chiqishini o'qib bo'lmadi (kod=%s): %s",
            returncode, stderr.decode("utf-8", "ignore")[:500],
        )
        return None


class FakeRenderValidator:
    """Testlar uchun: oldindan belgilangan natija qaytaradi, jarayon ishga tushirmaydi."""

    def __init__(self, *, ok: bool = True, problems: list[str] | None = None,
                still: bytes | None = b"\x89PNG\r\n\x1a\nfake-still") -> None:
        self.ok = ok
        self.problems = list(problems or [])
        self.still = still
        self.calls: list[dict[str, Any]] = []

    async def validate(self, theme: dict[str, Any]) -> ValidatorOutcome:
        self.calls.append(theme)
        return ValidatorOutcome(ok=self.ok, problems=list(self.problems), still=self.still)


@dataclass(slots=True)
class GateResult:
    ok: bool
    score: int | None
    problems: list[str]
    judge: dict[str, Any] | None
    still_uri: str | None


def _normalize_judge(data: dict[str, Any]) -> dict[str, Any]:
    try:
        score = round(float(data.get("score", 0)))
    except (TypeError, ValueError):
        score = 0
    score = max(0, min(10, score))
    return {
        "score": score,
        "breakdown": data.get("breakdown") if isinstance(data.get("breakdown"), dict) else {},
        "reasons": [str(r) for r in (data.get("reasons") or [])],
        "fixes": [str(f) for f in (data.get("fixes") or [])],
    }


async def evaluate(
    theme: dict[str, Any],
    *,
    workspace_id: str = "",
    existing_names: list[str] | None = None,
    validator: RenderValidator | None = None,
) -> GateResult:
    """To'liq darvoza quvuri (docs/03-roadmap.md 2.8): sxema/kontrast → render → VisionQA.

    Sxema xato bo'lsa render/judge bosqichlari o'tkazib yuboriladi (buzuq JSON'ni
    render qilishning ma'nosi yo'q). ``ok`` faqat qattiq muammolar yo'q VA
    ``judge.score >= settings.style_gate_min_score`` bo'lsa ``True``.
    """
    problems: list[str] = list(style_schema.validate_theme(theme))
    if problems:
        return GateResult(ok=False, score=None, problems=problems, judge=None, still_uri=None)

    problems.extend(style_schema.check_contrast(theme))

    render_validator = validator or CliRenderValidator()
    outcome = await render_validator.validate(theme)
    problems.extend(outcome.problems)

    judge: dict[str, Any] | None = None
    score: int | None = None
    still_uri: str | None = None

    if outcome.still:
        system = prompt_loader.render(
            "style_judge",
            theme_name=theme.get("name", ""),
            theme=theme,
            existing_names=existing_names or [],
        )
        user = "Katalog kadri (still frame) berildi. Rubrika bo'yicha baholang. Faqat JSON qaytaring."
        try:
            raw = await llm.complete_json(
                "final", system, user, node="style_judge",
                workspace_id=workspace_id, images=[outcome.still],
            )
            judge = _normalize_judge(raw)
            score = judge["score"]
        except llm.LLMError as exc:
            logger.warning("gate: VisionQA judge xatosi: %s", exc)
            problems.append(f"judge xatosi: {exc}")

        try:
            still_uri = await storage.put_bytes(
                storage.key_for(workspace_id or "global", "frame", "png"),
                outcome.still, "image/png",
            )
        except Exception as exc:  # noqa: BLE001 - best effort, gate natijasini buzmasin
            logger.warning("gate: kadr yuklanmadi (best effort): %s", exc)

    ok = not problems and score is not None and score >= settings.style_gate_min_score
    return GateResult(ok=ok, score=score, problems=problems, judge=judge, still_uri=still_uri)
