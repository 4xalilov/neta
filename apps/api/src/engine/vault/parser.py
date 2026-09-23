"""Markdown + YAML frontmatter parser (docs/10-obsidian-vault.md).

Har bir vault fayli ``---`` bilan o'ralgan YAML frontmatter + Markdown tanadan
iborat. Bu modul frontmatter'ni, sarlavhani (H1 yoki fayl nomi), ``[[wikilink]]``
larni (``|alias`` va ``#heading`` qismlari olib tashlanadi) va teglarni
(frontmatter ro'yxati + matn ichidagi ``#tag``) ajratib oladi.
"""

from __future__ import annotations

import datetime as _dt
import re
from dataclasses import dataclass, field

import yaml

__all__ = ["ParsedNote", "chunk", "parse"]

_FRONTMATTER_RE = re.compile(r"\A---[ \t]*\n(.*?)\n---[ \t]*\n?", re.DOTALL)
_H1_RE = re.compile(r"^[ \t]*#[ \t]+(.+?)[ \t]*$", re.MULTILINE)
# [[target]], [[target|alias]], [[target#heading]], [[target#heading|alias]]
_WIKILINK_RE = re.compile(r"\[\[([^\]|#]+?)(?:#[^\]|]*)?(?:\|[^\]]*)?\]\]")
_INLINE_TAG_RE = re.compile(r"(?<![\w/])#([A-Za-z][A-Za-z0-9_/-]*)")
_PARA_SPLIT_RE = re.compile(r"\n\s*\n")


@dataclass
class ParsedNote:
    """Bitta faylni tahlil qilish natijasi."""

    frontmatter: dict = field(default_factory=dict)
    body: str = ""
    title: str = ""
    tags: list[str] = field(default_factory=list)
    wikilinks: list[str] = field(default_factory=list)


def parse(text: str, *, fallback_title: str = "") -> ParsedNote:
    """Matnni frontmatter + tana + sarlavha + teglar + wikilink'larga bo'ladi."""
    frontmatter: dict = {}
    body = text
    match = _FRONTMATTER_RE.match(text)
    if match:
        try:
            loaded = yaml.safe_load(match.group(1))
        except yaml.YAMLError:
            loaded = None
        if isinstance(loaded, dict):
            frontmatter = _json_safe(loaded)
        body = text[match.end() :]

    title = _extract_title(body) or fallback_title
    tags = _extract_tags(frontmatter, body)
    wikilinks = _extract_wikilinks(body)

    return ParsedNote(
        frontmatter=frontmatter,
        body=body.strip(),
        title=title,
        tags=tags,
        wikilinks=wikilinks,
    )


def _json_safe(value: object) -> object:
    """YAML ``date``/``datetime`` kabi JSON'da serializatsiya bo'lmaydigan turlarni matnga aylantiradi."""
    if isinstance(value, (_dt.datetime, _dt.date)):
        return value.isoformat()
    if isinstance(value, dict):
        return {str(k): _json_safe(v) for k, v in value.items()}
    if isinstance(value, list):
        return [_json_safe(v) for v in value]
    return value


def _extract_title(body: str) -> str | None:
    match = _H1_RE.search(body)
    return match.group(1).strip() if match else None


def _extract_tags(frontmatter: dict, body: str) -> list[str]:
    ordered: list[str] = []
    seen: set[str] = set()

    def _add(value: str) -> None:
        value = value.strip()
        if value and value not in seen:
            seen.add(value)
            ordered.append(value)

    fm_tags = frontmatter.get("tags")
    if isinstance(fm_tags, list):
        for item in fm_tags:
            if item is not None and str(item).strip():
                _add(str(item))
    elif isinstance(fm_tags, str) and fm_tags.strip():
        _add(fm_tags)

    for m in _INLINE_TAG_RE.finditer(body):
        _add(m.group(1))

    return ordered


def _extract_wikilinks(body: str) -> list[str]:
    links: list[str] = []
    seen: set[str] = set()
    for m in _WIKILINK_RE.finditer(body):
        target = m.group(1).strip()
        if target and target not in seen:
            seen.add(target)
            links.append(target)
    return links


def chunk(text: str, max_chars: int = 1200) -> list[str]:
    """Matnni paragraf chegaralarida ``max_chars`` dan oshmaydigan bo'laklarga bo'ladi."""
    text = text.strip()
    if not text:
        return []
    if len(text) <= max_chars:
        return [text]

    chunks: list[str] = []
    current = ""
    for para in _PARA_SPLIT_RE.split(text):
        para = para.strip()
        if not para:
            continue
        candidate = f"{current}\n\n{para}" if current else para
        if len(candidate) <= max_chars:
            current = candidate
            continue
        if current:
            chunks.append(current)
            current = ""
        if len(para) <= max_chars:
            current = para
        else:
            for i in range(0, len(para), max_chars):
                chunks.append(para[i : i + max_chars])
    if current:
        chunks.append(current)
    return chunks
