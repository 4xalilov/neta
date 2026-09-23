import httpx
import pytest

from bot.api_client import ApiClient, ApiError


def _client_with_transport(transport: httpx.MockTransport) -> ApiClient:
    api = ApiClient(base_url="http://api:8000")
    api._client = httpx.AsyncClient(base_url="http://api:8000", transport=transport)
    return api


@pytest.mark.asyncio
async def test_create_workspace_posts_and_parses_json():
    def handler(request: httpx.Request) -> httpx.Response:
        assert request.method == "POST"
        assert request.url.path == "/v1/workspaces"
        assert request.content  # body was sent
        return httpx.Response(200, json={"id": "ws-1", "name": "Test"})

    api = _client_with_transport(httpx.MockTransport(handler))
    result = await api.create_workspace(owner_tg_id=1, name="Test")
    assert result == {"id": "ws-1", "name": "Test"}
    await api.aclose()


@pytest.mark.asyncio
async def test_get_workspace_returns_none_on_404():
    def handler(request: httpx.Request) -> httpx.Response:
        return httpx.Response(404, json={"detail": "not found"})

    api = _client_with_transport(httpx.MockTransport(handler))
    result = await api.get_workspace(owner_tg_id=1)
    assert result is None
    await api.aclose()


@pytest.mark.asyncio
async def test_server_error_raises_api_error():
    def handler(request: httpx.Request) -> httpx.Response:
        return httpx.Response(500, json={"detail": "boom"})

    api = _client_with_transport(httpx.MockTransport(handler))
    with pytest.raises(ApiError):
        await api.get_job("job-1")
    await api.aclose()


@pytest.mark.asyncio
async def test_network_error_raises_api_error():
    def handler(request: httpx.Request) -> httpx.Response:
        raise httpx.ConnectError("no route to host", request=request)

    api = _client_with_transport(httpx.MockTransport(handler))
    with pytest.raises(ApiError):
        await api.create_brief(workspace_id="ws-1", text="brif")
    await api.aclose()


@pytest.mark.asyncio
async def test_create_brief_extracts_job_id():
    def handler(request: httpx.Request) -> httpx.Response:
        return httpx.Response(200, json={"job_id": "job-42"})

    api = _client_with_transport(httpx.MockTransport(handler))
    job_id = await api.create_brief(workspace_id="ws-1", text="brif")
    assert job_id == "job-42"
    await api.aclose()


@pytest.mark.asyncio
async def test_approve_video_uses_video_approve_path_and_action_body():
    seen = {}

    def handler(request: httpx.Request) -> httpx.Response:
        seen["path"] = request.url.path
        seen["body"] = request.content
        return httpx.Response(200, json={"ok": True})

    api = _client_with_transport(httpx.MockTransport(handler))
    result = await api.approve_video("script-1", action="publish")
    assert result == {"ok": True}
    assert seen["path"] == "/v1/scripts/script-1/video-approve"
    assert b'"publish"' in seen["body"]
    await api.aclose()
