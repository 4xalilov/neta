from types import SimpleNamespace

import anthropic
import httpx2
import pytest
from google.genai import errors as genai_errors

from engine import cost_tracker, llm
from engine.settings import settings


class FakeAnthropic:
    """AsyncAnthropic'ning ``messages.create`` / ``beta.messages.create`` o'rnini bosadi."""

    def __init__(self, replies):
        self.replies = list(replies)  # str yoki Exception
        self.calls = []
        self.messages = SimpleNamespace(create=self._create("messages"))
        self.beta = SimpleNamespace(messages=SimpleNamespace(create=self._create("beta")))

    def _create(self, path):
        async def create(**kwargs):
            self.calls.append((path, kwargs))
            r = self.replies.pop(0)
            if isinstance(r, Exception):
                raise r
            return SimpleNamespace(
                stop_reason="end_turn",
                stop_details=None,
                model=kwargs["model"],
                content=[SimpleNamespace(type="thinking", thinking=""),
                         SimpleNamespace(type="text", text=r)],
                usage=SimpleNamespace(input_tokens=1000, output_tokens=200,
                                      cache_creation_input_tokens=0,
                                      cache_read_input_tokens=0),
            )
        return create


class FakeGemini:
    def __init__(self, replies):
        self.replies = list(replies)
        self.calls = []
        self.aio = SimpleNamespace(models=SimpleNamespace(generate_content=self._gen))

    async def _gen(self, *, model, contents, config):
        self.calls.append({"model": model, "contents": contents, "config": config})
        r = self.replies.pop(0)
        if isinstance(r, Exception):
            raise r
        return SimpleNamespace(
            text=r,
            usage_metadata=SimpleNamespace(prompt_token_count=400, candidates_token_count=100,
                                           thoughts_token_count=50),
        )


def _rate_limit():
    req = httpx2.Request("POST", "https://api.anthropic.com/v1/messages")
    return anthropic.RateLimitError("rate limited", response=httpx2.Response(429, request=req),
                                    body=None)


def _bad_request():
    req = httpx2.Request("POST", "https://api.anthropic.com/v1/messages")
    return anthropic.BadRequestError("bad", response=httpx2.Response(400, request=req), body=None)


@pytest.fixture(autouse=True)
def _env(monkeypatch):
    monkeypatch.setattr(llm, "RETRY_BASE_DELAY_S", 0.0)
    monkeypatch.setattr(settings, "llm_draft_model", "gemini-2.5-flash")
    monkeypatch.setattr(settings, "llm_critic_model", "claude-sonnet-5")
    monkeypatch.setattr(settings, "llm_vision_model", "gemini-2.5-flash")
    monkeypatch.setattr(settings, "llm_final_model", "claude-opus-5")
    monkeypatch.setattr(settings, "llm_max_retries", 3)

    def no_network():
        raise AssertionError("real client must not be created in tests")

    monkeypatch.setattr(llm, "_anthropic_client", no_network)
    monkeypatch.setattr(llm, "_gemini_client", no_network)
    cost_tracker.RECENT.clear()
    llm.clear_fake()
    yield
    llm.clear_fake()
    cost_tracker.RECENT.clear()


def _use(monkeypatch, *, claude=None, gemini=None):
    if claude is not None:
        monkeypatch.setattr(llm, "_anthropic_client", lambda: claude)
    if gemini is not None:
        monkeypatch.setattr(llm, "_gemini_client", lambda: gemini)


async def test_claude_tier_routes_to_anthropic(monkeypatch):
    claude = FakeAnthropic(["salom"])
    _use(monkeypatch, claude=claude)
    res = await llm.complete("critic", "sys", "user msg", node="uz_critic", workspace_id="ws1",
                             temperature=0.3)

    assert res.text == "salom"  # thinking bloklari tashlanadi
    assert res.provider == "anthropic" and res.model == "claude-sonnet-5"
    assert (res.tokens_in, res.tokens_out) == (1000, 200)
    assert res.usd == pytest.approx(cost_tracker.price("claude-sonnet-5", 1000, 200))

    path, kw = claude.calls[0]
    assert path == "messages"
    assert kw["system"] == "sys" and kw["max_tokens"] == 2048
    assert kw["messages"] == [{"role": "user", "content": "user msg"}]
    assert "extra_body" not in kw  # Sonnet 5 temperature qabul qilmaydi

    entry = cost_tracker.RECENT[-1]
    assert entry["workspace_id"] == "ws1" and entry["node"] == "uz_critic"
    assert entry["provider"] == "anthropic" and entry["model"] == "claude-sonnet-5"
    assert entry["usd"] == pytest.approx(res.usd)


