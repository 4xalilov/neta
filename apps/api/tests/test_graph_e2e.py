"""Brif → ... → approval interrupt → resume (approve/schedule/reject) va arq worker oqimi."""
from __future__ import annotations

import json
import uuid

import fakeredis
import pytest
from langgraph.types import Command
from sqlalchemy import select

from engine import jobs, worker
from engine.graphs import day_subgraph
from engine.graphs.day_subgraph import compile_graph
from engine.models import Asset, RenderJob, Script, TasteMemory

pytest_plugins = ["graph_fakes"]  # sqlite_db, graph_env, fake_llm, ... fixture'lari


def _config() -> dict:
    return {"configurable": {"thread_id": uuid.uuid4().hex}}


async def _run_to_interrupt(graph_env):
    fakes = graph_env["fakes"]
    graph = compile_graph()
    cfg = _config()
    out = await graph.ainvoke(fakes.initial_state(graph_env["workspace_id"]), cfg)
    return graph, cfg, out


async def test_brief_until_interrupt_has_remotion_props(graph_env):
    graph, cfg, out = await _run_to_interrupt(graph_env)
    snap = await graph.aget_state(cfg)
    assert snap.next == ("approval",)
    intr = snap.tasks[0].interrupts[0].value
    assert out["__interrupt__"][0].value == intr

    values = snap.values
    props = values["props"]
    assert set(props) == {"audioUrl", "cta", "scenes", "brand", "style", "hookText",
                          "captionPreset"}
    assert props["audioUrl"].startswith("http://localhost:9000/assets/ws/")
    assert props["audioUrl"].endswith(".mp3")
    assert props["cta"] == "Obuna bo'ling!"
    assert props["brand"] == {"font": "Plus Jakarta Sans", "accent": "#FACC15", "bg": "#0B0F19"}
    # motion-dizayn: writer bo'sh qoldirgan maydonlar apply_default_motion bilan to'ldirildi
    # (brand_profile'da "style" yo'q -> "bold"; hookText = hooks[best_hook_idx] birinchi 6 so'zi,
    # eng uzun so'zi yulduzchada; hook_critic fake har doim best_hook_idx=1 qaytaradi -> "3 ta xato")
    assert props["style"] == "bold"
    assert props["hookText"] == "3 ta *xato*"
    assert props["captionPreset"] is None
    assert len(props["scenes"]) == 3
    assert [sc["textAnim"] for sc in props["scenes"]] == ["WordPop", "Counter", "BounceIn"]
    assert [sc["transition"] for sc in props["scenes"]] == ["fade", "zoomPunch", "fade"]
    assert [sc["kenBurns"] for sc in props["scenes"]] == ["in", "out", "left"]
    total_words = 0
    for sc in props["scenes"]:
        assert set(sc) >= {"imageUrl", "durationS", "words", "subtitle", "title", "textAnim",
                           "transition", "fx", "kenBurns"}
        assert "depthUrl" not in sc
        assert sc["imageUrl"].startswith("http://localhost:9000/assets/")
        assert 0 < sc["durationS"]
        for w in sc["words"]:
            assert set(w) == {"w", "start", "end"}
        total_words += len(sc["words"])
    display_words = values["script"]["display_text"].split()
    assert total_words == len(display_words)
    assert "15%" in [w["w"] for sc in props["scenes"] for w in sc["words"]]
    assert sum(sc["durationS"] for sc in props["scenes"]) == pytest.approx(6.5, abs=0.01)
    assert values["composition"] == "ReelsBasic"

    # BullMQ job formati
    queue = graph_env["queue"]
    [(job_id, data)] = queue.jobs.items()
    assert set(data) == {"jobId", "workspaceId", "composition", "props", "outputKey"}
    assert data["jobId"] == job_id == values["render_job_id"]
    assert data["workspaceId"] == graph_env["workspace_id"]
    assert data["outputKey"].startswith(f"ws/{graph_env['workspace_id']}/video/")
    assert data["outputKey"].endswith(".mp4")
    assert values["video_uri"] == f"s3://assets/{data['outputKey']}"

    # interrupt payload — Telegram video tasdiq ekrani uchun
    assert intr["script_id"] == values["script_id"]
    assert intr["video_url"] == values["video_url"]
    assert intr["hooks"] == values["script"]["hooks"]
    assert intr["scores"] == {"uz": 9, "brand": 9, "hook": 9}
    assert intr["cost_usd"] > 0
    assert intr["vision_qa"] == {"pass": True, "issues": []}

    async with graph_env["db"]() as s:
        rj = await s.get(RenderJob, uuid.UUID(job_id))
        assert rj.status == "done" and rj.video_uri == values["video_uri"]
        kinds = sorted(a.kind for a in (await s.execute(select(Asset))).scalars())
        assert kinds == ["audio", "image", "image", "image", "video"]


