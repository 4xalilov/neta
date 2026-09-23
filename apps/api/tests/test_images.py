import fal_client
import pytest

from engine.integrations import images


@pytest.fixture(autouse=True)
def _clear_fake(monkeypatch):
    images.clear_fake_generator()
    yield
    images.clear_fake_generator()


async def _fake_download_to_storage(url, key, content_type=None):
    return f"s3://assets-test/{key}"


@pytest.fixture(autouse=True)
def _patch_download(monkeypatch):
    monkeypatch.setattr(images, "download_to_storage", _fake_download_to_storage)


async def _fake_run_async(model, arguments=None, **kwargs):
    return {
        "images": [{"url": "http://x/img.jpg", "width": 1080, "height": 1920}],
        "seed": 1,
    }


@pytest.mark.parametrize(
    "tier,model,price",
    [
        ("schnell", "fal-ai/flux/schnell", 0.003),
        ("dev", "fal-ai/flux/dev", 0.025),
        ("pro", "fal-ai/flux-pro/v1.1", 0.04),
    ],
)
async def test_generate_image_tier_model_price(monkeypatch, tier, model, price):
    monkeypatch.setattr(fal_client, "run_async", _fake_run_async)
    result = await images.generate_image("a cat", tier=tier, workspace_id="ws1")
    assert result.model == model
    assert result.usd == price
    assert result.url == "http://x/img.jpg"
    assert result.width == 1080
    assert result.height == 1920
    assert result.seed == 1
    assert result.uri.startswith("s3://assets-test/ws/ws1/image/")
    assert result.uri.endswith(".jpg")


async def test_generate_image_default_tier_is_schnell(monkeypatch):
    monkeypatch.setattr(fal_client, "run_async", _fake_run_async)
    result = await images.generate_image("a dog")
    assert result.model == images.MODELS["schnell"]
    assert result.usd == images.PRICES["schnell"]


async def test_generate_image_raises_without_images(monkeypatch):
    async def _empty(model, arguments=None, **kwargs):
        return {"images": []}

    monkeypatch.setattr(fal_client, "run_async", _empty)
    with pytest.raises(RuntimeError):
        await images.generate_image("nothing")


async def test_generate_image_passes_seed(monkeypatch):
    captured = {}

    async def _capture(model, arguments=None, **kwargs):
        captured["arguments"] = arguments
        return {"images": [{"url": "http://x/img.jpg", "width": 1080, "height": 1920}], "seed": 42}

    monkeypatch.setattr(fal_client, "run_async", _capture)
    result = await images.generate_image("a cat", seed=42)
    assert captured["arguments"]["seed"] == 42
    assert result.seed == 42


async def test_depth_map(monkeypatch):
    async def _fake_depth(model, arguments=None, **kwargs):
        assert model == images.DEPTH_MODEL
        return {"image": {"url": "http://x/depth.png"}}

    monkeypatch.setattr(fal_client, "run_async", _fake_depth)
    result = await images.depth_map("http://x/img.jpg", workspace_id="ws1")
    assert result.url == "http://x/depth.png"
    assert result.usd == images.DEPTH_PRICE_USD
    assert result.uri.startswith("s3://assets-test/ws/ws1/depth/")


async def test_depth_map_raises_without_url(monkeypatch):
    async def _empty(model, arguments=None, **kwargs):
        return {}

    monkeypatch.setattr(fal_client, "run_async", _empty)
    with pytest.raises(RuntimeError):
        await images.depth_map("http://x/img.jpg")


async def test_fake_generator_used_instead_of_network(monkeypatch):
    async def _blow_up(model, arguments=None, **kwargs):
        raise AssertionError("network should not be called when fake generator is set")

    monkeypatch.setattr(fal_client, "run_async", _blow_up)

    async def fake_gen(prompt, *, tier="schnell", width=1080, height=1920, seed=None,
                        workspace_id="", node="flux"):
        return images.ImageResult(
            uri="s3://fake/x.jpg", url="http://fake/x.jpg", width=width, height=height,
            seed=seed, usd=0.0, model="fake",
        )

    images.set_fake_generator(fake_gen)
    result = await images.generate_image("prompt", workspace_id="ws1")
    assert result.model == "fake"
    assert result.uri == "s3://fake/x.jpg"


def test_reels_prompt_appends_style_hints():
    prompt = images.reels_prompt(
        "a woman drinking coffee",
        {"bg": "#0B0F19", "accent": "#FACC15", "primary": "#6366F1"},
    )
    assert "a woman drinking coffee" in prompt
    assert "9:16" in prompt
    assert "no text" in prompt
    assert "no watermark" in prompt
    assert "#FACC15" in prompt


def test_negative_prompt_blocks_text_and_watermark():
    assert "text" in images.NEGATIVE_PROMPT
    assert "watermark" in images.NEGATIVE_PROMPT