async def test_final_tier_uses_server_side_fallbacks(monkeypatch):
    claude = FakeAnthropic(["ok"])
    _use(monkeypatch, claude=claude)
    res = await llm.complete("final", "", "hi", max_tokens=500, effort="low")
    path, kw = claude.calls[0]
    assert path == "beta" and kw["model"] == "claude-opus-5"
    assert kw["fallbacks"] == "default" and kw["betas"] == ["server-side-fallback-2026-07-01"]
    assert "system" not in kw and kw["max_tokens"] == 500
    assert kw["output_config"] == {"effort": "low"}
    assert res.text == "ok"


async def test_temperature_passed_for_older_claude(monkeypatch):
    monkeypatch.setattr(settings, "llm_draft_model", "claude-haiku-4-5")
    claude = FakeAnthropic(["x"])
    _use(monkeypatch, claude=claude)
    await llm.complete("draft", "s", "u", temperature=0.2)
    assert claude.calls[0][1]["extra_body"] == {"temperature": 0.2}


async def test_gemini_tier_routes_to_google(monkeypatch):
    gem = FakeGemini(['{"a": 1}'])
    _use(monkeypatch, gemini=gem)
    res = await llm.complete("draft", "sys", "u", json_mode=True, node="writer",
                             workspace_id="ws", temperature=0.7)

    call = gem.calls[0]
    assert call["model"] == "gemini-2.5-flash" and call["contents"] == "u"
    cfg = call["config"]
    assert cfg.response_mime_type == "application/json"
    assert cfg.system_instruction == "sys" and cfg.temperature == 0.7
    assert cfg.max_output_tokens == 2048
    assert res.provider == "google"
    assert (res.tokens_in, res.tokens_out) == (400, 150)  # thoughts ham hisoblanadi
    assert cost_tracker.RECENT[-1]["provider"] == "google"


async def test_vision_images(monkeypatch):
    png = b"\x89PNG\r\n\x1a\n" + b"0" * 10
    gem = FakeGemini(["ok"])
    _use(monkeypatch, gemini=gem)
    await llm.complete("vision", "s", "describe", images=[png, "https://x/y.jpg"])
    parts = gem.calls[0]["contents"]
    assert parts[0].inline_data.mime_type == "image/png"
    assert parts[1].file_data.file_uri == "https://x/y.jpg"
    assert parts[-1] == "describe"

    monkeypatch.setattr(settings, "llm_vision_model", "claude-sonnet-5")
    claude = FakeAnthropic(["ok"])
    _use(monkeypatch, claude=claude)
    await llm.complete("vision", "s", "describe", images=[png, "https://x/y.jpg"])
    content = claude.calls[0][1]["messages"][0]["content"]
    assert content[0]["source"]["type"] == "base64"
    assert content[0]["source"]["media_type"] == "image/png"
    assert content[1]["source"] == {"type": "url", "url": "https://x/y.jpg"}
    assert content[2] == {"type": "text", "text": "describe"}


async def test_retry_on_transient_then_success(monkeypatch):
    claude = FakeAnthropic([_rate_limit(), TimeoutError(), "done"])
    _use(monkeypatch, claude=claude)
    res = await llm.complete("critic", "s", "u")
    assert res.text == "done" and len(claude.calls) == 3
    assert len(cost_tracker.RECENT) == 1  # faqat muvaffaqiyatli chaqiriq yoziladi

    gem = FakeGemini([genai_errors.ServerError(503, {"error": {"message": "busy"}}), "ok"])
    _use(monkeypatch, gemini=gem)
    assert (await llm.complete("draft", "s", "u")).text == "ok"
    assert len(gem.calls) == 2


