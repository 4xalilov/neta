"""``style_theme`` jadvali bilan ishlash: CRUD, darvoza (gate) ishga tushirish,
qurilma ichidagi (builtin) temalarni import qilish, Remotion props uchun tema
JSON'ini olish va vault hujjat yozish (docs/03-roadmap.md 2.8).
"""

from __future__ import annotations

import json
import logging
import uuid
from datetime import UTC, datetime
from pathlib import Path
from typing import Any

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from engine.models.style import StyleTheme

from . import gate as gate_module
from .gate import RenderValidator

logger = logging.getLogger(__name__)

__all__ = [
    "approve",
    "get_theme",
    "import_builtin",
    "list_themes",
    "reject",
    "run_gate",
    "submit",
    "theme_for_props",
    "write_vault_doc",
]

# apps/render'ning JSON Schema'si (``meta.family``) 12 ta oilani biladi: bold,
# minimal, editorial, neon, luxury, warm, playful, uzbek, social, finance,
# fitness, beauty. Taklif qilingan tema odatda ``meta.family``ni o'zi beradi
# (``_infer_family`` shuni afzal ko'radi) — quyidagi taxmin faqat ``meta`` yo'q
# eski/qo'lda kiritilgan temalar uchun zaxira variant.
_FAMILY_HINTS: dict[str, tuple[str, str, str]] = {
    "bold": ("Plus Jakarta Sans", "zoomPunch", "karaoke"),
    "minimal": ("Manrope", "fade", "lineByLine"),
    "neon": ("Plus Jakarta Sans", "glitchCut", "bigWord"),
    "editorial": ("Playfair Display", "slice", "lineByLine"),
    "luxury": ("Playfair Display", "fade", "lineByLine"),
}


def _infer_family(theme: dict[str, Any]) -> str:
    """``theme.meta.family`` bo'lsa shuni qaytaradi (sxema kontrakti) — bo'lmasa
    shrift/o'tish/subtitr kombinatsiyasi bo'yicha taxmin qiladi."""
    meta_family = ((theme.get("meta") or {}).get("family") or "").strip()
    if meta_family:
        return meta_family

    display_font = ((theme.get("fonts") or {}).get("display") or {}).get("family", "")
    transition = theme.get("defaultTransition", "")
    caption = theme.get("captionPreset", "")
    best, best_score = "custom", 0
    for family, (font, trans, cap) in _FAMILY_HINTS.items():
        score = (display_font == font) + (transition == trans) + (caption == cap)
        if score > best_score:
            best, best_score = family, score
    return best


async def list_themes(session: AsyncSession, status: str | None = "approved") -> list[StyleTheme]:
    """Katalog ro'yxati; ``status=None`` — hamma holat (candidate/approved/rejected)."""
    stmt = select(StyleTheme).order_by(StyleTheme.name)
    if status:
        stmt = stmt.where(StyleTheme.status == status)
    return list((await session.scalars(stmt)).all())


async def get_theme(session: AsyncSession, name: str) -> StyleTheme | None:
    return await session.scalar(select(StyleTheme).where(StyleTheme.name == name))


async def submit(
    session: AsyncSession,
    theme: dict[str, Any],
    source: str,
    inspiration: str,
    *,
    workspace_id: uuid.UUID | str | None = None,
    family: str | None = None,
) -> StyleTheme:
    """Yangi ``candidate`` qator yaratadi (hali darvozadan o'tmagan)."""
    name = str(theme.get("name") or "").strip()
    if not name:
        raise ValueError("theme.name bo'sh bo'lishi mumkin emas")
    if await session.scalar(select(StyleTheme.id).where(StyleTheme.name == name)) is not None:
        raise ValueError(f"'{name}' nomli tema allaqachon mavjud")
    ws_id = uuid.UUID(str(workspace_id)) if workspace_id else None
    row = StyleTheme(
        workspace_id=ws_id,
        name=name,
        family=family or _infer_family(theme),
        status="candidate",
        source=source,
        theme_json=theme,
        inspiration=inspiration or None,
    )
    session.add(row)
    await session.commit()
    await session.refresh(row)
    return row


async def run_gate(
    session: AsyncSession, theme_id: uuid.UUID | str, validator: RenderValidator | None = None
) -> StyleTheme:
    """Darvozani ishga tushiradi va qatorni yangilaydi (``approved``/``rejected``)."""
    row = await session.get(StyleTheme, uuid.UUID(str(theme_id)))
    if row is None:
        raise ValueError(f"style_theme topilmadi: {theme_id}")

    existing = [
        n for n in (await session.scalars(select(StyleTheme.name))).all() if n != row.name
    ]
    result = await gate_module.evaluate(
        row.theme_json, workspace_id=str(row.workspace_id or ""),
        existing_names=existing, validator=validator,
    )

    row.judge_score = result.score
    row.judge_json = result.judge
    row.problems = result.problems
    if result.still_uri:
        row.still_uri = result.still_uri
    if result.ok:
        row.status = "approved"
        row.approved_by = "gate"
        row.approved_at = datetime.now(UTC)
    else:
        row.status = "rejected"

    await session.commit()
    await session.refresh(row)
    return row