async def test_resume_approve_publishes(graph_env):
    graph, cfg, _ = await _run_to_interrupt(graph_env)
    out = await graph.ainvoke(Command(resume={"decision": "approve", "hook_idx": 2}), cfg)
    assert out["publish_status"] == "approved"
    assert out["selected_hook_idx"] == 2
    assert (await graph.aget_state(cfg)).next == ()
    async with graph_env["db"]() as s:
        script = await s.get(Script, uuid.UUID(out["script_id"]))
        assert script.status == "approved"
        assert script.hook_variants["selected"] == 2
        taste = (await s.execute(select(TasteMemory))).scalars().all()
        assert [t.kind for t in taste] == ["approved"]


async def test_resume_schedule(graph_env):
    graph, cfg, _ = await _run_to_interrupt(graph_env)
    out = await graph.ainvoke(Command(resume={"decision": "schedule"}), cfg)
    assert out["publish_status"] == "scheduled"
    async with graph_env["db"]() as s:
        script = await s.get(Script, uuid.UUID(out["script_id"]))
        assert script.status == "scheduled"


async def test_resume_reject_writes_taste_memory(graph_env):
    graph, cfg, _ = await _run_to_interrupt(graph_env)
    out = await graph.ainvoke(
        Command(resume={"decision": "reject", "reason": "juda rasmiy ohang"}), cfg)
    assert out["approved"] is False
    assert out["publish_status"] == "rejected"
    assert (await graph.aget_state(cfg)).next == ()
    async with graph_env["db"]() as s:
        taste = (await s.execute(select(TasteMemory))).scalars().all()
        assert len(taste) == 1
        assert taste[0].kind == "rejected"
        assert taste[0].reason == "juda rasmiy ohang"
        assert str(taste[0].workspace_id) == graph_env["workspace_id"]
        script = await s.get(Script, uuid.UUID(out["script_id"]))
        assert script.status == "rejected"


async def test_parallax_uses_depth_maps(graph_env, fakes, monkeypatch):
    from engine.integrations import images

    async def fake_depth(url, *, workspace_id=""):
        return images.DepthResult(uri=f"s3://assets/ws/{workspace_id}/depth/x.png",
                                  url="https://fal.test/d.png", usd=0.01)

    monkeypatch.setattr(images, "depth_map", fake_depth)
    graph = compile_graph()
    cfg = _config()
    await graph.ainvoke(fakes.initial_state(graph_env["workspace_id"],
                                      plan_item={"parallax": True}), cfg)
    values = (await graph.aget_state(cfg)).values
    assert values["composition"] == "ReelsParallax"
    assert all(sc["depthUrl"].endswith("/depth/x.png") for sc in values["props"]["scenes"])


async def test_render_failure_raises(graph_env, fakes):
    graph_env["queue"].fail = True
    graph = compile_graph()
    with pytest.raises(RuntimeError, match="muvaffaqiyatsiz"):
        await graph.ainvoke(fakes.initial_state(graph_env["workspace_id"]), _config())
    async with graph_env["db"]() as s:
        rj = (await s.execute(select(RenderJob))).scalar_one()
        assert rj.status == "failed"


# ---------------------------------------------------------------- arq worker


