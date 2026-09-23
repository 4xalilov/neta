"""``evals/scripts/`` dataset yaxlitligi + ``engine.evals.run`` --fake rejimida
>= 85% aniqlikka yetishini tekshiradi (roadmap 2.3 qabul mezoni)."""
from __future__ import annotations

from collections import Counter

import pytest
from pydantic import ValidationError

from engine.evals.dataset import load_dataset
from engine.evals.run import ACCURACY_THRESHOLD, run_eval, write_report
from engine.graphs.nodes.writer import ScriptModel


@pytest.fixture(scope="module")
def dataset():
    return load_dataset()


# ---------------------------------------------------------------- dataset integrity


def test_dataset_has_30_pairs(dataset):
    assert len(dataset.pairs) == 30


def test_dataset_topics_are_unique(dataset):
    topics = [p.topic for p in dataset.pairs]
    assert len(set(topics)) == len(topics) == 30


def test_dataset_every_bad_script_names_a_flaw_category(dataset):
    for pair in dataset.pairs:
        assert pair.flaw_category, f"{pair.id}: flaw_category yo'q"
        assert pair.critic in ("uz", "brand", "hook")
        assert pair.why_bad.strip()


def test_dataset_schema_valid_against_writer_model(dataset):
    """Har ikkala (good/bad) ssenariy Writer'ning ``ScriptModel`` sxemasiga mos
    (hooks[3], scenes[3-6], duration_s 3-8 va h.k.) — dataset "Writer chiqargan"
    struktura bilan bir xil bo'lishi shart (vazifa ta'rifi)."""
    for pair in dataset.pairs:
        for kind, script in (("good", pair.good), ("bad", pair.bad)):
            try:
                ScriptModel.model_validate(script)
            except ValidationError as exc:  # pragma: no cover - xato xabarini ko'rsatish uchun
                pytest.fail(f"{pair.id}_{kind}.json sxemaga mos emas: {exc}")


def test_dataset_expected_shape(dataset):
    for pair in dataset.pairs:
        for kind in ("good", "bad"):
            exp = pair.expected[kind]
            assert set(exp) == {"uz", "brand", "hook"}
            for v in exp.values():
                assert v in (">=8", "<8")
        # good ssenariy har doim barcha o'lchamlarda o'tishi kutiladi
        assert all(v == ">=8" for v in pair.expected["good"].values())
        # bad ssenariyda faqat o'z kritikasi < 8, qolganlari o'tadi
        bad_exp = pair.expected["bad"]
        assert bad_exp[pair.critic] == "<8"
        assert sum(1 for v in bad_exp.values() if v == "<8") == 1


def test_dataset_flaw_categories_cover_rubric_dimensions(dataset):
    """docs/04 rubrikasidagi barcha o'lchamlar kamida bitta juft bilan qoplangan."""
    expected_categories = {
        "kalka_ruscha_konstruksiya", "siz_sen_aralash", "raqam_tts_notogri",
        "qisqartma", "subtitr_uzun", "taqiqlangan_soz", "taste_memory_takror",
        "hook_vada_yoq", "hook_body_uzilgan", "jargon", "uzun_jumla",
    }
    present = {p.flaw_category for p in dataset.pairs}
    assert expected_categories <= present
    counts = Counter(p.flaw_category for p in dataset.pairs)
    assert sum(counts.values()) == 30


def test_dataset_brand_profile_and_taste_memory_present(dataset):
    assert dataset.brand_profile.get("address_form") == "siz"
    assert dataset.brand_profile.get("forbidden_words")
    assert len(dataset.taste_memory) == 5
    for item in dataset.taste_memory:
        assert item.get("reason") and item.get("trigger_phrase")


# ---------------------------------------------------------------- --fake runner


async def test_fake_run_reaches_accuracy_threshold_per_critic(dataset):
    report = await run_eval(critic="all", fake=True, dataset=dataset)
    assert report.critic_names == ("uz", "brand", "hook")
    for c in report.critic_names:
        st = report.stats[c]
        assert st.total > 0
        assert st.accuracy >= ACCURACY_THRESHOLD, (
            f"{c} kritik aniqligi {st.accuracy:.1%} < {ACCURACY_THRESHOLD:.0%}"
        )
    assert report.passed
    assert report.total_usd >= 0.0


async def test_fake_run_single_critic_filter(dataset):
    report = await run_eval(critic="hook", fake=True, dataset=dataset)
    assert report.critic_names == ("hook",)
    assert "uz" not in report.stats
    assert report.stats["hook"].accuracy >= ACCURACY_THRESHOLD


async def test_fake_run_limit(dataset):
    report = await run_eval(critic="all", fake=True, limit=4, dataset=dataset)
    assert report.pairs_count == 4


async def test_fake_run_per_flaw_recall_is_perfect(dataset):
    """Heuristic kritik dataset uchun махсус ишланган — har flaw kategoriyasi 100%
    recall bilan aniqlanishi kutiladi (bu ham dataset flaw'lari haqiqatan
    "aniqlanadigan" ekanini tasdiqlaydi, vazifa ta'rifidagi talab)."""
    report = await run_eval(critic="all", fake=True, dataset=dataset)
    for cat, results in report.flaw_recall.items():
        assert all(results), f"{cat}: kamida bitta bad ssenariy aniqlanmadi"


async def test_report_file_written(dataset, tmp_path, monkeypatch):
    report = await run_eval(critic="all", fake=True, dataset=dataset)
    path = write_report(report, dataset, report_date="2000-01-01")
    try:
        assert path.is_file()
        assert path.name == "critics_2000-01-01.md"
        text = path.read_text(encoding="utf-8")
        assert "Kritiklar eval hisoboti" in text
        assert "uz" in text and "brand" in text and "hook" in text
    finally:
        path.unlink(missing_ok=True)
