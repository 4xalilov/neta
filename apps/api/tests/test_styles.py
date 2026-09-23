"""Uslub bilimlar bazasi testlari (docs/03-roadmap.md 2.8).

Postgres'siz (sqlite + aiosqlite), tarmoqsiz: LLM ``engine.llm.set_fake``,
render CLI ``engine.styles.gate.FakeRenderValidator``, S3 ``moto.mock_aws``.
"""

from __future__ import annotations

import copy
import json
import uuid
from pathlib import Path

import httpx
import pytest
import pytest_asyncio
from fastapi import FastAPI
from moto import mock_aws
from sqlalchemy.ext.asyncio import async_sessionmaker, create_async_engine

from engine import llm
from engine.api import style_routes
from engine.db import get_session, init_models
from engine.integrations import storage
from engine.styles import gate, proposer, registry
from engine.styles import schema as style_schema

# ------------------------------------------------------------------------- fixtures

# apps/render/src/motion/styles/themes.ts "bold" — docs/11-motion-library.md
# "Uslublar" jadvalidagi standart tema (bu yerda qo'lda nusxalangan; zod
# sxemasi bilan sinxronligi test_schema_valid_for_copied_builtin_theme orqali
# tekshiriladi).
BOLD_THEME: dict = {
    "name": "bold",
    "label": "Bold",
    "description": "Standart. Qalin Plus Jakarta 800, sariq highlight, zoom-punch kesimlar.",
    "fonts": {
        "display": {"family": "Plus Jakarta Sans", "weight": 800, "lightWeight": 400,
                     "letterSpacing": -0.02, "charEm": 0.64},
        "body": {"family": "Manrope", "weight": 600, "charEm": 0.56},
    },
    "colors": {
        "bg": "#0B0F19", "surface": "#131A2A", "text": "#E6EAF2", "muted": "#8B95AD",
        "primary": "#6366F1", "accent": "#FACC15", "highlight": "#FACC15",
        "onHighlight": "#0B0F19",
    },
    "captionPreset": "karaoke",
    "captionStyle": {"font": "display", "stroke": 6},
    "defaultTextAnim": "WordPop",
    "secondaryTextAnim": "Highlighter",
    "ctaTextAnim": "BounceIn",
    "defaultTransition": "zoomPunch",
    "transitionFrames": 10,
    "fx": ["grain", "vignette"],
    "fxIntensity": {"grain": 0.07, "vignette": 0.45},
    "background": {"kind": "brand", "colors": ["#6366F1", "#22D3EE"]},
    "headline": {"size": 104, "hookSize": 124, "align": "center", "maxLines": 4, "stroke": 0},
    "card": {"glass": True, "radius": 36},
    "kenBurns": "in",
    "tempo": 1,
    "meta": {
        "family": "bold",
        "mood": ["energetic", "confident"],
        "niches": ["retail", "services", "promo", "universal"],
        "aida": ["attention", "action"],
        "description_uz": "Universal standart: qalin sarlavha, sariq karaoke subtitr.",
        "since": "2026-08",
    },
}


def _variant(name: str, **overrides) -> dict:
    theme = copy.deepcopy(BOLD_THEME)
    theme["name"] = name
    theme.update(overrides)
    return theme


@pytest.fixture(autouse=True)
def _no_leftover_fake():
    yield
    llm.clear_fake()


@pytest_asyncio.fixture(autouse=True)
async def _s3(monkeypatch):
    """``gate.evaluate`` kadrni ``storage.put_bytes`` orqali yozadi — moto bilan mock."""
    monkeypatch.setattr(storage.settings, "s3_endpoint", "")
    monkeypatch.setattr(storage.settings, "s3_bucket", "styles-test")
    with mock_aws():
        await storage.ensure_bucket()
        yield


@pytest_asyncio.fixture
async def sqlite_session_factory():
    engine = create_async_engine("sqlite+aiosqlite:///:memory:")
    await init_models(bind=engine)
    factory = async_sessionmaker(engine, expire_on_commit=False)
    yield factory
    await engine.dispose()