@pytest.fixture
async def worker_env(graph_env, monkeypatch):
    redis = fakeredis.FakeAsyncRedis(decode_responses=True)
    jobs.set_redis(redis)
    sent: list[dict] = []
    real_notify = jobs.notify

    async def capture(chat_id, kind, payload):
        sent.append({"chat_id": chat_id, "kind": kind, "payload": payload})
        await real_notify(chat_id, kind, payload)

    monkeypatch.setattr(jobs, "notify", capture)
    await day_subgraph.close_graph()
    yield {**graph_env, "redis": redis, "sent": sent}
    await day_subgraph.close_graph()
    jobs.set_redis(None)


async def test_worker_run_and_resume(worker_env):
    ws = worker_env["workspace_id"]
    job_id = uuid.uuid4().hex
    await jobs.create(job_id, workspace_id=ws, chat_id=42)
    pubsub = worker_env["redis"].pubsub()
    await pubsub.subscribe(jobs.NOTIFY_CHANNEL)

    res = await worker.run_brief({}, ws, "15% chegirma haqida", job_id)
    assert res == {"status": "done", "stage": "awaiting_approval"}
    job = await jobs.get(job_id)
    assert job["status"] == "done" and job["stage"] == "awaiting_approval"
    assert job["progress"] == 100 and job["script_id"] and job["video_url"]
    assert await jobs.job_for_script(job["script_id"]) == job_id

    kinds = [m["kind"] for m in worker_env["sent"]]
    assert kinds == ["script", "video"]
    script_msg, video_msg = worker_env["sent"]
    assert script_msg["chat_id"] == 42
    sp = script_msg["payload"]
    assert sp["script_id"] == job["script_id"] and len(sp["hooks"]) == 3
    assert sp["selected_idx"] == 1
    assert (sp["uz_score"], sp["brand_score"], sp["hook_score"]) == (9, 9, 9)
    vp = video_msg["payload"]
    assert vp["script_id"] == job["script_id"] and vp["video_url"] == job["video_url"]
    assert vp["vision_qa"] == "OK ✅" and float(vp["cost"]) >= 0 and vp["duration"] == 6

    # tg:notify kanalidagi JSON — bot formati
    msg = None
    for _ in range(5):
        msg = await pubsub.get_message(ignore_subscribe_messages=True, timeout=0.2)
        if msg is not None:
            break
    data = json.loads(msg["data"])
    assert set(data) == {"chat_id", "kind", "payload"} and data["kind"] == "script"
    await pubsub.aclose()

    res = await worker.resume_brief({}, job_id, {"decision": "approve", "hook_idx": 0})
    assert res == {"status": "done", "stage": "published"}
    assert (await jobs.get(job_id))["stage"] == "published"
    # ikkinchi resume — no-op
    assert (await worker.resume_brief({}, job_id, {"decision": "approve"}))["status"] == "noop"


async def test_worker_pending_reject_applied_at_interrupt(worker_env):
    ws = worker_env["workspace_id"]
    job_id = uuid.uuid4().hex
    await jobs.create(job_id, workspace_id=ws, chat_id=42)
    await jobs.set_pending_decision(job_id, {"decision": "reject", "reason": "yoqmadi"})
    res = await worker.run_brief({}, ws, "brif", job_id)
    assert res["stage"] == "rejected"
    async with worker_env["db"]() as s:
        taste = (await s.execute(select(TasteMemory))).scalar_one()
        assert taste.kind == "rejected" and taste.reason == "yoqmadi"


async def test_worker_error_notifies(worker_env):
    worker_env["queue"].fail = True
    job_id = uuid.uuid4().hex
    await jobs.create(job_id, workspace_id=worker_env["workspace_id"], chat_id=42)
    res = await worker.run_brief({}, worker_env["workspace_id"], "brif", job_id)
    assert res["status"] == "failed"
    job = await jobs.get(job_id)
    assert job["status"] == "failed" and "render" in job["error"]
    assert [m["kind"] for m in worker_env["sent"]] == ["script", "error"]


def test_postgres_conn_string():
    assert day_subgraph.postgres_conn_string("postgresql+asyncpg://u:p@h:5432/d") == \
        "postgresql://u:p@h:5432/d"
    assert day_subgraph.postgres_conn_string("postgresql://u@h/d") == "postgresql://u@h/d"
