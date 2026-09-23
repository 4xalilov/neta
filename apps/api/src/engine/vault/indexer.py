"""Vault indekslovchi (docs/10-obsidian-vault.md, roadmap 3.6-3.7).

``scan`` — diskdagi ``.md`` fayllarni topadi, ``reindex`` — ular bilan
``vault_note`` jadvalini sinxronlaydi (hash bo'yicha o'zgarish aniqlanadi,
har o'zgarishda hodisa chiqadi), ``search`` — embedding bo'yicha qidiradi,
``graph_snapshot`` — jonli graf uchun tugun/qirralar, ``load_for_prompt`` —
Writer/Jarvis promptlariga brend/SOP matnini yig'adi, ``write_report`` —
Jarvis kunlik hisobotini ``reports/`` ga yozadi.
"""

from __future__ import annotations

import hashlib
import logging
from collections.abc import Awaitable, Callable
from dataclasses import dataclass
from datetime import UTC, datetime
from pathlib import Path
from typing import Any

from sqlalchemy import delete, select
from sqlalchemy.ext.asyncio import AsyncSession

from engine.models.vault import VaultNote
from engine.vault import embeddings
from engine.vault.events import vault_bus
from engine.vault.parser import ParsedNote, chunk, parse

logger = logging.getLogger(__name__)

__all__ = [
    "IndexReport",
    "NoteFile",
    "graph_snapshot",
    "load_for_prompt",
    "reindex",
    "scan",
    "search",
    "write_report",
]

OnEvent = Callable[[dict[str, Any]], "Awaitable[None] | None"]

# `templates/` — Obsidian shablonlari (docs/10), haqiqiy yozuv emas — indekslanmaydi.
_SKIP_DIRS = {"templates"}
# Vault ildizidagi qoida fayli (docs/10) — tur/frontmatter'ga ega emas, graf tuguni emas.
_SKIP_ROOT_FILES = {"README.md"}


@dataclass(slots=True)
class NoteFile:
    """Diskdan o'qilgan bitta ``.md`` fayl (hali bazaga yozilmagan)."""

    path: str  # `vault_dir` ga nisbatan, posix ko'rinishida, masalan "brand/faq.md"
    abs_path: Path
    mtime: datetime
    text: str
    content_hash: str


@dataclass
class IndexReport:
    added: int = 0
    updated: int = 0
    removed: int = 0
    unchanged: int = 0


def scan(vault_dir: str | Path) -> list[NoteFile]:
    """``vault_dir`` ichidagi hamma ``.md`` faylni o'qib qaytaradi (yo'l bo'yicha tartiblangan)."""
    root = Path(vault_dir)
    if not root.exists():
        return []
    notes: list[NoteFile] = []
    for path in sorted(root.rglob("*.md")):
        rel = path.relative_to(root)
        if rel.parts and rel.parts[0] in _SKIP_DIRS:
            continue
        if len(rel.parts) == 1 and rel.parts[0] in _SKIP_ROOT_FILES:
            continue
        try:
            text = path.read_text(encoding="utf-8")
        except OSError:  # pragma: no cover - o'qib bo'lmaydigan fayl
            logger.warning("vault: %s o'qib bo'lmadi", path)
            continue
        content_hash = hashlib.sha256(text.encode("utf-8")).hexdigest()
        try:
            mtime = datetime.fromtimestamp(path.stat().st_mtime, tz=UTC)
        except OSError:  # pragma: no cover
            mtime = datetime.now(tz=UTC)
        notes.append(
            NoteFile(
                path=rel.as_posix(),
                abs_path=path,
                mtime=mtime,
                text=text,
                content_hash=content_hash,
            )
        )
    return notes


def _default_type(path: str) -> str:
    """Frontmatterda ``type`` bo'lmasa, papka joylashuviga qarab taxmin."""
    parts = Path(path).parts
    if parts[:1] == ("reports",):
        return "report"
    if parts[:1] == ("brand",):
        return "brand"
    if parts[:2] == ("jarvis", "sop"):
        return "sop"
    if parts[:2] == ("jarvis", "staff"):
        return "staff"
    if parts[:2] == ("content", "references"):
        return "reference"
    if parts[:1] == ("content",):
        return "plan"
    return "reference"


def _resolve_links(
    raw_links: list[str], stem_to_path: dict[str, str], own_path: str
) -> list[str]:
    """``[[wikilink]]`` larni bilingan fayl nomlari bo'yicha to'liq yo'lga aylantiradi.

    Mos fayl topilmasa, xom matn saqlanadi (docs/10: "resolved to paths when possible").
    """
    resolved: list[str] = []
    for raw in raw_links:
        key = Path(raw.strip()).stem.strip().lower()
        target = stem_to_path.get(key, raw.strip())
        if target and target != own_path and target not in resolved:
            resolved.append(target)
    return resolved


