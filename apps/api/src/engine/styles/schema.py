"""StyleTheme JSON Schema yuklash/tekshirish + WCAG kontrast tekshiruvi.

Sxemaning haqiqiy manbai ``apps/render/src/motion/styles/schema.ts`` (zod) dan
chiqarilgan ``{settings.render_dir}/schemas/style-theme.schema.json`` (boshqa
agent tomonidan yozilmoqda). U topilmasa, shu paketdagi zaxira nusxa
(``style-theme.schema.json`` — DIQQAT: qo'lda sinxronlashtiriladi, zod sxemasi
o'zgarsa shu faylni ham yangilang) ishlatiladi.
"""

from __future__ import annotations

import json
import logging
from pathlib import Path
from typing import Any

import jsonschema

from engine.settings import settings

logger = logging.getLogger(__name__)

__all__ = [
    "BUNDLED_SCHEMA_PATH",
    "check_contrast",
    "contrast_ratio",
    "load_schema",
    "relative_luminance",
    "schema_source",
    "validate_theme",
]

BUNDLED_SCHEMA_PATH = Path(__file__).with_name("style-theme.schema.json")

# docs/03-roadmap.md 2.8 birinchi (arzon) darvoza bosqichi: matn/fon va
# subtitr/fon juftliklari WCAG AA (≥ 4.5) kontrastni qanoatlantirishi kerak.
MIN_CONTRAST = 4.5


def schema_source() -> Path:
    """Qaysi fayldan sxema o'qilishini qaytaradi (render_dir'dagi asl nusxa yoki zaxira)."""
    primary = Path(settings.render_dir) / "schemas" / "style-theme.schema.json"
    if primary.is_file():
        return primary
    return BUNDLED_SCHEMA_PATH


def load_schema() -> dict[str, Any]:
    """Joriy ``settings.render_dir`` bo'yicha JSON Schema'ni o'qiydi (keshsiz — testlarda
    ``settings.render_dir`` monkeypatch qilinadi)."""
    path = schema_source()
    return json.loads(path.read_text(encoding="utf-8"))


def validate_theme(theme: dict[str, Any]) -> list[str]:
    """Sxemaga mos kelmagan joylarni o'zbekcha xabar sifatida qaytaradi (bo'sh — yaroqli)."""
    schema = load_schema()
    validator = jsonschema.Draft202012Validator(schema)
    problems: list[str] = []
    for err in sorted(validator.iter_errors(theme), key=lambda e: list(e.path)):
        loc = ".".join(str(p) for p in err.path) or "(ildiz)"
        problems.append(f"sxema: {loc}: {err.message}")
    return problems


def relative_luminance(hex_color: str) -> float:
    """WCAG nisbiy yorqinlik (0..1). Alfa-kanalli (8 xonali) reng bo'lsa alfa e'tiborsiz."""
    s = hex_color.lstrip("#")
    if len(s) in (3, 4):
        s = "".join(ch * 2 for ch in s[:3])
    else:
        s = s[:6]
    r, g, b = (int(s[i:i + 2], 16) / 255.0 for i in (0, 2, 4))

    def lin(c: float) -> float:
        return c / 12.92 if c <= 0.04045 else ((c + 0.055) / 1.055) ** 2.4

    r, g, b = lin(r), lin(g), lin(b)
    return 0.2126 * r + 0.7152 * g + 0.0722 * b


def contrast_ratio(hex1: str, hex2: str) -> float:
    """WCAG kontrast nisbati (1..21)."""
    l1, l2 = relative_luminance(hex1), relative_luminance(hex2)
    lighter, darker = max(l1, l2), min(l1, l2)
    return (lighter + 0.05) / (darker + 0.05)


def _pair_problem(label: str, fg: str, bg: str) -> str | None:
    try:
        ratio = contrast_ratio(fg, bg)
    except (ValueError, IndexError):
        return f"kontrast: {label} rangi o'qib bo'lmadi ({fg!r}/{bg!r})"
    if ratio < MIN_CONTRAST:
        return f"kontrast: {label} {ratio:.2f} (kerak >= {MIN_CONTRAST})"
    return None


def check_contrast(theme: dict[str, Any]) -> list[str]:
    """Matn/fon va subtitr(highlight ustidagi matn)/highlight juftliklarini tekshiradi.

    ``theme`` allaqachon sxema bo'yicha yaroqli deb hisoblanadi (chaqiruvchi
    avval ``validate_theme`` ni tekshiradi) — kalitlar yo'q/noto'g'ri bo'lsa
    shunchaki muammo sifatida qaytariladi, xato tashlamaydi.
    """
    colors = theme.get("colors") or {}
    problems: list[str] = []
    text, bg = colors.get("text"), colors.get("bg")
    if isinstance(text, str) and isinstance(bg, str):
        problem = _pair_problem("matn/fon", text, bg)
        if problem:
            problems.append(problem)
    on_highlight, highlight = colors.get("onHighlight"), colors.get("highlight")
    if isinstance(on_highlight, str) and isinstance(highlight, str):
        problem = _pair_problem("subtitr/highlight", on_highlight, highlight)
        if problem:
            problems.append(problem)
    return problems
