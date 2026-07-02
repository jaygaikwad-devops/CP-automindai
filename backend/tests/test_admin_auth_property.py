"""Property-based tests for admin-only authorization.

**Validates: Requirements 16.5**

Uses hypothesis to generate random user roles and verify that
non-admin users always receive 403 Forbidden on admin endpoints.
"""

import uuid
from unittest.mock import AsyncMock, MagicMock

import pytest
from httpx import ASGITransport, AsyncClient
from hypothesis import given, settings, assume, HealthCheck
from hypothesis import strategies as st

from app.core.database import get_db
from app.core.security import create_access_token
from app.services.redis_cache import get_redis


# --- Strategies ---

# Known roles that are NOT admin
known_non_admin_roles = st.sampled_from(["cp", "buyer", "anonymous", "guest", "user"])

# Random strings for roles (fuzz testing)
random_role_strategy = st.text(
    alphabet=st.characters(whitelist_categories=("L", "N")),
    min_size=1,
    max_size=20,
).filter(lambda s: s != "admin")

# Combined: non-admin roles — both known and random
non_admin_role_strategy = st.one_of(known_non_admin_roles, random_role_strategy)

# Admin endpoint paths with methods and sample payloads
admin_endpoints = [
    ("POST", "/api/v1/admin/projects", {
        "name": "Test Project",
        "builder_id": str(uuid.uuid4()),
        "location": "Mumbai",
        "unit_types": ["2BHK"],
    }),
    ("POST", "/api/v1/admin/partnerships", {
        "cp_id": str(uuid.uuid4()),
        "project_id": str(uuid.uuid4()),
    }),
    ("DELETE", f"/api/v1/admin/partnerships/{uuid.uuid4()}", None),
]


# --- Helpers ---


def _create_token_with_role(role: str) -> str:
    """Create a JWT token with the given role."""
    return create_access_token(
        data={"sub": f"user-{role}", "phone": "9876543210", "role": role}
    )


async def _get_client():
    """Create a test client with mocked dependencies."""
    from app.main import app

    mock_redis = AsyncMock()
    mock_db = AsyncMock()
    mock_db.add = MagicMock()
    mock_db.commit = AsyncMock()
    mock_db.flush = AsyncMock()
    mock_db.delete = AsyncMock()
    mock_db.rollback = AsyncMock()
    mock_db.execute = AsyncMock(
        return_value=MagicMock(scalar_one_or_none=MagicMock(return_value=None))
    )

    async def override_get_redis():
        return mock_redis

    async def override_get_db():
        yield mock_db

    app.dependency_overrides[get_redis] = override_get_redis
    app.dependency_overrides[get_db] = override_get_db

    transport = ASGITransport(app=app)
    client = AsyncClient(transport=transport, base_url="http://test")
    return client, app


# --- Property Tests ---


@pytest.mark.asyncio
@given(role=non_admin_role_strategy)
@settings(max_examples=50, deadline=None, suppress_health_check=[HealthCheck.function_scoped_fixture])
async def test_non_admin_always_gets_403_on_create_project(role: str):
    """Property 22: Non-admin users always get 403 on POST /api/v1/admin/projects."""
    client, app = await _get_client()
    try:
        token = _create_token_with_role(role)
        response = await client.post(
            "/api/v1/admin/projects",
            json={
                "name": "Test Project",
                "builder_id": str(uuid.uuid4()),
                "location": "Mumbai",
                "unit_types": ["2BHK"],
            },
            headers={"Authorization": f"Bearer {token}"},
        )
        assert response.status_code == 403, f"Role '{role}' got {response.status_code}, expected 403"
    finally:
        await client.aclose()
        app.dependency_overrides.clear()


@pytest.mark.asyncio
@given(role=non_admin_role_strategy)
@settings(max_examples=50, deadline=None, suppress_health_check=[HealthCheck.function_scoped_fixture])
async def test_non_admin_always_gets_403_on_create_partnership(role: str):
    """Property 22: Non-admin users always get 403 on POST /api/v1/admin/partnerships."""
    client, app = await _get_client()
    try:
        token = _create_token_with_role(role)
        response = await client.post(
            "/api/v1/admin/partnerships",
            json={
                "cp_id": str(uuid.uuid4()),
                "project_id": str(uuid.uuid4()),
            },
            headers={"Authorization": f"Bearer {token}"},
        )
        assert response.status_code == 403, f"Role '{role}' got {response.status_code}, expected 403"
    finally:
        await client.aclose()
        app.dependency_overrides.clear()


@pytest.mark.asyncio
@given(role=non_admin_role_strategy)
@settings(max_examples=50, deadline=None, suppress_health_check=[HealthCheck.function_scoped_fixture])
async def test_non_admin_always_gets_403_on_delete_partnership(role: str):
    """Property 22: Non-admin users always get 403 on DELETE /api/v1/admin/partnerships/{id}."""
    client, app = await _get_client()
    try:
        token = _create_token_with_role(role)
        partnership_id = str(uuid.uuid4())
        response = await client.delete(
            f"/api/v1/admin/partnerships/{partnership_id}",
            headers={"Authorization": f"Bearer {token}"},
        )
        assert response.status_code == 403, f"Role '{role}' got {response.status_code}, expected 403"
    finally:
        await client.aclose()
        app.dependency_overrides.clear()