def _note_embedding_text(parsed: ParsedNote) -> str:
    """Embeddinglanadigan matn: teglar + tana. Sarlavha tanada H1 sifatida allaqachon
    bo'lsa, uni qayta qo'shmaymiz — aks holda sarlavha so'zlari ikki marta hisoblanib,
    qidiruv natijalarini buzadi (masalan sarlavhasida so'rov so'zi bor qisqa fayllar
    sun'iy ravishda ustunlik qiladi)."""
    body = parsed.body
    first_line = body.lstrip().splitlines()[0].lstrip("#").strip() if body.strip() else ""
    title_in_body = bool(parsed.title) and first_line == parsed.title
    prefix = "" if title_in_body else parsed.title
    return f"{prefix}\n{' '.join(parsed.tags)}\n{body}".strip()


async def _embed_note(parsed: ParsedNote) -> list[float] | None:
    text = _note_embedding_text(parsed)
    pieces = chunk(text, max_chars=1200)
    if not pieces:
        return None
    vectors = await embeddings.embed(pieces)
    vectors = [v for v in vectors if v]
    if not vectors:
        return None
    dim = len(vectors[0])
    acc = [0.0] * dim
    for vec in vectors:
        for i, x in enumerate(vec):
            acc[i] += x
    mean = [x / len(vectors) for x in acc]
    norm = sum(x * x for x in mean) ** 0.5
    if norm > 0:
        mean = [x / norm for x in mean]
    return mean


def _node_payload(note: VaultNote) -> dict[str, Any]:
    return {
        "id": str(note.id),
        "path": note.path,
        "title": note.title,
        "type": note.type,
        "tags": list(note.tags or []),
        "updated": note.updated_at.isoformat() if note.updated_at else None,
    }


async def _emit(on_event: OnEvent | None, payload: dict[str, Any]) -> None:
    vault_bus.publish(payload)
    if on_event is None:
        return
    result = on_event(payload)
    if hasattr(result, "__await__"):
        await result  # type: ignore[misc]


async def reindex(
    session_factory: Callable[[], AsyncSession],
    vault_dir: str | Path,
    *,
    force: bool = False,
    on_event: OnEvent | None = None,
) -> IndexReport:
    """``vault_dir`` ni skanerlaydi va ``vault_note`` jadvalini sinxronlaydi.

    ``content_hash`` o'zgarmagan fayllar o'tkazib yuboriladi (``force=True`` bo'lmasa).
    Har qo'shilgan/yangilangan/o'chirilgan qator uchun ``on_event`` (va ``VaultBus``)
    orqali ``{"event": "added"|"updated"|"removed", "node": {...}, "links": [...]}`` chiqadi.
    """
    report = IndexReport()
    files = scan(vault_dir)
    stem_to_path = {Path(f.path).stem.lower(): f.path for f in files}

    async with session_factory() as session:
        existing_rows = (await session.execute(select(VaultNote))).scalars().all()
        existing_by_path = {row.path: row for row in existing_rows}
        seen_paths: set[str] = set()

        for f in files:
            seen_paths.add(f.path)
            row = existing_by_path.get(f.path)
            if row is not None and not force and row.content_hash == f.content_hash:
                report.unchanged += 1
                continue

            parsed = parse(f.text, fallback_title=Path(f.path).stem)
            links = _resolve_links(parsed.wikilinks, stem_to_path, f.path)
            embedding = await _embed_note(parsed)
            note_type = str(parsed.frontmatter.get("type") or _default_type(f.path))

            is_new = row is None
            if row is None:
                row = VaultNote(path=f.path)
                session.add(row)

            row.type = note_type
            row.title = parsed.title
            row.tags = parsed.tags
            row.links = links
            row.frontmatter = parsed.frontmatter
            row.body_excerpt = parsed.body[:500]
            row.content_hash = f.content_hash
            row.mtime = f.mtime
            row.embedding = embedding

            await session.flush()
            if not is_new:
                # ``updated_at`` DB tomonda ``onupdate`` bilan yangilanadi — UPDATE'dan
                # keyin obyekt eskirgan (expired) holatda, xodisaga to'g'ri vaqt chiqishi
                # uchun aniq refresh qilamiz (aks holda keyingi o'qish greenlet xatosi beradi).
                await session.refresh(row, attribute_names=["updated_at"])

            if is_new:
                report.added += 1
                event_name = "added"
            else:
                report.updated += 1
                event_name = "updated"

            await _emit(
                on_event, {"event": event_name, "node": _node_payload(row), "links": links}
            )

        removed_paths = sorted(set(existing_by_path) - seen_paths)
        for path in removed_paths:
            row = existing_by_path[path]
            payload = {
                "event": "removed",
                "node": _node_payload(row),
                "links": list(row.links or []),
            }
            await session.execute(delete(VaultNote).where(VaultNote.id == row.id))
            report.removed += 1
            await _emit(on_event, payload)

        await session.commit()

    return report