@pytest.fixture(autouse=True)
def _proposer_db(monkeypatch, sqlite_session_factory):
    """``proposer._existing_names``/``_base_theme_json`` sqlite'ga ishlasin (haqiqiy
    ``engine.db.async_session`` postgres'ga ulanishga urinadi)."""
    monkeypatch.setattr(proposer, "async_session", sqlite_session_factory)


def _fake_llm(theme: dict, *, score: int = 9, judge_extra: dict | None = None):
    """tier ``critic`` — tema JSON'ini, tier ``final`` — judge JSON'ini qaytaradi."""

    def handler(tier: str, system: str, user: str):
        if tier == "critic":
            return theme
        if tier == "final":
            return {"score": score, "breakdown": {}, "reasons": ["test"], "fixes": [],
                    **(judge_extra or {})}
        raise AssertionError(f"kutilmagan tier: {tier}")

    return handler


# ------------------------------------------------------------------------- schema

def test_schema_valid_for_copied_builtin_theme():
    assert style_schema.validate_theme(BOLD_THEME) == []


def test_schema_invalid_for_broken_theme():
    broken = copy.deepcopy(BOLD_THEME)
    broken["kenBurns"] = "diagonal"  # enum'da yo'q
    del broken["colors"]["accent"]  # majburiy maydon yo'q

    problems = style_schema.validate_theme(broken)
    assert problems
    assert any("kenBurns" in p for p in problems)


def test_schema_bundled_file_is_valid_json():
    data = json.loads(style_schema.BUNDLED_SCHEMA_PATH.read_text(encoding="utf-8"))
    assert "StyleTheme" in data["title"]


def test_schema_source_falls_back_to_bundled_when_render_dir_missing(tmp_path, monkeypatch):
    monkeypatch.setattr(style_schema.settings, "render_dir", str(tmp_path / "no-such-dir"))
    assert style_schema.schema_source() == style_schema.BUNDLED_SCHEMA_PATH


def test_schema_source_prefers_render_dir_when_present(tmp_path, monkeypatch):
    schemas_dir = tmp_path / "schemas"
    schemas_dir.mkdir()
    custom = schemas_dir / "style-theme.schema.json"
    custom.write_text('{"type": "object"}', encoding="utf-8")
    monkeypatch.setattr(style_schema.settings, "render_dir", str(tmp_path))
    assert style_schema.schema_source() == custom


# ------------------------------------------------------------------------- contrast

def test_contrast_passes_for_bold_theme():
    assert style_schema.check_contrast(BOLD_THEME) == []


def test_contrast_fails_for_low_contrast_pair():
    theme = copy.deepcopy(BOLD_THEME)
    theme["colors"]["text"] = "#0B0F19"  # deyarli fon bilan bir xil
    problems = style_schema.check_contrast(theme)
    assert any("matn/fon" in p for p in problems)


def test_contrast_ratio_black_on_white_is_21():
    assert style_schema.contrast_ratio("#000000", "#FFFFFF") == pytest.approx(21.0, abs=0.05)


def test_contrast_ratio_same_color_is_one():
    assert style_schema.contrast_ratio("#6366F1", "#6366F1") == pytest.approx(1.0, abs=1e-6)


# ------------------------------------------------------------------------- proposer

async def test_propose_returns_schema_valid_theme():
    theme = _variant("sunsetpop", label="Sunset Pop")
    llm.set_fake(_fake_llm(theme))

    result = await proposer.propose("quyosh botishi, iliq ranglar", niche="kafe", mood="issiq")

    assert result["name"] == "sunsetpop"
    assert style_schema.validate_theme(result) == []


async def test_propose_repairs_once_on_schema_error():
    broken = _variant("brokenone")
    del broken["colors"]["accent"]
    fixed = _variant("brokenone")

    calls: list[str] = []

    def handler(tier, system, user):
        calls.append(user)
        return broken if len(calls) == 1 else fixed

    llm.set_fake(handler)
    result = await proposer.propose("test ilhom")

    assert len(calls) == 2
    assert style_schema.validate_theme(result) == []


