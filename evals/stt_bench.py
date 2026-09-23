"""STT provayderlarini ``evals/stt_test.md`` buyruqlari bilan sinash (roadmap 5.10).

Ishga tushirish (repo ildizidan, ``apps/api/.venv`` bilan)::

    PYTHONPATH=apps/api/src apps/api/.venv/bin/python -m evals.stt_bench \\
        --audio-dir evals/stt_audio --providers gemini,whisper --intents --out evals/out/stt/

    # oflayn, tarmoqsiz: "audio" = referens matnning o'zi (quvur/format tekshiruvi uchun)
    apps/api/.venv/bin/python -m evals.stt_bench --fake --intents --out evals/out/stt/

``--audio-dir`` dagi fayllar raqam bilan nomlanadi: ``1.ogg``, ``2.wav``, ``3.mp3`` ...
Har provayder uchun har faylni ``engine.integrations.stt.get_stt(name).transcribe`` bilan
o'qiydi, referens matnga nisbatan WER (so'z xato darajasi) hisoblaydi va
``<out>/results.md`` jadvalini yozadi. ``--intents`` — transkriptni
``engine.jarvis.intents.parse_intent`` dan o'tkazib, kutilgan niyat bilan solishtiradi
(qabul: STT + niyat ≥ 90%). ``--fake`` rejimida niyat — oddiy kalit-so'z klassifikatori
(faqat quvurni tekshirish uchun, aniqlik ko'rsatkichi sifatida ma'noli EMAS).

Tarmoq/kalit yo'qligi xatolari jadvalga "XATO" sifatida yoziladi — skript to'xtamaydi.
"""
from __future__ import annotations

import argparse
import asyncio
import json
import os
import re
import sys
import time
from dataclasses import dataclass, field
from datetime import datetime
from pathlib import Path
from typing import Any
from zoneinfo import ZoneInfo

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

from engine import llm
from engine.integrations import stt
from engine.jarvis import intents as intents_mod

_DEFAULT_COMMANDS = Path(__file__).parent / "stt_test.md"
_LINE_RE = re.compile(r"^(\d+)\.\s+(.+?)\s+→\s+([a-z_]+)\s*(\{.*\})?\s*$")
_AUDIO_EXTS = (".ogg", ".oga", ".opus", ".wav", ".mp3", ".m4a")
WER_OK = 0.25  # buyruq "tushunildi" deb hisoblanadigan maksimal WER

BENCH_STAFF = [("s1", "Aziz"), ("s2", "Dilnoza"), ("s3", "Jasur"), ("s4", "Nodira")]
BENCH_LEADS = [("l1", "Malika"), ("l2", "Sardor Aliyev")]
BENCH_WORKSPACES = [("w1", "Qahva uyi"), ("w2", "Fitnes klub Olimp")]


@dataclass
class Command:
    n: int
    text: str
    intent: str
    entities: dict[str, Any] = field(default_factory=dict)


def load_commands(path: Path = _DEFAULT_COMMANDS) -> list[Command]:
    out: list[Command] = []
    for line in path.read_text(encoding="utf-8").splitlines():
        m = _LINE_RE.match(line.strip())
        if m:
            ents = json.loads(m.group(4)) if m.group(4) else {}
            out.append(Command(int(m.group(1)), m.group(2).strip(), m.group(3), ents))
    return out


# ---------------------------------------------------------------- WER


def _norm_words(text: str) -> list[str]:
    t = text.lower()
    t = re.sub(r"[ʻʼ‘’`´]", "'", t)
    t = re.sub(r"[.,!?;«»\"()\[\]—–]", " ", t)
    t = re.sub(r"(?<!\d)[:\-](?!\d)", " ", t)  # 15:00 va 1-son saqlanadi
    return t.split()


def wer(reference: str, hypothesis: str) -> float:
    """Word Error Rate = (S + D + I) / N (Levenshtein so'zlar bo'yicha)."""
    ref, hyp = _norm_words(reference), _norm_words(hypothesis)
    if not ref:
        return 0.0 if not hyp else 1.0
    prev = list(range(len(hyp) + 1))
    for i, r in enumerate(ref, 1):
        cur = [i] + [0] * len(hyp)
        for j, h in enumerate(hyp, 1):
            cur[j] = min(prev[j] + 1, cur[j - 1] + 1, prev[j - 1] + (r != h))
        prev = cur
    return prev[-1] / len(ref)


# ---------------------------------------------------------------- fake rejim


class TextAsAudioSTT:
    """``--fake``: "audio" baytlari = referens matn (UTF-8). Tarmoqsiz quvur tekshiruvi."""

    name = "fake"

    async def transcribe(self, audio: bytes, fmt: str, *, workspace_id: str = "") -> Any:
        return stt.STTResult(text=audio.decode("utf-8"), provider=self.name, confidence=1.0)


