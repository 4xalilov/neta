"""``python -m engine.evals.run`` — 3 kritikni ``evals/scripts/`` dataseti bilan sinaydi
(roadmap 2.3).

    python -m engine.evals.run [--critic uz|brand|hook|all] [--limit N] [--fake] [--no-fail]

Har juft (``NNN_good.json``/``NNN_bad.json``) uchun haqiqiy kritik nodlarini
(``graphs/nodes/critics.uz_critic`` va h.k.) minimal ``DayState`` bilan chaqiradi va
natijani ``evals/scripts/index.json`` dagi kutilgan qiymat (``>=8`` yoki ``<8``) bilan
solishtiradi. Chiqish: Markdown jadval (stdout + ``evals/out/critics_<sana>.md``).

``--fake`` — tarmoqqa chiqmaydi: ``engine.llm.set_fake`` orqali
``engine.evals.heuristic_critic.HeuristicCritic`` (oddiy qoida-asosidagi, LLM emas)
ulanadi. Shu rejim CI/testlarda ishlatiladi va ``evals/scripts/`` dagi nuqsonlar
avtomatik aniqlanishini tasdiqlaydi.

``docs/03-roadmap.md`` 2.3 qabul mezoni: har kritik aniqligi >= 85%. Shunga yetmasa
chiqish kodi 1 (``--no-fail`` bilan bekor qilinadi).
"""
from __future__ import annotations

# ``engine.graphs.nodes.critics`` import qilinganda ``engine.settings.Settings()`` ham
# yuklanadi (majburiy maydonlar: DATABASE_URL va h.k.). Eval faqat kritik promptlarini
# chaqiradi — DB/S3'ga chiqmaydi — shuning uchun bu yerda faqat YO'Q bo'lsa xavfsiz
# standart qiymatlar qo'yiladi (haqiqiy ``.env``/muhit o'zgaruvchilari ustunlik qiladi).
import os

for _k, _v in {
    "DATABASE_URL": "postgresql+asyncpg://eval:eval@localhost/eval",
    "REDIS_URL": "redis://localhost:6379/0",
    "S3_ENDPOINT": "http://localhost:9000",
    "S3_ACCESS_KEY": "eval",
    "S3_SECRET_KEY": "eval",
}.items():
    os.environ.setdefault(_k, _v)

import argparse
import asyncio
import logging
from dataclasses import dataclass, field
from datetime import UTC, datetime
from pathlib import Path
from typing import Any

from engine import cost_tracker, llm
from engine.graphs.nodes import critics

from .dataset import Dataset, Pair, load_dataset, taste_reasons
from .heuristic_critic import HeuristicCritic

logger = logging.getLogger(__name__)

ACCURACY_THRESHOLD = 0.85  # docs/03-roadmap.md 2.3 qabul mezoni
CRITIC_NAMES = ("uz", "brand", "hook")
CRITIC_NODES = {
    "uz": critics.uz_critic,
    "brand": critics.brand_critic,
    "hook": critics.hook_critic,
}


@dataclass
class CriticStats:
    name: str
    tp: int = 0  # bad, to'g'ri < 8 deb topildi
    fp: int = 0  # good/tegishsiz bad, noto'g'ri < 8 deb topildi (yolg'on signal)
    tn: int = 0  # good/tegishsiz bad, to'g'ri >= 8 deb topildi
    fn: int = 0  # bad, noto'g'ri >= 8 deb topildi (nuqson o'tkazib yuborildi)
    gaps: list[int] = field(default_factory=list)  # good_score - bad_score, faqat o'z flaw'i uchun

    @property
    def total(self) -> int:
        return self.tp + self.fp + self.tn + self.fn

    @property
    def accuracy(self) -> float:
        return (self.tp + self.tn) / self.total if self.total else 0.0

    @property
    def mean_gap(self) -> float:
        return sum(self.gaps) / len(self.gaps) if self.gaps else 0.0


@dataclass
class EvalReport:
    critic_names: tuple[str, ...]
    stats: dict[str, CriticStats]
    flaw_recall: dict[str, list[bool]]
    total_usd: float
    pairs_count: int
    markdown: str

    @property
    def passed(self) -> bool:
        return all(self.stats[c].accuracy >= ACCURACY_THRESHOLD for c in self.critic_names)


def _build_state(dataset: Dataset, script: dict[str, Any]) -> dict[str, Any]:
    return {
        "workspace_id": "eval",
        "brand_profile": dataset.brand_profile,
        "script": script,
        "taste": taste_reasons(dataset.taste_memory),
        "references": [],
        "plan_item": {},
        "iteration": 0,
    }


async def _score(critic_name: str, state: dict[str, Any]) -> int:
    out = await CRITIC_NODES[critic_name](state)
    review = out["reviews"][0]
    return int(review.get("score", 0))