async def test_propose_from_url_best_effort_on_network_error():
    text = await proposer.propose_from_url("http://does-not-exist.invalid/x")
    assert "does-not-exist.invalid" in text


async def test_propose_from_url_strips_html(monkeypatch):
    class FakeResponse:
        status_code = 200
        content = b"<html><body><script>bad()</script><h1>Salom</h1> Matn</body></html>"

        def raise_for_status(self) -> None:
            return None

    class FakeClient:
        async def __aenter__(self):
            return self

        async def __aexit__(self, *exc):
            return None

        async def get(self, url):
            return FakeResponse()

    monkeypatch.setattr(proposer.httpx, "AsyncClient", lambda **kw: FakeClient())
    text = await proposer.propose_from_url("http://example.test")
    assert "bad()" not in text
    assert "Salom" in text and "Matn" in text


# ------------------------------------------------------------------------- gate

async def test_gate_approves_when_schema_ok_render_ok_and_score_high():
    theme = _variant("approvedtest")
    llm.set_fake(_fake_llm(theme, score=9))
    validator = gate.FakeRenderValidator(ok=True, problems=[])

    result = await gate.evaluate(theme, workspace_id="ws1", validator=validator)

    assert result.ok is True
    assert result.score == 9
    assert result.problems == []
    assert result.still_uri is not None
    assert validator.calls == [theme]


async def test_gate_rejects_when_score_low():
    theme = _variant("lowscoretest")
    llm.set_fake(_fake_llm(theme, score=5))
    validator = gate.FakeRenderValidator(ok=True, problems=[])

    result = await gate.evaluate(theme, validator=validator)

    assert result.ok is False
    assert result.score == 5


async def test_gate_rejects_when_validator_reports_problems():
    theme = _variant("clippedtest")
    llm.set_fake(_fake_llm(theme, score=9))
    validator = gate.FakeRenderValidator(ok=False, problems=["matn kesilgan"])

    result = await gate.evaluate(theme, validator=validator)

    assert result.ok is False
    assert "matn kesilgan" in result.problems
    # validator "ok: false" bo'lsa ham hali kadr bergan bo'lishi mumkin — judge baribir ishlaydi
    assert result.score == 9


async def test_gate_skips_render_and_judge_when_schema_invalid():
    theme = copy.deepcopy(BOLD_THEME)
    theme["name"] = "brokengate"
    del theme["colors"]

    validator = gate.FakeRenderValidator(ok=True, problems=[])
    result = await gate.evaluate(theme, validator=validator)

    assert result.ok is False
    assert result.score is None
    assert result.judge is None
    assert validator.calls == []  # render'gacha yetib bormadi


async def test_gate_reports_unavailable_validator():
    theme = _variant("novalidatortest")

    class MissingCliValidator:
        async def validate(self, theme: dict) -> gate.ValidatorOutcome:
            return gate.ValidatorOutcome(ok=False, problems=["render validator unavailable"])

    result = await gate.evaluate(theme, validator=MissingCliValidator())
    assert result.ok is False
    assert "render validator unavailable" in result.problems
    assert result.score is None  # kadr yo'q — judge ishlamadi


def test_contrast_ratio_used_inside_check_contrast_matches_helper():
    ratio = style_schema.contrast_ratio(BOLD_THEME["colors"]["text"], BOLD_THEME["colors"]["bg"])
    assert ratio >= 4.5


# ------------------------------------------------------------------------- registry

async def test_submit_infers_family_and_creates_candidate(sqlite_session_factory):
    theme = _variant("submittest")
    async with sqlite_session_factory() as session:
        row = await registry.submit(session, theme, source="owner", inspiration="qo'lda")
    assert row.status == "candidate"
    assert row.source == "owner"
    assert row.family == "bold"  # BOLD_THEME'ning aniq nusxasi -> "bold" oilasi


