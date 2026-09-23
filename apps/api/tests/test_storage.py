import httpx
import pytest
from moto import mock_aws

from engine.integrations import storage


@pytest.fixture(autouse=True)
def _aws_endpoint(monkeypatch):
    # moto odatda custom (masalan MinIO) endpoint_url'ni ushlamaydi — standart
    # AWS endpoint'iga o'tkazamiz, shunda mock ishlaydi. `@mock_aws` async test
    # funksiyalarni to'g'ri o'rab bera olmagani uchun context manager sifatida
    # ishlatamiz (pytest-asyncio bilan mos ishlashi uchun).
    monkeypatch.setattr(storage.settings, "s3_endpoint", "")
    monkeypatch.setattr(storage.settings, "s3_bucket", "assets-test")
    with mock_aws():
        yield


def test_key_for_format():
    key = storage.key_for("ws1", "image", "jpg")
    assert key.startswith("ws/ws1/image/")
    assert key.endswith(".jpg")
    assert key.count("/") == 3


def test_public_url_from_uri():
    storage.settings.public_s3_url = "http://localhost:9000"
    assert (
        storage.public_url("s3://assets/ws/1/image/a.jpg")
        == "http://localhost:9000/assets/ws/1/image/a.jpg"
    )


def test_public_url_from_bare_key():
    storage.settings.public_s3_url = "http://localhost:9000"
    storage.settings.s3_bucket = "assets"
    assert (
        storage.public_url("ws/1/image/a.jpg")
        == "http://localhost:9000/assets/ws/1/image/a.jpg"
    )


async def test_ensure_bucket_and_put_get_bytes():
    await storage.ensure_bucket()
    uri = await storage.put_bytes("ws/1/image/a.jpg", b"hello", "image/jpeg")
    assert uri == "s3://assets-test/ws/1/image/a.jpg"
    data = await storage.get_bytes("ws/1/image/a.jpg")
    assert data == b"hello"


async def test_put_file(tmp_path):
    await storage.ensure_bucket()
    p = tmp_path / "f.txt"
    p.write_text("content")
    uri = await storage.put_file("ws/1/audio/a.txt", str(p), "text/plain")
    assert uri == "s3://assets-test/ws/1/audio/a.txt"
    assert await storage.get_bytes("ws/1/audio/a.txt") == b"content"


async def test_presigned_url_contains_key():
    await storage.ensure_bucket()
    await storage.put_bytes("ws/1/image/a.jpg", b"x", "image/jpeg")
    url = await storage.presigned_url("ws/1/image/a.jpg", expires=60)
    assert "ws/1/image/a.jpg" in url


async def test_download_to_storage(monkeypatch):
    await storage.ensure_bucket()

    def handler(request: httpx.Request) -> httpx.Response:
        assert str(request.url) == "http://x/img.jpg"
        return httpx.Response(200, content=b"binarydata", headers={"content-type": "image/jpeg"})

    def _fake_http_client() -> httpx.AsyncClient:
        return httpx.AsyncClient(transport=httpx.MockTransport(handler))

    monkeypatch.setattr(storage, "_http_client", _fake_http_client)

    uri = await storage.download_to_storage("http://x/img.jpg", "ws/1/image/b.jpg")
    assert uri == "s3://assets-test/ws/1/image/b.jpg"
    assert await storage.get_bytes("ws/1/image/b.jpg") == b"binarydata"


async def test_download_to_storage_explicit_content_type(monkeypatch):
    await storage.ensure_bucket()

    def handler(request: httpx.Request) -> httpx.Response:
        return httpx.Response(200, content=b"png-bytes")

    def _fake_http_client() -> httpx.AsyncClient:
        return httpx.AsyncClient(transport=httpx.MockTransport(handler))

    monkeypatch.setattr(storage, "_http_client", _fake_http_client)

    uri = await storage.download_to_storage(
        "http://x/depth.png", "ws/1/depth/c.png", content_type="image/png"
    )
    assert uri.endswith("ws/1/depth/c.png")
