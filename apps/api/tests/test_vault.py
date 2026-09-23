"""Vault: parser, indekslovchi, qidiruv, graf, promptga yuklash, HTTP/WS API testlari.

docs/10-obsidian-vault.md + roadmap 3.6-3.7. Postgres'siz (sqlite + aiosqlite),
haqiqiy ``vault/`` namunalarining ``tmp_path`` nusxasi ustida ishlaydi.
"""

from __future__ import annotations

import datetime
import shutil
from pathlib import Path

import fakeredis
import httpx
import pytest
import pytest_asyncio
from fastapi import FastAPI
from sqlalchemy.ext.asyncio import async_sessionmaker, create_async_engine
from starlette.testclient import TestClient

from engine import jobs
from engine.api import vault_routes
from engine.db import get_session, init_models
from engine.vault import embeddings, indexer, parser

REPO_VAULT = Path(__file__).resolve().parents[3] / "vault"

EXPECTED_PATHS = {
    "brand/faq.md",
    "brand/forbidden.md",
    "brand/profile.md",
    "content/references/example.md",
    "jarvis/sop/escalation.md",
    "jarvis/sop/first-message.md",
    "jarvis/sop/pricing.md",
    "jarvis/staff/aziz.md",
}


@pytest.fixture(autouse=True)
def _fake_redis_for_vault_bus():
    """``VaultBus`` Redis'ga ``engine.jobs.get_redis()`` orqali "best effort" yozadi —
    testlarda haqiqiy tarmoqqa chiqmasin."""
    jobs.set_redis(fakeredis.FakeAsyncRedis(decode_responses=True))
    yield
    jobs.set_redis(None)


@pytest.fixture
def tmp_vault(tmp_path) -> Path:
    dest = tmp_path / "vault"
    shutil.copytree(REPO_VAULT, dest)
    return dest


@pytest_asyncio.fixture
async def sqlite_session_factory():
    engine = create_async_engine("sqlite+aiosqlite:///:memory:")
    await init_models(bind=engine)
    factory = async_sessionmaker(engine, expire_on_commit=False)
    yield factory
    await engine.dispose()


# ------------------------------------------------------------------------- parser


def test_parse_frontmatter_tags_and_wikilinks():
    text = (
        "---\n"
        "type: sop\n"
        "tags: [jarvis/sop, pricing]\n"
        "updated: 2026-09-24\n"
        "---\n"
        "# Narx so'ralsa\n"
        "Ma'lumot #tag1 va #jarvis/sop yana bir bor.\n"
        "Qarang: [[first-message|birinchi xabar]] va [[pricing#bo'lim]].\n"
    )
    parsed = parser.parse(text, fallback_title="pricing")

    assert parsed.frontmatter["type"] == "sop"
    assert parsed.frontmatter["updated"] == "2026-09-24"  # yaml date -> JSON-safe str
    assert parsed.title == "Narx so'ralsa"
    assert parsed.tags[:2] == ["jarvis/sop", "pricing"]  # frontmatter ro'yxati, tartib saqlanadi
    assert "tag1" in parsed.tags  # inline #tag
    assert parsed.wikilinks == ["first-message", "pricing"]  # |alias va #heading olib tashlangan


def test_parse_fallback_title_when_no_h1():
    parsed = parser.parse("Bu yerda sarlavha yo'q, faqat matn.", fallback_title="my-note")
    assert parsed.title == "my-note"
    assert parsed.frontmatter == {}
    assert parsed.wikilinks == []


def test_parse_tags_string_frontmatter_and_dedup():
    text = "---\ntags: brand/profile\n---\n# Sarlavha\n#brand/profile takroriy tag emas.\n"
    parsed = parser.parse(text, fallback_title="x")
    assert parsed.tags == ["brand/profile"]


def test_chunk_short_text_returns_single_chunk():
    assert parser.chunk("qisqa matn", max_chars=1200) == ["qisqa matn"]


def test_chunk_empty_text_returns_no_chunks():
    assert parser.chunk("   \n\n  ", max_chars=1200) == []


def test_chunk_respects_max_chars_on_long_text():
    paragraph = "so'z " * 400  # ~2000 belgi, bitta paragraf ichida bo'linadi
    text = "Kirish.\n\n" + paragraph + "\n\nYakun."
    chunks = parser.chunk(text, max_chars=200)
    assert len(chunks) > 1
    assert all(len(c) <= 200 for c in chunks)


# ------------------------------------------------------------------------- embeddings


async def test_hash_embed_deterministic_and_l2_normalized():
    vecs = await embeddings.embed(["salom dunyo, bu test matni"])
    assert len(vecs) == 1
    assert len(vecs[0]) == embeddings.DIM
    norm = sum(x * x for x in vecs[0]) ** 0.5
    assert norm == pytest.approx(1.0, abs=1e-6)

    vecs2 = await embeddings.embed(["salom dunyo, bu test matni"])
    assert vecs == vecs2  # deterministik


