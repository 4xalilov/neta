"""Writer ↔ Critics halqasi (roadmap 2.2): ball < 8 → qayta yozish, max 3 iteratsiya."""
from __future__ import annotations

import uuid

from sqlalchemy import select

from engine.graphs.day_subgraph import compile_graph, route_after_critics
from engine.graphs.nodes.asset_gen import fit_scene_durations, split_words_by_scenes
from engine.graphs.nodes.writer import (
    apply_default_motion,
    format_previous_reviews,
    validate_script,
)
from engine.graphs.state import merge_reviews
from engine.models import CriticReview, Script

pytest_plugins = ["graph_fakes"]  # sqlite_db, graph_env, fake_llm, ... fixture'lari


def _config() -> dict:
    return {"configurable": {"thread_id": uuid.uuid4().hex}}


async def test_loop_rewrites_until_pass(graph_env, fakes):
    fake = graph_env["llm"]
    fake.scores = [6, 9]
    graph = compile_graph()
    cfg = _config()
    await graph.ainvoke(fakes.initial_state(graph_env["workspace_id"]), cfg)
    values = (await graph.aget_state(cfg)).values

    assert fake.writer_calls == 2
    # 0-iteratsiya draft tier, keyingisi critic tier (docs/04)
    assert [t for n, t in fake.calls if n == "writer"] == ["draft", "critic"]
    assert sorted(n for n, _ in fake.calls if n in ("uz", "brand", "hook")) == \
        ["brand", "brand", "hook", "hook", "uz", "uz"]
    assert values["iteration"] == 2
    assert values["best_score"] == 9
    assert values["script"]["body"].endswith("Versiya 2.")
    assert values["best_hook_idx"] == 1
    assert len(values["reviews"]) == 3  # faqat joriy iteratsiya
    assert len(values["review_history"]) == 6
    assert not values.get("errors")
    # asset_gen'ga o'tdi va approval'da to'xtadi
    assert values["props"]["scenes"]
    assert (await graph.aget_state(cfg)).next == ("approval",)

    async with graph_env["db"]() as s:
        rows = (await s.execute(select(CriticReview))).scalars().all()
        assert len(rows) == 6
        script = await s.get(Script, uuid.UUID(values["script_id"]))
        assert script.status == "ready"
        assert script.score == 9
        assert script.iteration == 2
        assert script.hook_variants["selected"] == 1


async def test_max_three_iterations_keeps_best(graph_env, fakes):
    fake = graph_env["llm"]
    fake.scores = [5, {"uz": 7, "brand": 9, "hook": 8}, 6]
    graph = compile_graph()
    cfg = _config()
    await graph.ainvoke(fakes.initial_state(graph_env["workspace_id"]), cfg)
    values = (await graph.aget_state(cfg)).values

    assert fake.writer_calls == 3
    assert values["iteration"] == 3
    assert values["best_score"] == 7
    assert values["script"]["body"].endswith("Versiya 2.")  # eng yaxshisi — 2-versiya
    assert values["best_script"] == values["script"]
    assert values["errors"] and "3 iteratsiyada" in values["errors"][0]
    assert {r["critic"]: r["score"] for r in values["best_reviews"]} == \
        {"uz": 7, "brand": 9, "hook": 8}
    assert (await graph.aget_state(cfg)).next == ("approval",)

    async with graph_env["db"]() as s:
        script = await s.get(Script, uuid.UUID(values["script_id"]))
        assert script.body.endswith("Versiya 2.")
        assert script.score == 7


def test_route_after_critics():
    ok = [{"score": 8}, {"score": 9}, {"score": 10}]
    low = [{"score": 8}, {"score": 7}, {"score": 10}]
    assert route_after_critics({"reviews": ok, "iteration": 1}) == "asset_gen"
    assert route_after_critics({"reviews": low, "iteration": 1}) == "writer"
    assert route_after_critics({"reviews": low, "iteration": 3}) == "asset_gen"
    assert route_after_critics({"reviews": [], "iteration": 0}) == "writer"


def test_merge_reviews_reset_and_append():
    assert merge_reviews([{"score": 1}], None) == []
    assert merge_reviews([{"score": 1}], [{"score": 2}]) == [{"score": 1}, {"score": 2}]
    assert merge_reviews(None, [{"score": 2}]) == [{"score": 2}]


def test_validate_script_normalizes_and_rejects_bad(fakes):
    from pydantic import ValidationError

    script_json = fakes.script_json

    s = validate_script(script_json(1))
    assert len(s["hooks"]) == 3 and len(s["scenes"]) == 3
    bad = script_json(1)
    bad["scenes"][0]["duration_s"] = 12
    try:
        validate_script(bad)
    except ValidationError:
        pass
    else:
        raise AssertionError("duration_s 12 o'tib ketdi")
    bad = script_json(1)
    bad["hooks"] = bad["hooks"][:2]
    try:
        validate_script(bad)
    except ValidationError:
        pass
    else:
        raise AssertionError("2 hook o'tib ketdi")


