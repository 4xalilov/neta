"""``evals/scripts/`` eval dataset yuklovchisi (roadmap 2.3).

Dataset repo ildizida (``evals/scripts/``), bu modul esa ``apps/api/src/engine/evals/``
ichida yashaydi — shuning uchun ``find_scripts_dir`` shu fayldan yuqoriga qarab
``evals/scripts/index.json`` ni qidiradi (``EVALS_DIR`` muhit o'zgaruvchisi bilan
bekor qilinishi mumkin, masalan boshqa joylashuvdagi konteynerlarda).
"""
from __future__ import annotations

import json
import os
from dataclasses import dataclass
from pathlib import Path
from typing import Any


class DatasetNotFoundError(RuntimeError):
    """``evals/scripts/index.json`` topilmadi."""


def find_scripts_dir() -> Path:
    env = os.environ.get("EVALS_DIR")
    if env:
        p = Path(env)
        if (p / "index.json").is_file():
            return p
        raise DatasetNotFoundError(f"EVALS_DIR={env!r} ichida index.json topilmadi")

    here = Path(__file__).resolve()
    for parent in here.parents:
        candidate = parent / "evals" / "scripts"
        if (candidate / "index.json").is_file():
            return candidate
    raise DatasetNotFoundError(
        "evals/scripts/index.json topilmadi. Repo ildizidan ishga tushiring yoki "
        "EVALS_DIR muhit o'zgaruvchisini shu papkaga o'rnating."
    )


@dataclass(frozen=True)
class Pair:
    """Bitta yaxshi/yomon juft: ``evals/scripts/index.json`` yozuvi + ikkala ssenariy."""

    id: str
    topic: str
    flaw_category: str
    critic: str  # "uz" | "brand" | "hook" — shu flaw qaysi kritikka tegishli
    why_bad: str
    expected: dict[str, dict[str, str]]  # {"good": {...}, "bad": {...}} -> ">=8" | "<8"
    good: dict[str, Any]
    bad: dict[str, Any]

    def expects_pass(self, kind: str, critic: str) -> bool:
        """``kind`` ("good"|"bad") + ``critic`` uchun kutilgan natija: ``score >= 8`` bo'lishi kerakmi."""
        return self.expected[kind][critic].strip().startswith(">=")


@dataclass(frozen=True)
class Dataset:
    pairs: list[Pair]
    brand_profile: dict[str, Any]
    taste_memory: list[Any]
    scripts_dir: Path


def load_dataset(scripts_dir: Path | None = None) -> Dataset:
    d = scripts_dir or find_scripts_dir()
    index = json.loads((d / "index.json").read_text(encoding="utf-8"))
    brand_profile = json.loads((d / "brand_profile.json").read_text(encoding="utf-8"))
    taste_memory = json.loads((d / "taste_memory.json").read_text(encoding="utf-8"))

    pairs: list[Pair] = []
    seen_topics: set[str] = set()
    for row in index["pairs"]:
        good = json.loads((d / row["good_file"]).read_text(encoding="utf-8"))
        bad = json.loads((d / row["bad_file"]).read_text(encoding="utf-8"))
        seen_topics.add(row["topic"])
        pairs.append(Pair(
            id=row["id"], topic=row["topic"], flaw_category=row["flaw_category"],
            critic=row["critic"], why_bad=row["why_bad"], expected=row["expected"],
            good=good, bad=bad,
        ))
    return Dataset(pairs=pairs, brand_profile=brand_profile, taste_memory=taste_memory,
                    scripts_dir=d)


def taste_reasons(taste_memory: list[Any]) -> list[str]:
    """``taste`` state maydoni uchun: prompt/kritik kutgan matn ro'yxati (docs/04 "taste top-5")."""
    out = []
    for item in taste_memory:
        if isinstance(item, dict):
            out.append(item.get("reason") or item.get("trigger_phrase") or "")
        else:
            out.append(str(item))
    return [t for t in out if t]