_KEYWORDS: list[tuple[str, str]] = [
    (r"hammasi(ga|ni)", "approve_all"),
    (r"\b(o't)\b|o'tamiz", "select_workspace"),
    (r"eslat|turtib", "remind_staff"),
    (r"qo'ng'iroq|zvonit qil\b", "call_lead"),
    (r"lid\w* ?(ga|larga)? yoz|lidlarga|ga yoz|yana yoz", "message_lead"),
    (r"hisobot|otchyot|sotuv bo'ldi", "daily_report"),
    (r"nechta lid|lidlar qancha|lid tushdi|lid keldi", "query_leads"),
    (r"vazifa\w* (holati|kechik)|ochiq ish|kechikkan vazifa|vazifa kechik", "query_tasks"),
    (r"reels|video", "create_brief"),
    (r"joyla", "schedule_post"),
    (r"gapir|ovozni", "update_settings"),
    (r"ayt|topshir|vazifa:", "assign_task"),
    (r"^(ha|mayli)\b", "approve"),
    (r"^(yo'q|otmena)|bekor", "reject"),
    (r"salom|rahmat|qalaysan", "smalltalk"),
]


def keyword_intent(text: str) -> dict[str, Any]:
    """Juda oddiy klassifikator — faqat ``--fake --intents`` quvurini tekshirish uchun."""
    t = re.sub(r"[ʻʼ‘’`]", "'", text.lower())
    for pattern, name in _KEYWORDS:
        if re.search(pattern, t):
            ents: dict[str, Any] = {}
            if name in ("assign_task", "remind_staff"):
                ents["staff_name"] = t.split()[0].strip(",")
                ents["task_title"] = t
            if name in ("message_lead", "call_lead"):
                for temp, key in (("issiq", "hot"), ("iliq", "warm"), ("sovuq", "cold")):
                    if temp in t:
                        ents["temperature"] = key
                if "temperature" not in ents:
                    ents["lead_name"] = t.split()[0].strip(",")
            if name == "select_workspace":
                ents["workspace_name"] = t.split(" o't")[0]
            if name == "update_settings":
                ents.update({"setting_key": "pronoun", "setting_value": "sen"})
            return {"intent": name, "entities": ents, "confidence": 0.9}
    return {"intent": "unknown", "entities": {}, "confidence": 0.3}


# ---------------------------------------------------------------- bench


def find_audio(audio_dir: Path) -> dict[int, Path]:
    out: dict[int, Path] = {}
    if not audio_dir.is_dir():
        return out
    for p in sorted(audio_dir.iterdir()):
        if p.suffix.lower() in _AUDIO_EXTS and p.stem.isdigit():
            out[int(p.stem)] = p
    return out


def _bench_context() -> intents_mod.OwnerContext:
    return intents_mod.OwnerContext(
        now=datetime(2026, 9, 23, 10, 0, tzinfo=ZoneInfo("Asia/Tashkent")),
        timezone="Asia/Tashkent", workspace_id="bench", company="Qahva uyi",
        staff=list(BENCH_STAFF), leads=list(BENCH_LEADS), workspaces=list(BENCH_WORKSPACES),
    )


async def _bench_one(provider: Any, cmd: Command, audio: bytes, fmt: str,
                     with_intents: bool) -> dict[str, Any]:
    t0 = time.perf_counter()
    row: dict[str, Any] = {"provider": provider.name, "n": cmd.n, "ref": cmd.text,
                           "expected_intent": cmd.intent, "hyp": None, "wer": None,
                           "usd": None, "ms": None, "intent": None, "intent_ok": None,
                           "error": None}
    try:
        res = await provider.transcribe(audio, fmt)
    except Exception as exc:  # noqa: BLE001 — jadvalga yozib davom etamiz
        row.update(ms=round((time.perf_counter() - t0) * 1000), error=str(exc)[:200])
        return row
    row["ms"] = round((time.perf_counter() - t0) * 1000)
    hyp = stt.normalize_apostrophes(res.text)
    row.update(hyp=hyp, wer=round(wer(cmd.text, hyp), 3), usd=round(res.usd, 5))
    if with_intents:
        intent = await intents_mod.parse_intent(hyp, context=_bench_context())
        row["intent"] = intent.intent
        row["intent_ok"] = intent.intent == cmd.intent
    return row


def summarize(rows: list[dict[str, Any]]) -> dict[str, dict[str, Any]]:
    by: dict[str, dict[str, Any]] = {}
    for r in rows:
        s = by.setdefault(r["provider"], {"n": 0, "errors": 0, "wer_sum": 0.0, "wer_ok": 0,
                                          "intent_n": 0, "intent_ok": 0, "e2e_ok": 0,
                                          "usd": 0.0})
        s["n"] += 1
        if r["error"]:
            s["errors"] += 1
            continue
        s["wer_sum"] += r["wer"]
        s["usd"] += r["usd"] or 0.0
        ok_wer = r["wer"] <= WER_OK
        s["wer_ok"] += ok_wer
        if r["intent_ok"] is not None:
            s["intent_n"] += 1
            s["intent_ok"] += r["intent_ok"]
            s["e2e_ok"] += ok_wer and r["intent_ok"]
    for s in by.values():
        done = s["n"] - s["errors"]
        s["wer_avg"] = round(s["wer_sum"] / done, 3) if done else None
    return by