async def test_submit_rejects_duplicate_name(sqlite_session_factory):
    theme = _variant("duptest")
    async with sqlite_session_factory() as session:
        await registry.submit(session, theme, source="owner", inspiration="1")
        with pytest.raises(ValueError, match="allaqachon mavjud"):
            await registry.submit(session, theme, source="owner", inspiration="2")


async def test_run_gate_approves_and_writes_vault_doc(sqlite_session_factory, tmp_path):
    theme = _variant("gateapprove")
    llm.set_fake(_fake_llm(theme, score=9))
    validator = gate.FakeRenderValidator(ok=True, problems=[])

    async with sqlite_session_factory() as session:
        row = await registry.submit(session, theme, source="llm", inspiration="test")
        updated = await registry.run_gate(session, row.id, validator=validator)

    assert updated.status == "approved"
    assert updated.approved_by == "gate"
    assert updated.judge_score == 9
    assert updated.approved_at is not None

    out = await registry.write_vault_doc(updated, tmp_path)
    content = out.read_text(encoding="utf-8")
    assert content.startswith("---\ntype: reference")
    assert "tags: [style/bold]" in content
    assert "# Uslub: Bold" in content  # sarlavha theme.label'dan olinadi


async def test_run_gate_rejects_and_records_problems(sqlite_session_factory):
    theme = _variant("gatereject")
    llm.set_fake(_fake_llm(theme, score=3))
    validator = gate.FakeRenderValidator(ok=True, problems=[])

    async with sqlite_session_factory() as session:
        row = await registry.submit(session, theme, source="llm", inspiration="test")
        updated = await registry.run_gate(session, row.id, validator=validator)

    assert updated.status == "rejected"
    assert updated.approved_by is None


async def test_run_gate_missing_theme_raises(sqlite_session_factory):
    async with sqlite_session_factory() as session:
        with pytest.raises(ValueError, match="topilmadi"):
            await registry.run_gate(session, uuid.uuid4())


async def test_owner_approve_and_reject_override(sqlite_session_factory):
    theme_a = _variant("ownerapprove")
    theme_b = _variant("ownerreject")
    async with sqlite_session_factory() as session:
        row_a = await registry.submit(session, theme_a, source="llm", inspiration="x")
        row_b = await registry.submit(session, theme_b, source="llm", inspiration="y")

        approved = await registry.approve(session, row_a.id, reason="ega yoqtirdi")
        rejected = await registry.reject(session, row_b.id, reason="brendga mos emas")

    assert approved.status == "approved"
    assert approved.approved_by == "owner"
    assert approved.judge_json == {"override_reason": "ega yoqtirdi"}

    assert rejected.status == "rejected"
    assert any("brendga mos emas" in p for p in rejected.problems)


async def test_list_and_get_theme(sqlite_session_factory):
    theme = _variant("listtest")
    async with sqlite_session_factory() as session:
        row = await registry.submit(session, theme, source="owner", inspiration="x")
        await registry.approve(session, row.id)

        approved_only = await registry.list_themes(session, status="approved")
        candidates = await registry.list_themes(session, status="candidate")
        found = await registry.get_theme(session, "listtest")
        missing = await registry.get_theme(session, "does-not-exist")

    assert [t.name for t in approved_only] == ["listtest"]
    assert candidates == []
    assert found is not None and found.name == "listtest"
    assert missing is None


async def test_theme_for_props_only_returns_approved(sqlite_session_factory):
    theme = _variant("propstest")
    async with sqlite_session_factory() as session:
        row = await registry.submit(session, theme, source="owner", inspiration="x")

        assert await registry.theme_for_props(session, "propstest") is None  # hali candidate

        await registry.approve(session, row.id)
        result = await registry.theme_for_props(session, "propstest")

    assert result is not None
    assert result["name"] == "propstest"
    assert result is not theme  # nusxa, referens emas