def test_validate_script_accepts_motion_fields(fakes):
    script_json = fakes.script_json
    data = script_json(1)
    data["style"] = "hype"
    data["hook_text"] = "Bugun *50%* chegirma"
    data["caption_preset"] = "boxHighlight"
    data["scenes"][0]["title"] = "Nega *achchiq*?"
    data["scenes"][0]["text_anim"] = "WordPop"
    data["scenes"][0]["transition"] = "zoomPunch"
    data["scenes"][0]["fx"] = ["shake"]
    data["scenes"][0]["ken_burns"] = "in"

    s = validate_script(data)
    assert s["style"] == "hype"
    assert s["hook_text"] == "Bugun *50%* chegirma"
    assert s["caption_preset"] == "boxHighlight"
    sc0 = s["scenes"][0]
    assert sc0["title"] == "Nega *achchiq*?"
    assert sc0["text_anim"] == "WordPop"
    assert sc0["transition"] == "zoomPunch"
    assert sc0["fx"] == ["shake"]
    assert sc0["ken_burns"] == "in"


def test_validate_script_unknown_motion_enum_becomes_none(fakes):
    script_json = fakes.script_json
    data = script_json(1)
    data["style"] = "cyberpunk"  # noma'lum
    data["caption_preset"] = "neonGlow"  # noma'lum
    data["scenes"][0]["text_anim"] = "SuperZoom"  # noma'lum
    data["scenes"][0]["transition"] = "teleport"  # noma'lum
    data["scenes"][0]["ken_burns"] = "diagonal"  # noma'lum

    s = validate_script(data)
    assert s["style"] is None
    assert s["caption_preset"] is None
    sc0 = s["scenes"][0]
    assert sc0["text_anim"] is None
    assert sc0["transition"] is None
    assert sc0["ken_burns"] is None


def test_validate_script_missing_motion_fields_default_to_none(fakes):
    """Eski (docs/11'dan oldingi) ssenariylar hali ham yaroqli bo'lishi kerak."""
    s = validate_script(fakes.script_json(1))
    assert s["style"] is None
    assert s["hook_text"] is None
    assert s["caption_preset"] is None
    for sc in s["scenes"]:
        assert sc["title"] is None
        assert sc["text_anim"] is None
        assert sc["transition"] is None
        assert sc["fx"] == []
        assert sc["ken_burns"] is None


def test_apply_default_motion_fills_all_fields(fakes):
    script = validate_script(fakes.script_json(1))
    out = apply_default_motion(script, {}, best_hook_idx=1)

    assert out["style"] == "bold"
    # hooks[1] == "3 ta xato" -> birinchi 6 so'zi, eng uzuni "xato" yulduzchada
    assert out["hook_text"] == "3 ta *xato*"
    n = len(out["scenes"])
    assert out["scenes"][0]["text_anim"] == "WordPop"
    assert out["scenes"][-1]["text_anim"] == "BounceIn"
    # scene 1 (index 1) raqam saqlaydi ("15% chegirma") -> Counter
    assert out["scenes"][1]["text_anim"] == "Counter"
    assert [sc["transition"] for sc in out["scenes"]] == \
        ["zoomPunch" if i == 1 else "fade" for i in range(n)]
    assert [sc["ken_burns"] for sc in out["scenes"]] == ["in", "out", "left"][:n]


def test_apply_default_motion_uses_brand_style_and_keeps_llm_values():
    script = {
        "hooks": ["a", "b", "c"],
        "scenes": [
            {"subtitle": "x", "text_anim": "Glitch", "transition": None, "ken_burns": None},
            {"subtitle": "y"},
            {"subtitle": "z"},
        ],
        "style": None,
        "hook_text": "Allaqachon *tayyor*",
        "caption_preset": None,
    }
    out = apply_default_motion(script, {"style": "luxury"}, best_hook_idx=0)
    assert out["style"] == "luxury"
    assert out["hook_text"] == "Allaqachon *tayyor*"  # LLM qiymati saqlandi, qayta hisoblanmadi
    assert out["scenes"][0]["text_anim"] == "Glitch"  # LLM qiymati ustuvor


def test_previous_reviews_text():
    assert "birinchi iteratsiya" in format_previous_reviews({})
    text = format_previous_reviews({
        "script": {"hooks": ["a"]},
        "reviews": [{"critic": "uz", "score": 6, "reasons": ["kalka"], "fixes": ["X → Y"]}],
    })
    assert "UzCritic: 6/10" in text and "X → Y" in text


def test_split_words_by_scenes():
    words = [{"w": f"w{i}", "start": i * 1.0, "end": i * 1.0 + 0.8} for i in range(10)]
    durations = fit_scene_durations([4, 4, 2], 10.0)
    assert durations == [4.0, 4.0, 2.0]
    parts = split_words_by_scenes(words, durations)
    assert [len(p) for p in parts] == [4, 4, 2]
    assert parts[1][0]["w"] == "w4" and parts[1][0]["start"] == 4.0  # vaqtlar absolyut
    # davomiylik ovozga moslanadi, nisbat saqlanadi
    assert fit_scene_durations([4, 4], 6.0) == [3.0, 3.0]
    assert split_words_by_scenes([], [1.0]) == [[]]
    # oxirgi chegaradan keyingi so'zlar — oxirgi sahnaga
    assert len(split_words_by_scenes(words, [1.0, 1.0])[1]) == 9