def write_results_md(rows: list[dict[str, Any]], path: Path) -> None:
    summary = summarize(rows)
    lines = ["# STT bench natijalari (roadmap 5.10)", "",
             f"Buyruq 'tushunildi': WER ≤ {WER_OK}. Qabul: STT + niyat ≥ 90%.", "",
             ("| provayder | buyruq | xato | o'rtacha WER | WER ≤ 0.25 | niyat to'g'ri "
              "| STT+niyat | $ |"),
             "|---|---|---|---|---|---|---|---|"]
    for name, s in summary.items():
        intent_cell = f"{s['intent_ok']}/{s['intent_n']}" if s["intent_n"] else "-"
        e2e_cell = (f"{s['e2e_ok']}/{s['intent_n']} ({100 * s['e2e_ok'] / s['intent_n']:.0f}%)"
                    if s["intent_n"] else "-")
        lines.append(f"| {name} | {s['n']} | {s['errors']} | {s['wer_avg']} | "
                     f"{s['wer_ok']}/{s['n'] - s['errors']} | {intent_cell} | {e2e_cell} | "
                     f"{s['usd']:.4f} |")
    lines += ["", "| provayder | # | WER | niyat (kutilgan) | ms | transkript / xato |",
              "|---|---|---|---|---|---|"]
    for r in rows:
        tail = r["hyp"] if r["error"] is None else f"XATO: {r['error']}"
        intent = "-" if r["intent"] is None else (
            f"{r['intent']}{' ✅' if r['intent_ok'] else ' ❌'} ({r['expected_intent']})")
        wer_cell = "-" if r["wer"] is None else r["wer"]
        lines.append(f"| {r['provider']} | {r['n']} | {wer_cell} | {intent} | {r['ms']} | "
                     f"{tail} |")
    path.write_text("\n".join(lines) + "\n", encoding="utf-8")


async def run(providers: list[str], out_dir: Path, commands_path: Path = _DEFAULT_COMMANDS,
              audio_dir: Path | None = None, *, fake: bool = False,
              with_intents: bool = False) -> list[dict[str, Any]]:
    out_dir.mkdir(parents=True, exist_ok=True)
    commands = load_commands(commands_path)
    if not commands:
        raise SystemExit(f"{commands_path} da buyruq topilmadi")

    if fake:
        provider_objs: list[Any] = [TextAsAudioSTT()]
        inputs = {c.n: (c.text.encode("utf-8"), "txt") for c in commands}
        if with_intents:
            llm.set_fake(lambda tier, system, user: keyword_intent(user))
    else:
        files = find_audio(audio_dir or Path("evals/stt_audio"))
        if not files:
            raise SystemExit(f"{audio_dir}: raqamli audio fayl topilmadi (1.ogg, 2.wav, ...)")
        provider_objs = [stt.get_stt(p) for p in providers]
        inputs = {n: (p.read_bytes(), p.suffix.lstrip(".")) for n, p in files.items()}

    rows: list[dict[str, Any]] = []
    try:
        for provider in provider_objs:
            for cmd in commands:
                if cmd.n not in inputs:
                    continue
                audio, fmt = inputs[cmd.n]
                row = await _bench_one(provider, cmd, audio, fmt, with_intents)
                rows.append(row)
                status = "OK" if row["error"] is None else f"XATO: {row['error']}"
                print(f"[{provider.name} #{cmd.n}] {status} wer={row['wer']} "
                      f"intent={row['intent']} ({row['ms']} ms)")
    finally:
        if fake and with_intents:
            llm.clear_fake()
    write_results_md(rows, out_dir / "results.md")
    print(f"\nNatijalar: {out_dir / 'results.md'}")
    return rows


def main(argv: list[str] | None = None) -> None:
    parser = argparse.ArgumentParser(description="STT bench: evals/stt_test.md (roadmap 5.10)")
    parser.add_argument("--providers", default="gemini",
                        help="vergul bilan: gemini,whisper,aisha,uzbekvoice,azure")
    parser.add_argument("--audio-dir", default="evals/stt_audio",
                        help="raqam bilan nomlangan audio fayllar papkasi")
    parser.add_argument("--commands", default=str(_DEFAULT_COMMANDS))
    parser.add_argument("--out", default="evals/out/stt/")
    parser.add_argument("--fake", action="store_true",
                        help="tarmoqsiz: referens matn 'audio' sifatida (quvur tekshiruvi)")
    parser.add_argument("--intents", action="store_true",
                        help="transkriptni parse_intent'dan o'tkazib niyatni solishtirish")
    args = parser.parse_args(argv)
    providers = [p.strip() for p in args.providers.split(",") if p.strip()]
    asyncio.run(run(providers, Path(args.out), Path(args.commands), Path(args.audio_dir),
                    fake=args.fake, with_intents=args.intents))


if __name__ == "__main__":
    main()
