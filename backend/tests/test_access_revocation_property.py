"""Property-based tests for access revocation immediacy.

**Validates: Requirements 16.4**

Uses hypothesis to test that after partnership removal,
subsequent project access attempts by the CP return 403.
"""

import uuid
from unittest.mock import AsyncMock, MagicMock

import pytest
from httpx import ASGITransport, AsyncClient
from hypothesis import given, settings, HealthCheck
from hypothesis import strategies as st

from app.core.database import get_db
from app.core.security import create_access_token
from app.core.tenant_isolation import require_project_access
from app.services.redis_cache import get_redis


# --- Strategies ---

@st.composite
def partnership_removal_scenarios(draw):
    """Generate partnership creation + removal sequences."""
    num_partnerships = draw(st.integers(min_value=1, max_value=5))

    scenarios = []
    for _ in range(num_partnerships):
        cp_id = str(uuid.uuid4())
        project_id = str(uuid.uuid4())
        # Always remove after creation
        scenarios.append({
            "cp_id": cp_id,
            "project_id": project_id,
        })

    return scenarios


# --- Helpers ---


def _create_admin_token() -> str:
    """Create a JWT token with admin role."""
    return create_access_token(
        data={"sub": "admin-sub", "phone": "9999999999", "role": "admin"}
    )


def _create_cp_token(cp_id: str) -> str:
    """Create a JWT token for a CP with their cp_id."""
    return create_access_token(
        data={"sub": f"cp-{cp_id}", "phone": "9876543210", "role": "cp", "cp_id": cp_id}
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

    async def override_get_redis():
        return mock_redis

    async def override_get_db():
        yield mock_db

    app.dependency_overrides[get_redis] = override_get_redis
    app.dependency_overrides[get_db] = override_get_db

    transport = ASGITransport(app=app)
    client = AsyncClient(transport=transport, base_url="http://test")
    return client, app, mock_db


# --- Property Tests ---


@pytest.mark.asyncio
@given(scenarios=partnership_removal_scenarios())
@settings(max_examples=50, deadline=None, suppress_health_check=[HealthCheck.function_scoped_fixture])
async def test_access_denied_after_partnership_removal(scenarios: list):
    """Property 23: After partnership removal, all access attempts return 403.

    For each partnership:
    1. Create partnership (admin)
    2. Delete partnership (admin)
    3. Verify CP gets 403 when accessing the project via tenant isolation
    """
    client, app, mock_db = await _get_client()
    try:
        admin_token = _create_admin_token()

        for scenario in scenarios:
            cp_id = scenario["cp_id"]
            project_id = scenario["project_id"]
            partnership_id = str(uuid.uuid4())

            # Step 1: Create partnership (mock success)
            mock_project = MagicMock()
            mock_project.builder_id = uuid.uuid4()
            mock_cp = MagicMock()

            call_count = [0]

            async def mock_execute_create(stmt, _project=mock_project, _cp=mock_cp):
                call_count[0] += 1
                result = MagicMock()
                if call_count[0] == 1:
                    result.scalar_one_or_none = MagicMock(return_value=_project)
                else:
                    result.scalar_one_or_none = MagicMock(return_value=_cp)
                return result

            mock_db.execute = mock_execute_create
            mock_db.flush = AsyncMock()

            response = await client.post(
                "/api/v1/admin/partnerships",
                json={"cp_id": cp_id, "project_id": project_id},
                headers={"Authorization": f"Bearer {admin_token}"},
            )
            assert response.status_code == 201

            # Step 2: Delete partnership
            mock_partnership = MagicMock()
            mock_result = MagicMock()
            mock_result.scalar_one_or_none = MagicMock(return_value=mock_partnership)
            mock_db.execute = AsyncMock(return_value=mock_result)

            response = await client.delete(
                f"/api/v1/admin/partnerships/{partnership_id}",
                headers={"Authorization": f"Bearer {admin_token}"},
            )
            assert response.status_code == 204

            # Step 3: Verify CP access is denied (simulate tenant isolation check)
            # After deletion, partnership lookup should return None
            mock_no_result = MagicMock()
            mock_no_result.scalar_one_or_none = MagicMock(return_value=None)
            mock_db.execute = AsyncMock(return_value=mock_no_result)

            from fastapi import HTTPException
            from app.core.tenant_isolation import require_project_access

            cp_user = {"sub": f"cp-{cp_id}", "phone": "9876543210", "role": "cp", "cp_id": cp_id}

            # Create a real async session mock for the dependency
            class FakeDB:
                async def execute(self, stmt):
                    return mock_no_result

            with pytest.raises(HTTPException) as exc_info:
                await require_project_access(
                    project_id=project_id,
                    current_user=cp_user,
                    db=FakeDB(),
                )
            assert exc_info.value.status_code == 403

    finally:
        await client.aclose()
        app.dependency_overrides.clear()