async def approve(
    session: AsyncSession, theme_id: uuid.UUID | str, *,
    reason: str | None = None, approved_by: str = "owner",
) -> StyleTheme:
    """Ega tasdiqlaydi (darvoza natijasidan qat'i nazar — qo'lda o'tkazib yuborish)."""
    row = await session.get(StyleTheme, uuid.UUID(str(theme_id)))
    if row is None:
        raise ValueError(f"style_theme topilmadi: {theme_id}")
    row.status = "approved"
    row.approved_by = approved_by
    row.approved_at = datetime.now(UTC)
    if reason:
        row.judge_json = {**(row.judge_json or {}), "override_reason": reason}
    await session.commit()
    await session.refresh(row)
    return row


async def reject(
    session: AsyncSession, theme_id: uuid.UUID | str, *,
    reason: str | None = None, approved_by: str = "owner",
) -> StyleTheme:
    """Ega rad etadi — sabab ``problems`` ga qo'shiladi (keyingi taklif takrorlamasin)."""
    row = await session.get(StyleTheme, uuid.UUID(str(theme_id)))
    if row is None:
        raise ValueError(f"style_theme topilmadi: {theme_id}")
    row.status = "rejected"
    row.approved_by = approved_by
    row.approved_at = datetime.now(UTC)
    if reason:
        row.problems = [*(row.problems or []), f"ega rad etdi: {reason}"]
    await session.commit()
    await session.refresh(row)
    return row


def _builtin_themes_dir(render_dir: str | Path) -> Path:
    return Path(render_dir) / "src" / "motion" / "styles" / "themes"


async def import_builtin(session: AsyncSession, render_dir: str | Path) -> dict[str, int]:
    """``apps/render/src/motion/styles/themes/*.json`` — Remotion'ning o'ziga xos 7+ ta
    tayyor temasini ``approved``/``builtin`` sifatida katalogga qo'shadi (idempotent:
    qayta chaqirilsa mavjud qatorlarni yangilaydi, dublikat yaratmaydi)."""
    themes_dir = _builtin_themes_dir(render_dir)
    files = sorted(themes_dir.glob("*.json")) if themes_dir.is_dir() else []

    added = updated = skipped = 0
    for path in files:
        try:
            theme = json.loads(path.read_text(encoding="utf-8"))
        except (OSError, ValueError) as exc:
            logger.warning("registry: builtin tema o'qilmadi (%s): %s", path, exc)
            skipped += 1
            continue
        name = str(theme.get("name") or path.stem)
        family = _infer_family(theme)

        row = await session.scalar(select(StyleTheme).where(StyleTheme.name == name))
        if row is None:
            row = StyleTheme(
                name=name, family=family, status="approved", source="builtin",
                theme_json=theme, inspiration="apps/render motion kutubxonasi (builtin)",
                problems=[], approved_by="builtin", approved_at=datetime.now(UTC),
            )
            session.add(row)
            added += 1
        else:
            row.theme_json = theme
            row.family = family
            row.status = "approved"
            row.source = "builtin"
            row.problems = []
            updated += 1

    await session.commit()
    return {"found": len(files), "added": added, "updated": updated, "skipped": skipped}


async def theme_for_props(session: AsyncSession, name: str) -> dict[str, Any] | None:
    """``approved`` tema JSON'ini qaytaradi (Remotion ``theme`` prop override uchun) —
    ``asset_gen`` shu funksiyani ``script["style"]`` nomi bilan chaqiradi."""
    row = await session.scalar(
        select(StyleTheme).where(StyleTheme.name == name, StyleTheme.status == "approved")
    )
    return dict(row.theme_json) if row and row.theme_json else None


async def write_vault_doc(theme_row: StyleTheme, vault_dir: str | Path) -> Path:
    """``vault/styles/<name>.md`` yozadi (frontmatter + inson o'qiy oladigan xulosa) —
    shunda uslub bilim grafida (roadmap 3.7) ham ko'rinadi."""
    styles_dir = Path(vault_dir) / "styles"
    styles_dir.mkdir(parents=True, exist_ok=True)
    out_path = styles_dir / f"{theme_row.name}.md"

    theme = theme_row.theme_json or {}
    colors = theme.get("colors") or {}
    updated = theme_row.updated_at.isoformat()[:10] if theme_row.updated_at else ""

    frontmatter = (
        "---\n"
        "type: reference\n"
        f"tags: [style/{theme_row.family}]\n"
        f"updated: {updated}\n"
        "---\n"
    )
    lines = [
        f"# Uslub: {theme.get('label') or theme_row.name}",
        "",
        str(theme.get("description") or "").strip() or "(tavsif yo'q)",
        "",
        f"- Nomi: `{theme_row.name}` · Oila: `{theme_row.family}`",
        f"- Holat: **{theme_row.status}** (manba: {theme_row.source})",
        "- VisionQA ball: {} (kerak >= darvoza chegarasi)".format(
            theme_row.judge_score if theme_row.judge_score is not None else "—"
        ),
        f"- Fon: `{colors.get('bg', '—')}` · Aksent: `{colors.get('accent', '—')}`",
        f"- Ilhom: {theme_row.inspiration or '—'}",
    ]
    if theme_row.problems:
        lines.append("")
        lines.append("## Muammolar / rad sabablari")
        for p in theme_row.problems:
            lines.append(f"- {p}")

    out_path.write_text(frontmatter + "\n" + "\n".join(lines) + "\n", encoding="utf-8")
    return out_path