def render_markdown(report_date: str, dataset: Dataset, critic_names: tuple[str, ...],
                    stats: dict[str, CriticStats], flaw_recall: dict[str, list[bool]],
                    total_usd: float) -> str:
    lines = [
        "# Kritiklar eval hisoboti",
        "",
        f"- Sana: {report_date}",
        f"- Dataset: `{dataset.scripts_dir}` ({len(dataset.pairs)} juft)",
        f"- Jami xarajat: ${total_usd:.4f}",
        f"- Chegara (docs/03 2.3): aniqlik >= {ACCURACY_THRESHOLD:.0%}",
        "",
        "## Kritik aniqligi",
        "",
        "| Kritik | Aniqlik | O'tdi | TP | FP | TN | FN | O'rtacha ball farqi (good-bad) |",
        "|---|---|---|---|---|---|---|---|",
    ]
    for c in critic_names:
        st = stats[c]
        ok = "✅" if st.accuracy >= ACCURACY_THRESHOLD else "❌"
        lines.append(
            f"| {c} | {st.accuracy * 100:.1f}% | {ok} | {st.tp} | {st.fp} | {st.tn} | {st.fn} "
            f"| {st.mean_gap:+.2f} |"
        )
    lines += ["", "## Flaw kategoriyasi bo'yicha recall (bad ssenariy to'g'ri < 8 topildimi)", "",
              "| Flaw kategoriyasi | Recall | n |", "|---|---|---|"]
    for cat, results in sorted(flaw_recall.items()):
        recall = sum(results) / len(results) if results else 0.0
        lines.append(f"| {cat} | {recall * 100:.1f}% | {len(results)} |")
    lines.append("")
    return "\n".join(lines)


async def run_eval(*, critic: str = "all", limit: int | None = None,
                   fake: bool = False, dataset: Dataset | None = None) -> EvalReport:
    ds = dataset or load_dataset()
    pairs: list[Pair] = ds.pairs[:limit] if limit else ds.pairs
    critic_names = CRITIC_NAMES if critic in (None, "all") else (critic,)

    heuristic: HeuristicCritic | None = None
    if fake:
        heuristic = HeuristicCritic()
        llm.set_fake(heuristic)

    stats = {c: CriticStats(c) for c in critic_names}
    flaw_recall: dict[str, list[bool]] = {}
    recent_start = len(cost_tracker.RECENT)

    try:
        for pair in pairs:
            scores: dict[str, dict[str, int]] = {"good": {}, "bad": {}}
            for kind, script in (("good", pair.good), ("bad", pair.bad)):
                if heuristic is not None:
                    heuristic.use(script, ds.brand_profile, ds.taste_memory)
                state = _build_state(ds, script)
                for c in critic_names:
                    score = await _score(c, state)
                    scores[kind][c] = score
                    expect_pass = pair.expects_pass(kind, c)
                    got_pass = score >= critics.PASS_SCORE
                    st = stats[c]
                    if got_pass and expect_pass:
                        st.tn += 1
                    elif (not got_pass) and (not expect_pass):
                        st.tp += 1
                    elif got_pass and (not expect_pass):
                        st.fn += 1
                    else:
                        st.fp += 1

            if pair.critic in critic_names:
                c = pair.critic
                stats[c].gaps.append(scores["good"][c] - scores["bad"][c])
                flaw_recall.setdefault(pair.flaw_category, []).append(
                    scores["bad"][c] < critics.PASS_SCORE
                )
    finally:
        if fake:
            llm.clear_fake()

    total_usd = sum(e["usd"] for e in list(cost_tracker.RECENT)[recent_start:])
    report_date = datetime.now(UTC).date().isoformat()
    markdown = render_markdown(report_date, ds, critic_names, stats, flaw_recall, total_usd)

    return EvalReport(critic_names=critic_names, stats=stats, flaw_recall=flaw_recall,
                      total_usd=total_usd, pairs_count=len(pairs), markdown=markdown)


def write_report(report: EvalReport, dataset: Dataset, *, report_date: str | None = None) -> Path:
    out_dir = dataset.scripts_dir.parent / "out"
    out_dir.mkdir(parents=True, exist_ok=True)
    date = report_date or datetime.now(UTC).date().isoformat()
    path = out_dir / f"critics_{date}.md"
    path.write_text(report.markdown, encoding="utf-8")
    return path


def _parse_args(argv: list[str] | None) -> argparse.Namespace:
    parser = argparse.ArgumentParser(
        prog="python -m engine.evals.run",
        description="UzCritic/BrandCritic/HookCritic aniqligini evals/scripts/ dataseti bilan o'lchaydi.",
    )
    parser.add_argument("--critic", choices=["uz", "brand", "hook", "all"], default="all")
    parser.add_argument("--limit", type=int, default=None, help="faqat birinchi N juft")
    parser.add_argument("--fake", action="store_true",
                        help="LLM chaqirmaydi — deterministik heuristic kritikdan foydalanadi")
    parser.add_argument("--no-fail", action="store_true",
                        help="aniqlik 85%%dan past bo'lsa ham chiqish kodi 0")
    return parser.parse_args(argv)


def main(argv: list[str] | None = None) -> int:
    args = _parse_args(argv)
    dataset = load_dataset()
    report = asyncio.run(run_eval(critic=args.critic, limit=args.limit, fake=args.fake,
                                  dataset=dataset))
    print(report.markdown)
    path = write_report(report, dataset)
    print(f"\nHisobot yozildi: {path}")
    if not report.passed and not args.no_fail:
        return 1
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