def _write_builtin_files(tmp_path: Path, names: list[str]) -> Path:
    render_dir = tmp_path / "render"
    themes_dir = render_dir / "src" / "motion" / "styles" / "themes"
    themes_dir.mkdir(parents=True)
    for name in names:
        theme = _variant(name)
        (themes_dir / f"{name}.json").write_text(json.dumps(theme), encoding="utf-8")
    return render_dir


async def test_import_builtin_is_idempotent(sqlite_session_factory, tmp_path):
    render_dir = _write_builtin_files(tmp_path, ["builtinone", "builtintwo"])

    async with sqlite_session_factory() as session:
        first = await registry.import_builtin(session, render_dir)
        second = await registry.import_builtin(session, render_dir)
        rows = await registry.list_themes(session, status="approved")

    assert first == {"found": 2, "added": 2, "updated": 0, "skipped": 0}
    assert second == {"found": 2, "added": 0, "updated": 2, "skipped": 0}
    assert {r.name for r in rows} == {"builtinone", "builtintwo"}
    assert all(r.source == "builtin" and r.status == "approved" for r in rows)


async def test_import_builtin_missing_dir_returns_zero(sqlite_session_factory, tmp_path):
    async with sqlite_session_factory() as session:
        result = await registry.import_builtin(session, tmp_path / "nope")
    assert result == {"found": 0, "added": 0, "updated": 0, "skipped": 0}


async def test_write_vault_doc_creates_markdown_with_frontmatter(sqlite_session_factory, tmp_path):
    theme = _variant("vaultdoctest", label="Vault Doc Test")
    async with sqlite_session_factory() as session:
        row = await registry.submit(session, theme, source="owner", inspiration="qo'lda yaratildi")

    out = await registry.write_vault_doc(row, tmp_path)

    assert out == tmp_path / "styles" / "vaultdoctest.md"
    content = out.read_text(encoding="utf-8")
    assert content.startswith("---\ntype: reference\n")
    assert "tags: [style/bold]" in content
    assert "# Uslub: Vault Doc Test" in content
    assert "candidate" in content
    assert "qo'lda yaratildi" in content


# ------------------------------------------------------------------------- HTTP routes

def _build_app(sqlite_session_factory) -> FastAPI:
    app = FastAPI()
    app.include_router(style_routes.router)

    async def _session():
        async with sqlite_session_factory() as session:
            yield session

    app.dependency_overrides[get_session] = _session
    app.dependency_overrides[style_routes.get_session_factory] = lambda: sqlite_session_factory
    return app


@pytest_asyncio.fixture
async def api_client(sqlite_session_factory, monkeypatch, tmp_path):
    monkeypatch.setattr(style_routes.settings, "vault_dir", str(tmp_path / "vault"))
    app = _build_app(sqlite_session_factory)
    transport = httpx.ASGITransport(app=app)
    async with httpx.AsyncClient(transport=transport, base_url="http://styles-test") as client:
        yield client


async def test_route_propose_then_gate_runs_in_background(api_client, monkeypatch):
    theme = _variant("routepropose")
    llm.set_fake(_fake_llm(theme, score=9))
    # Haqiqiy npm CLI bu muhitda yo'q — darvozaning render bosqichini soxtalashtiramiz,
    # shunda to'liq fon quvuri (propose -> submit -> gate -> approve) sinaladi.
    monkeypatch.setattr(gate, "CliRenderValidator", lambda: gate.FakeRenderValidator(ok=True))

    resp = await api_client.post("/v1/styles/propose", json={"inspiration": "yorqin kayfiyat"})
    assert resp.status_code == 202
    body = resp.json()
    assert body["status"] == "candidate"

    detail = await api_client.get(f"/v1/styles/{body['name']}")
    assert detail.status_code == 200
    data = detail.json()
    assert data["status"] == "approved"  # fon vazifasi javobdan oldin tugagan
    assert data["judge_score"] == 9


async def test_route_propose_requires_inspiration_or_url(api_client):
    resp = await api_client.post("/v1/styles/propose", json={})
    assert resp.status_code == 422


