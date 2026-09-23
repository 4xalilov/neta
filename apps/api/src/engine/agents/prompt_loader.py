"""Agent promptlarini ``agents/prompts/*.md`` fayllaridan o'qish va to'ldirish.

- ``load(name)`` — xom matn (kesh bilan).
- ``render(name, **kw)`` — ``{placeholder}`` larni to'ldiradi.

Promptlarda JSON sxemalar (``{"score":0,...}``) bor, shuning uchun oddiy ``str.format``
yiqiladi. ``render`` avval faqat ``{identifier}`` ko'rinishidagi joy-belgilarni qoldirib,
boshqa barcha ``{``/``}`` larni ekranlaydi, keyin ``str.format_map(SafeDict)`` qiladi:
noma'lum joy-belgi o'zgarishsiz qoladi (``{name}``), hech narsa ``KeyError`` bermaydi.
dict/list qiymatlar JSON (``ensure_ascii=False``) ko'rinishida qo'yiladi.
"""
from __future__ import annotations

import json
import re
from functools import lru_cache
from pathlib import Path
from typing import Any

PROMPTS_DIR = Path(__file__).parent / "prompts"

_PLACEHOLDER_RE = re.compile(r"\{([A-Za-z_][A-Za-z0-9_]*)\}")

__all__ = ["PROMPTS_DIR", "SafeDict", "load", "placeholders", "render"]


class SafeDict(dict):
    """``format_map`` uchun: yo'q kalit ``{key}`` bo'lib qoladi."""

    def __missing__(self, key: str) -> str:
        return "{" + key + "}"


@lru_cache(maxsize=64)
def load(name: str) -> str:
    """``prompts/<name>.md`` matni. Nom ``.md`` bilan yoki usiz berilishi mumkin."""
    fname = name if name.endswith(".md") else f"{name}.md"
    path = PROMPTS_DIR / fname
    if not path.is_file():
        raise FileNotFoundError(f"prompt topilmadi: {path}")
    return path.read_text(encoding="utf-8")


def placeholders(name: str) -> set[str]:
    """Promptdagi ``{identifier}`` joy-belgilar to'plami."""
    return set(_PLACEHOLDER_RE.findall(load(name)))


def _escape_non_placeholders(template: str) -> str:
    out: list[str] = []
    pos = 0
    for m in _PLACEHOLDER_RE.finditer(template):
        out.append(template[pos:m.start()].replace("{", "{{").replace("}", "}}"))
        out.append(m.group(0))
        pos = m.end()
    out.append(template[pos:].replace("{", "{{").replace("}", "}}"))
    return "".join(out)


def _to_text(value: Any) -> str:
    if value is None:
        return "—"
    if isinstance(value, str):
        return value if value.strip() else "—"
    if isinstance(value, (dict, list, tuple)):
        if not value:
            return "—"
        return json.dumps(value, ensure_ascii=False, indent=1, default=str)
    return str(value)


def render(name: str, **kw: Any) -> str:
    """Promptni to'ldiradi; stray qavslar va yo'q kalitlar xato bermaydi."""
    template = _escape_non_placeholders(load(name))
    values = SafeDict({k: _to_text(v) for k, v in kw.items()})
    return template.format_map(values)
