import pytest

from engine import cost_tracker


@pytest.fixture(autouse=True)
def _clean():
    cost_tracker.RECENT.clear()
    cost_tracker.set_sink(None)
    yield
    cost_tracker.RECENT.clear()
    cost_tracker.set_sink(None)


def test_price_exact_models():
    # claude-sonnet-5: $2 in / $10 out per 1M
    assert cost_tracker.price("claude-sonnet-5", 1_000_000, 0) == pytest.approx(2.0)
    assert cost_tracker.price("claude-sonnet-5", 0, 1_000_000) == pytest.approx(10.0)
    # gemini-2.5-flash: 1000 in + 500 out
    assert cost_tracker.price("gemini-2.5-flash", 1000, 500) == pytest.approx(
        (1000 * 0.30 + 500 * 2.50) / 1_000_000)


def test_price_longest_prefix_and_unknown():
    # versiyali id eng uzun prefiksga tushadi: flash-lite, flash emas
    assert cost_tracker.price("gemini-2.5-flash-lite-001", 1_000_000, 0) == pytest.approx(0.10)
    # opus-5-5 o'z narxiga ega (opus-5 prefiksi bilan chalkashmaydi)
    assert cost_tracker.price("claude-opus-5-5", 1_000_000, 0) == pytest.approx(4.0)
    assert cost_tracker.price("claude-opus-5", 1_000_000, 0) == pytest.approx(5.0)
    assert cost_tracker.price("mystery-model", 10, 10) == 0.0


async def test_log_recent_and_summary():
    await cost_tracker.log("ws1", "writer", "anthropic", "claude-sonnet-5", 100, 50, 0.01)
    await cost_tracker.log("ws1", "writer", "google", "gemini-2.5-flash", 100, 50, 0.02)
    await cost_tracker.log("ws1", "critic", "anthropic", "claude-sonnet-5", 10, 5, 0.03)
    await cost_tracker.log("ws2", "writer", "anthropic", "claude-sonnet-5", 10, 5, 1.0)
    await cost_tracker.log_media("ws1", "tts", "azure", 0.004, {"chars": 400})

    s = cost_tracker.summary("ws1")
    assert s["usd_total"] == pytest.approx(0.064)
    assert s["by_node"] == pytest.approx({"writer": 0.03, "critic": 0.03, "tts": 0.004})
    assert cost_tracker.summary("nobody") == {"usd_total": 0.0, "by_node": {}}

    media = cost_tracker.RECENT[-1]
    assert media["kind"] == "media" and media["meta"] == {"chars": 400}
    assert cost_tracker.RECENT[0]["kind"] == "llm"


async def test_recent_is_bounded():
    for _ in range(1005):
        await cost_tracker.log("ws", "n", "p", "m", 1, 1, 0.0)
    assert len(cost_tracker.RECENT) == 1000


async def test_sink_called_and_errors_swallowed():
    seen = []

    async def sink(entry):
        seen.append(entry)

    cost_tracker.set_sink(sink)
    await cost_tracker.log("ws", "writer", "anthropic", "claude-sonnet-5", 1, 2, 0.5)
    assert seen[0]["workspace_id"] == "ws" and seen[0]["usd"] == 0.5
    assert seen[0]["tokens_in"] == 1 and seen[0]["tokens_out"] == 2

    async def broken(entry):
        raise RuntimeError("db down")

    cost_tracker.set_sink(broken)
    await cost_tracker.log("ws", "writer", "anthropic", "claude-sonnet-5", 1, 2, 0.5)
    assert len(cost_tracker.RECENT) == 2