async def search(
    session: AsyncSession,
    query: str,
    *,
    types: list[str] | None = None,
    k: int = 5,
) -> list[VaultNote]:
    """Embedding bo'yicha eng yaqin ``k`` ta yozuvni qaytaradi.

    Postgres'da pgvector ``<=>`` (cosine distance) bazada hisoblanadi; sqlite kabi
    boshqa dialektlarda kosinus Python tomonda hisoblanadi (testlar shu yo'l bilan).
    """
    stmt = select(VaultNote)
    if types:
        stmt = stmt.where(VaultNote.type.in_(types))

    query_vecs = await embeddings.embed([query]) if query and query.strip() else []
    query_vec = query_vecs[0] if query_vecs else None

    bind = session.get_bind()
    dialect_name = getattr(getattr(bind, "dialect", None), "name", "sqlite")

    if dialect_name == "postgresql" and query_vec is not None:
        pg_stmt = stmt.where(VaultNote.embedding.is_not(None))
        pg_stmt = pg_stmt.order_by(VaultNote.embedding.cosine_distance(query_vec)).limit(k)
        result = await session.execute(pg_stmt)
        return list(result.scalars().all())

    result = await session.execute(stmt)
    rows = list(result.scalars().all())
    if query_vec is None:
        return rows[:k]

    scored = [(embeddings.cosine(query_vec, row.embedding or []), row) for row in rows]
    scored.sort(key=lambda pair: pair[0], reverse=True)
    return [row for _, row in scored[:k]]


async def graph_snapshot(session: AsyncSession) -> dict[str, Any]:
    """Jonli graf uchun to'liq holat: ``{"nodes": [...], "links": [...]}``."""
    rows = (await session.execute(select(VaultNote))).scalars().all()
    by_path = {row.path: row for row in rows}

    nodes = [
        {
            "id": str(row.id),
            "path": row.path,
            "title": row.title,
            "type": row.type,
            "tags": list(row.tags or []),
            "updated": row.updated_at.isoformat() if row.updated_at else None,
        }
        for row in rows
    ]
    links: list[dict[str, str]] = []
    for row in rows:
        for target_path in row.links or []:
            if target_path in by_path:
                links.append({"source": row.path, "target": target_path})
    return {"nodes": nodes, "links": links}


async def load_for_prompt(
    session: AsyncSession,
    types: tuple[str, ...] = ("brand", "sop"),
    max_chars: int = 6000,
) -> str:
    """Writer/Jarvis promptlariga qo'shish uchun brend/SOP matnini yig'adi.

    Har yozuv ``## <sarlavha> (<yo'l>)`` sarlavhasi bilan; jami uzunlik
    ``max_chars`` dan oshmaydi (oxirgi yozuv kesilishi mumkin).
    """
    stmt = select(VaultNote).where(VaultNote.type.in_(types)).order_by(VaultNote.path)
    rows = (await session.execute(stmt)).scalars().all()

    parts: list[str] = []
    total = 0
    for row in rows:
        section = f"## {row.title} ({row.path})\n{row.body_excerpt or ''}".strip()
        if total >= max_chars:
            break
        remaining = max_chars - total
        if len(section) > remaining:
            section = section[:remaining]
        parts.append(section)
        total += len(section) + 2  # "\n\n" ajratuvchi hisobga olinadi
    return "\n\n".join(parts)[:max_chars]


def write_report(vault_dir: str | Path, date: Any, text: str) -> Path:
    """Jarvis kunlik hisobotini ``reports/YYYY-MM-DD.md`` ga frontmatter bilan yozadi."""
    if hasattr(date, "isoformat"):
        date_str = date.isoformat()[:10]
    else:
        date_str = str(date)[:10]

    reports_dir = Path(vault_dir) / "reports"
    reports_dir.mkdir(parents=True, exist_ok=True)
    out_path = reports_dir / f"{date_str}.md"

    frontmatter = f"---\ntype: report\ntags: [jarvis/report]\nupdated: {date_str}\n---\n"
    out_path.write_text(f"{frontmatter}\n{text.strip()}\n", encoding="utf-8")
    return out_path
