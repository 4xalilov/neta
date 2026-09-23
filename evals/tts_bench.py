"""TTS providerlarni ``evals/tts_test.md`` jumlalari bilan sinash (bosqich 1.2).

Ishga tushirish (repo ildizidan, ``apps/api/.venv`` bilan)::

    PYTHONPATH=apps/api/src apps/api/.venv/bin/python -m evals.tts_bench \\
        --providers edge,navoiy --out evals/out/

Har provayder uchun ``evals/tts_test.md`` dagi har raqamlangan jumlani sintez qiladi,
audio faylni ``evals/out/<provayder>_<n>.<mp3|wav>`` ga yozadi va ``evals/out/results.md``
jadvalini (belgi soni, davomiylik, $ narx, kechikish ms) chiqaradi.

Tarmoq/kalit yo'qligi (masalan Navoiy serveri ishga tushmagan, Azure/Aisha kaliti yo'q)
bilan bog'liq xatolar jadvalga "XATO" sifatida yoziladi — skript to'xtamay davom etadi.
Bu skript test emas (pytest bilan yig'ilmaydi), qo'lda/CI cron orqali ishga tushiriladi.
"""
from __future__ import annotations

import argparse
import asyncio
import os
import re
import sys
import time
from pathlib import Path
from typing import Any

# Mustaqil ishga tushirish uchun: apps/api/src ni yo'lga qo'shamiz va
# majburiy sozlamalarga (DB, Redis, S3) qo'g'irchoq qiymat beramiz — TTS ularga muhtoj emas.
_REPO = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(_REPO / "apps" / "api" / "src"))
for _k, _v in {
    "DATABASE_URL": "sqlite+aiosqlite:///:memory:",
    "REDIS_URL": "redis://localhost:6379/0",
    "S3_ENDPOINT": "http://localhost:9000",
    "S3_ACCESS_KEY": "x",
    "S3_SECRET_KEY": "x",
}.items():
    os.environ.setdefault(_k, _v)

from engine.integrations import tts

_SENTENCE_RE = re.compile(r"^(\d+)\.\s+(.*)$")
_DEFAULT_SENTENCES = Path(__file__).parent / "tts_test.md"


def load_sentences(path: Path) -> list[tuple[int, str]]:
    """``tts_test.md`` dagi raqamlangan qatorlarni ``[(n, jumla), ...]`` qilib o'qiydi."""
    out: list[tuple[int, str]] = []
    for line in path.read_text(encoding="utf-8").splitlines():
        m = _SENTENCE_RE.match(line.strip())
        if m:
            out.append((int(m.group(1)), m.group(2).strip()))
    return out


async def _bench_one(provider_name: str, n: int, text: str, out_dir: Path) -> dict[str, Any]:
    norm_text = tts.to_tts_text(text)
    t0 = time.perf_counter()
    try:
        provider = tts.get_provider(provider_name)
        result = await provider.synthesize(norm_text)
    except Exception as exc:  # noqa: BLE001 — jadvalga yozib, keyingi jumlaga o'tamiz
        return {
            "provider": provider_name,
            "n": n,
            "chars": len(norm_text),
            "duration_s": None,
            "usd": None,
            "ms": round((time.perf_counter() - t0) * 1000),
            "file": None,
            "error": str(exc),
        }
    ms = round((time.perf_counter() - t0) * 1000)
    path = out_dir / f"{provider_name}_{n}.{result.format}"
    path.write_bytes(result.audio)
    return {
        "provider": provider_name,
        "n": n,
        "chars": result.chars,
        "duration_s": round(result.duration_s, 2),
        "usd": round(result.usd, 5),
        "ms": ms,
        "file": path.name,
        "error": None,
    }


def write_results_md(rows: list[dict[str, Any]], path: Path) -> None:
    lines = [
        "# TTS bench natijalari (bosqich 1.2)",
        "",
        "| provayder | # | belgi | davomiylik (s) | $ | kechikish (ms) | fayl / xato |",
        "|---|---|---|---|---|---|---|",
    ]
    for r in rows:
        if r["error"] is None:
            tail, duration, usd = r["file"], r["duration_s"], r["usd"]
        else:
            tail, duration, usd = f"XATO: {r['error']}", "-", "-"
        lines.append(
            f"| {r['provider']} | {r['n']} | {r['chars']} | {duration} | {usd} | "
            f"{r['ms']} | {tail} |"
        )
    path.write_text("\n".join(lines) + "\n", encoding="utf-8")


async def run(providers: list[str], out_dir: Path, sentences_path: Path) -> list[dict[str, Any]]:
    out_dir.mkdir(parents=True, exist_ok=True)
    sentences = load_sentences(sentences_path)
    if not sentences:
        raise SystemExit(f"{sentences_path} da raqamlangan jumla topilmadi")
    rows: list[dict[str, Any]] = []
    for provider_name in providers:
        for n, text in sentences:
            row = await _bench_one(provider_name, n, text, out_dir)
            rows.append(row)
            status = "OK" if row["error"] is None else f"XATO: {row['error']}"
            print(f"[{provider_name} #{n}] {status} ({row['ms']} ms)")
    write_results_md(rows, out_dir / "results.md")
    print(f"\nNatijalar: {out_dir / 'results.md'}")
    return rows


def main(argv: list[str] | None = None) -> None:
    parser = argparse.ArgumentParser(
        description="TTS providerlarni evals/tts_test.md jumlalari bilan sinash (bosqich 1.2)."
    )
    parser.add_argument(
        "--providers",
        default="edge",
        help="vergul bilan ajratilgan provayder nomlari, masalan: edge,navoiy,azure,aisha",
    )
    parser.add_argument("--out", default="evals/out/", help="chiqish papkasi")
    parser.add_argument(
        "--sentences",
        default=str(_DEFAULT_SENTENCES),
        help="jumlalar fayli yo'li (default: evals/tts_test.md)",
    )
    args = parser.parse_args(argv)
    providers = [p.strip() for p in args.providers.split(",") if p.strip()]
    asyncio.run(run(providers, Path(args.out), Path(args.sentences)))


if __name__ == "__main__":
    main()