async def test_retry_gives_up_after_max_attempts(monkeypatch):
    claude = FakeAnthropic([_rate_limit(), _rate_limit(), _rate_limit(), "never"])
    _use(monkeypatch, claude=claude)
    with pytest.raises(anthropic.RateLimitError):
        await llm.complete("critic", "s", "u")
    assert len(claude.calls) == 3
    assert not cost_tracker.RECENT


async def test_no_retry_on_client_error(monkeypatch):
    claude = FakeAnthropic([_bad_request(), "never"])
    _use(monkeypatch, claude=claude)
    with pytest.raises(anthropic.BadRequestError):
        await llm.complete("critic", "s", "u")
    assert len(claude.calls) == 1


async def test_refusal_raises(monkeypatch):
    claude = FakeAnthropic(["x"])

    async def refuse(**kwargs):
        return SimpleNamespace(stop_reason="refusal",
                               stop_details=SimpleNamespace(category="cyber"),
                               content=[], usage=None, model=kwargs["model"])

    claude.messages.create = refuse
    _use(monkeypatch, claude=claude)
    with pytest.raises(llm.LLMRefusalError):
        await llm.complete("critic", "s", "u")


def test_unknown_provider():
    with pytest.raises(ValueError):
        llm._provider_for("gpt-5")


@pytest.mark.parametrize("raw", [
    '{"score": 8, "reasons": ["a"]}',
    '```json\n{"score": 8, "reasons": ["a"]}\n```',
    'Mana natija:\n```\n{"score": 8, "reasons": ["a",],}\n```\nOmad!',
    'Natija: {"score": 8, "reasons": ["a"]} tamom',
    '“x”',  # dict emas -> xato (quyida alohida)
])
def test_parse_json_repairs(raw):
    if raw.startswith("“"):
        with pytest.raises(llm.LLMJSONError):
            llm.parse_json(raw)
    else:
        assert llm.parse_json(raw) == {"score": 8, "reasons": ["a"]}


async def test_complete_json_system_instruction_and_retry_nudge(monkeypatch):
    claude = FakeAnthropic(["Kechirasiz, bu JSON emas", '{"score": 9}'])
    _use(monkeypatch, claude=claude)
    out = await llm.complete_json("critic", "Rate it.", "script", node="hook_critic")
    assert out == {"score": 9}
    first, second = claude.calls[0][1], claude.calls[1][1]
    assert "valid JSON" in first["system"]
    assert first["messages"][0]["content"] == "script"
    assert "not valid JSON" in second["messages"][0]["content"]
    assert len(cost_tracker.RECENT) == 2


async def test_complete_json_fails_after_one_retry(monkeypatch):
    claude = FakeAnthropic(["nope", "still nope", '{"never": 1}'])
    _use(monkeypatch, claude=claude)
    with pytest.raises(llm.LLMJSONError):
        await llm.complete_json("critic", "s", "u")
    assert len(claude.calls) == 2


async def test_set_fake_bypasses_providers():
    seen = []

    def handler(tier, system, user):
        seen.append((tier, system, user))
        return {"score": 9, "reasons": []} if tier == "critic" else "draft text"

    llm.set_fake(handler)
    res = await llm.complete("draft", "s" * 40, "u" * 40, node="writer", workspace_id="ws")
    assert res.text == "draft text" and res.provider == "fake"
    assert res.tokens_in == 20 and res.tokens_out == len("draft text") // 4
    assert res.usd == pytest.approx(cost_tracker.price("gemini-2.5-flash", 20, 2))

    assert await llm.complete_json("critic", "s", "u") == {"score": 9, "reasons": []}
    assert [t for t, _, _ in seen] == ["draft", "critic"]
    assert cost_tracker.summary("ws")["by_node"] == {"writer": pytest.approx(res.usd)}

    async def async_handler(tier, system, user):
        return "async ok"

    llm.set_fake(async_handler)
    assert (await llm.complete("final", "s", "u")).text == "async ok"

    llm.clear_fake()
    with pytest.raises(AssertionError, match="real client"):
        await llm.complete("draft", "s", "u")