async def test_cosine_self_similarity_is_one_and_orthogonal_is_low():
    v1 = (await embeddings.embed(["mutlaqo boshqa mavzu haqida"]))[0]
    v2 = (await embeddings.embed(["narx narx narx narx narx"]))[0]
    assert embeddings.cosine(v1, v1) == pytest.approx(1.0, abs=1e-6)
    assert embeddings.cosine(v1, v2) < 0.5


async def test_embed_empty_list_returns_empty():
    assert await embeddings.embed([]) == []


# ------------------------------------------------------------------------- reindex


async def test_reindex_add_then_unchanged_then_update_then_remove(
    tmp_vault, sqlite_session_factory
):
    events: list[tuple[str, str]] = []

    def on_event(payload):
        events.append((payload["event"], payload["node"]["path"]))

    report1 = await indexer.reindex(sqlite_session_factory, tmp_vault, on_event=on_event)
    assert report1.added == 8
    assert (report1.updated, report1.removed, report1.unchanged) == (0, 0, 0)
    assert {p for e, p in events if e == "added"} == EXPECTED_PATHS
    assert len(events) == 8  # har fayl uchun faqat bitta hodisa

    # 2) o'zgarishsiz qayta indekslash — hech qanday hodisa yo'q
    events.clear()
    report2 = await indexer.reindex(sqlite_session_factory, tmp_vault, on_event=on_event)
    assert (report2.added, report2.updated, report2.removed) == (0, 0, 0)
    assert report2.unchanged == 8
    assert events == []

    # 3) bitta faylni tahrirlash — faqat shu fayl uchun "updated"
    faq_path = tmp_vault / "brand" / "faq.md"
    faq_path.write_text(faq_path.read_text(encoding="utf-8") + "\nYana bir qator.\n")
    events.clear()
    report3 = await indexer.reindex(sqlite_session_factory, tmp_vault, on_event=on_event)
    assert report3.updated == 1
    assert report3.unchanged == 7
    assert events == [("updated", "brand/faq.md")]

    # 4) faylni o'chirish — faqat shu fayl uchun "removed"
    (tmp_vault / "jarvis" / "staff" / "aziz.md").unlink()
    events.clear()
    report4 = await indexer.reindex(sqlite_session_factory, tmp_vault, on_event=on_event)
    assert report4.removed == 1
    assert report4.unchanged == 7
    assert events == [("removed", "jarvis/staff/aziz.md")]

    async with sqlite_session_factory() as session:
        from sqlalchemy import func, select

        from engine.models.vault import VaultNote

        count = (await session.execute(select(func.count(VaultNote.id)))).scalar_one()
        assert count == 7


async def test_reindex_skips_templates_and_root_readme(tmp_vault, sqlite_session_factory):
    report = await indexer.reindex(sqlite_session_factory, tmp_vault)
    assert report.added == 8  # templates/script.md va README.md kirmaydi


async def test_reindex_force_reembeds_unchanged_file(tmp_vault, sqlite_session_factory):
    await indexer.reindex(sqlite_session_factory, tmp_vault)
    report = await indexer.reindex(sqlite_session_factory, tmp_vault, force=True)
    assert report.updated == 8
    assert report.unchanged == 0


async def test_scan_empty_dir_returns_empty_list(tmp_path):
    assert indexer.scan(tmp_path / "does-not-exist") == []


# ------------------------------------------------------------------------- search


async def test_search_returns_faq_note_for_narx(tmp_vault, sqlite_session_factory):
    await indexer.reindex(sqlite_session_factory, tmp_vault)
    async with sqlite_session_factory() as session:
        results = await indexer.search(session, "narx", k=3)
    assert results
    assert results[0].path == "brand/faq.md"


async def test_search_filters_by_type(tmp_vault, sqlite_session_factory):
    await indexer.reindex(sqlite_session_factory, tmp_vault)
    async with sqlite_session_factory() as session:
        results = await indexer.search(session, "narx", types=["sop"], k=5)
    assert results
    assert all(r.type == "sop" for r in results)
    assert "jarvis/sop/pricing.md" in {r.path for r in results}


async def test_search_empty_query_returns_up_to_k_rows(tmp_vault, sqlite_session_factory):
    await indexer.reindex(sqlite_session_factory, tmp_vault)
    async with sqlite_session_factory() as session:
        results = await indexer.search(session, "", k=4)
    assert len(results) == 4


# ------------------------------------------------------------------------- graph_snapshot


async def test_graph_snapshot_nodes_and_links(tmp_vault, sqlite_session_factory):
    await indexer.reindex(sqlite_session_factory, tmp_vault)
    async with sqlite_session_factory() as session:
        snap = await indexer.graph_snapshot(session)

    assert len(snap["nodes"]) == 8
    assert {n["path"] for n in snap["nodes"]} == EXPECTED_PATHS

    link_pairs = {(link["source"], link["target"]) for link in snap["links"]}
    assert ("brand/faq.md", "jarvis/sop/pricing.md") in link_pairs
    assert ("jarvis/sop/pricing.md", "jarvis/sop/first-message.md") in link_pairs