async def test_route_propose_duplicate_name_conflicts(api_client):
    theme = _variant("dupsroute")
    llm.set_fake(_fake_llm(theme, score=9))
    r1 = await api_client.post("/v1/styles/propose", json={"inspiration": "birinchi"})
    assert r1.status_code == 202

    r2 = await api_client.post("/v1/styles/propose", json={"inspiration": "ikkinchi"})
    assert r2.status_code == 409


async def test_route_list_filters_by_status(api_client, sqlite_session_factory):
    theme = _variant("routelist")
    async with sqlite_session_factory() as session:
        row = await registry.submit(session, theme, source="owner", inspiration="x")

    only_approved = await api_client.get("/v1/styles")
    assert only_approved.json() == []

    async with sqlite_session_factory() as session:
        await registry.approve(session, row.id)

    approved_resp = await api_client.get("/v1/styles")
    assert [s["name"] for s in approved_resp.json()] == ["routelist"]

    candidates_resp = await api_client.get("/v1/styles", params={"status": "candidate"})
    assert candidates_resp.json() == []  # allaqachon approved bo'lib qoldi


async def test_route_get_style_404(api_client):
    resp = await api_client.get("/v1/styles/does-not-exist")
    assert resp.status_code == 404


async def test_route_manual_gate_and_approve_reject(api_client, sqlite_session_factory):
    theme = _variant("routegate")
    async with sqlite_session_factory() as session:
        row = await registry.submit(session, theme, source="owner", inspiration="x")

    llm.set_fake(_fake_llm(theme, score=3))
    gate_resp = await api_client.post(f"/v1/styles/{row.id}/gate")
    assert gate_resp.status_code == 200
    assert gate_resp.json()["status"] == "rejected"

    approve_resp = await api_client.post(
        f"/v1/styles/{row.id}/approve", json={"reason": "ega qo'lda tasdiqladi"}
    )
    assert approve_resp.status_code == 200
    assert approve_resp.json()["status"] == "approved"
    assert approve_resp.json()["approved_by"] == "owner"

    reject_resp = await api_client.post(
        f"/v1/styles/{row.id}/reject", json={"reason": "fikr o'zgardi"}
    )
    assert reject_resp.status_code == 200
    assert reject_resp.json()["status"] == "rejected"


async def test_route_approve_missing_id_404(api_client):
    resp = await api_client.post(f"/v1/styles/{uuid.uuid4()}/approve", json={})
    assert resp.status_code == 404


async def test_route_import_builtin(api_client, tmp_path, monkeypatch):
    render_dir = _write_builtin_files(tmp_path, ["routebuiltin"])
    monkeypatch.setattr(style_routes.settings, "render_dir", str(render_dir))

    resp = await api_client.post("/v1/styles/import-builtin")
    assert resp.status_code == 200
    assert resp.json() == {"found": 1, "added": 1, "updated": 0, "skipped": 0}

    listed = await api_client.get("/v1/styles")
    assert [s["name"] for s in listed.json()] == ["routebuiltin"]


async def test_route_still_redirects_to_public_url(api_client, sqlite_session_factory):
    theme = _variant("routestill")
    llm.set_fake(_fake_llm(theme, score=9))
    validator = gate.FakeRenderValidator(ok=True, problems=[])

    async with sqlite_session_factory() as session:
        row = await registry.submit(session, theme, source="owner", inspiration="x")
        await registry.run_gate(session, row.id, validator=validator)

    resp = await api_client.get("/v1/styles/routestill/still", follow_redirects=False)
    assert resp.status_code in (302, 307)
    assert resp.headers["location"].startswith(storage.settings.public_s3_url)


async def test_route_still_404_when_no_frame(api_client, sqlite_session_factory):
    theme = _variant("routestillmissing")
    async with sqlite_session_factory() as session:
        await registry.submit(session, theme, source="owner", inspiration="x")

    resp = await api_client.get("/v1/styles/routestillmissing/still")
    assert resp.status_code == 404
