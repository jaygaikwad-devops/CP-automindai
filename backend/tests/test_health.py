"""Tests for the health check endpoint."""

import pytest
from httpx import ASGITransport, AsyncClient

from app.main import app


@pytest.fixture
async def client():
    transport = ASGITransport(app=app)
    async with AsyncClient(transport=transport, base_url="http://test") as ac:
        yield ac


@pytest.mark.asyncio
async def test_health_check_returns_200(client):
    """GET /health returns 200 with status ok."""
    response = await client.get("/health")
    assert response.status_code == 200
    assert response.json() == {"status": "ok"}


@pytest.mark.asyncio
async def test_health_check_has_request_id_header(client):
    """GET /health response includes X-Request-ID header."""
    response = await client.get("/health")
    assert "x-request-id" in response.headers


@pytest.mark.asyncio
async def test_health_check_preserves_request_id(client):
    """If X-Request-ID is provided, it is echoed back."""
    custom_id = "test-req-12345"
    response = await client.get("/health", headers={"X-Request-ID": custom_id})
    assert response.headers["x-request-id"] == custom_id


@pytest.mark.asyncio
async def test_not_found_returns_error_format(client):
    """Unknown path returns 404 with standard error format."""
    response = await client.get("/nonexistent")
    assert response.status_code == 404
    body = response.json()
    assert "error" in body
    assert body["error"]["code"] == "not_found"
    assert "request_id" in body["error"]