# ------------------------------------------------------------------------- load_for_prompt


async def test_load_for_prompt_contains_sop_text(tmp_vault, sqlite_session_factory):
    await indexer.reindex(sqlite_session_factory, tmp_vault)
    async with sqlite_session_factory() as session:
        text = await indexer.load_for_prompt(session, types=("brand", "sop"), max_chars=6000)
    assert "Narx so'ralsa" in text
    assert "jarvis/sop/pricing.md" in text


async def test_load_for_prompt_respects_max_chars(tmp_vault, sqlite_session_factory):
    await indexer.reindex(sqlite_session_factory, tmp_vault)
    async with sqlite_session_factory() as session:
        text = await indexer.load_for_prompt(session, types=("brand", "sop"), max_chars=80)
    assert len(text) <= 80


# ------------------------------------------------------------------------- write_report


def test_write_report_creates_file_with_frontmatter(tmp_vault):
    out = indexer.write_report(tmp_vault, datetime.date(2026, 9, 24), "Bugun 3 ta lid keldi.")
    assert out.name == "2026-09-24.md"
    content = out.read_text(encoding="utf-8")
    assert content.startswith("---\ntype: report")
    assert "Bugun 3 ta lid keldi." in content


# ------------------------------------------------------------------------- HTTP routes


def _build_app(sqlite_session_factory) -> FastAPI:
    app = FastAPI()
    app.include_router(vault_routes.router)

    async def _session():
        async with sqlite_session_factory() as session:
            yield session

    app.dependency_overrides[get_session] = _session
    app.dependency_overrides[vault_routes.get_session_factory] = lambda: sqlite_session_factory
    return app


@pytest_asyncio.fixture
async def api_client(tmp_vault, sqlite_session_factory, monkeypatch):
    monkeypatch.setattr(vault_routes.settings, "vault_dir", str(tmp_vault))
    app = _build_app(sqlite_session_factory)
    transport = httpx.ASGITransport(app=app)
    async with httpx.AsyncClient(transport=transport, base_url="http://vault-test") as client:
        yield client


async def test_route_reindex_then_graph_json(api_client):
    r = await api_client.post("/v1/vault/reindex")
    assert r.status_code == 200
    assert r.json() == {"added": 8, "updated": 0, "removed": 0, "unchanged": 0}

    r2 = await api_client.get("/v1/vault/graph")
    assert r2.status_code == 200
    data = r2.json()
    assert len(data["nodes"]) == 8
    assert any(
        link["source"] == "brand/faq.md" and link["target"] == "jarvis/sop/pricing.md"
        for link in data["links"]
    )


async def test_route_notes_detail_and_404(api_client):
    await api_client.post("/v1/vault/reindex")

    r = await api_client.get("/v1/vault/notes/brand/faq.md")
    assert r.status_code == 200
    note = r.json()
    assert note["type"] == "brand"
    assert note["path"] == "brand/faq.md"
    assert "Narx" in note["markdown"]
    assert "jarvis/sop/pricing.md" in note["links"]

    r404 = await api_client.get("/v1/vault/notes/does/not/exist.md")
    assert r404.status_code == 404


async def test_route_search(api_client):
    await api_client.post("/v1/vault/reindex")
    r = await api_client.get("/v1/vault/search", params={"q": "narx", "k": 3})
    assert r.status_code == 200
    results = r.json()
    assert results[0]["path"] == "brand/faq.md"


async def test_route_graph_html_and_static_assets(api_client):
    r = await api_client.get("/vault/graph")
    assert r.status_code == 200
    assert "text/html" in r.headers["content-type"]
    assert "graph.js" in r.text

    r_js = await api_client.get("/vault/static/graph.js")
    assert r_js.status_code == 200
    assert "application/javascript" in r_js.headers["content-type"]

    r_css = await api_client.get("/vault/static/graph.css")
    assert r_css.status_code == 200
    assert "text/css" in r_css.headers["content-type"]

    r_missing = await api_client.get("/vault/static/nope.js")
    assert r_missing.status_code == 404

    r_traversal = await api_client.get("/vault/static/..")
    assert r_traversal.status_code == 404


# ------------------------------------------------------------------------- WebSocket


def test_websocket_snapshot_then_event_after_reindex(tmp_vault, sqlite_session_factory, monkeypatch):
    monkeypatch.setattr(vault_routes.settings, "vault_dir", str(tmp_vault))
    app = _build_app(sqlite_session_factory)

    with TestClient(app) as client, client.websocket_connect("/ws/vault") as ws:
        snapshot = ws.receive_json()
        assert snapshot["event"] == "snapshot"
        assert snapshot["nodes"] == []
        assert snapshot["links"] == []

        resp = client.post("/v1/vault/reindex")
        assert resp.status_code == 200
        assert resp.json()["added"] == 8

        received = [ws.receive_json() for _ in range(8)]
        assert all(payload["event"] == "added" for payload in received)
        assert {payload["node"]["path"] for payload in received} == EXPECTED_PATHS
