"""Tests for admin API endpoints.

Tests project creation, partnership assignment, partnership removal,
and admin-only authorization enforcement.
"""

import uuid
from unittest.mock import AsyncMock, MagicMock, patch

import pytest
from httpx import ASGITransport, AsyncClient
from sqlalchemy.exc import IntegrityError

from app.core.database import get_db
from app.core.security import create_access_token
from app.services.redis_cache import get_redis


# --- Test Fixtures ---


def _create_admin_token() -> str:
    """Create a JWT token with admin role."""
    return create_access_token(
        data={"sub": "admin-sub", "phone": "9999999999", "role": "admin"}
    )


def _create_cp_token() -> str:
    """Create a JWT token with cp role."""
    return create_access_token(
        data={"sub": "cp-sub", "phone": "9876543210", "role": "cp"}
    )


def _create_buyer_token() -> str:
    """Create a JWT token with buyer role."""
    return create_access_token(
        data={"sub": "buyer-sub", "phone": "", "role": "buyer"}
    )


@pytest.fixture
async def admin_client():
    """Async test client with mocked dependencies."""
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
    async with AsyncClient(transport=transport, base_url="http://test") as ac:
        ac._mock_db = mock_db
        yield ac

    app.dependency_overrides.clear()


# --- Project Creation Tests ---


class TestCreateProject:
    """Tests for POST /api/v1/admin/projects."""

    @pytest.mark.asyncio
    async def test_admin_creates_project_201(self, admin_client):
        """Admin user can successfully create a project."""
        token = _create_admin_token()
        builder_id = str(uuid.uuid4())

        response = await admin_client.post(
            "/api/v1/admin/projects",
            json={
                "name": "Sunshine Heights",
                "builder_id": builder_id,
                "location": "Pune",
                "unit_types": ["2BHK", "3BHK"],
            },
            headers={"Authorization": f"Bearer {token}"},
        )

        assert response.status_code == 201
        data = response.json()
        assert "project_id" in data
        assert data["status"] == "not_started"

    @pytest.mark.asyncio
    async def test_cp_cannot_create_project_403(self, admin_client):
        """CP user gets 403 when trying to create a project."""
        token = _create_cp_token()

        response = await admin_client.post(
            "/api/v1/admin/projects",
            json={
                "name": "Sunshine Heights",
                "builder_id": str(uuid.uuid4()),
                "location": "Pune",
                "unit_types": ["2BHK"],
            },
            headers={"Authorization": f"Bearer {token}"},
        )

        assert response.status_code == 403

    @pytest.mark.asyncio
    async def test_buyer_cannot_create_project_403(self, admin_client):
        """Buyer user gets 403 when trying to create a project."""
        token = _create_buyer_token()

        response = await admin_client.post(
            "/api/v1/admin/projects",
            json={
                "name": "Sunshine Heights",
                "builder_id": str(uuid.uuid4()),
                "location": "Pune",
                "unit_types": [],
            },
            headers={"Authorization": f"Bearer {token}"},
        )

        assert response.status_code == 403

    @pytest.mark.asyncio
    async def test_no_auth_returns_403(self, admin_client):
        """Request without auth token returns 403."""
        response = await admin_client.post(
            "/api/v1/admin/projects",
            json={
                "name": "Sunshine Heights",
                "builder_id": str(uuid.uuid4()),
                "location": "Pune",
                "unit_types": [],
            },
        )

        assert response.status_code == 403

    @pytest.mark.asyncio
    async def test_empty_name_returns_422(self, admin_client):
        """Empty project name returns 422."""
        token = _create_admin_token()

        response = await admin_client.post(
            "/api/v1/admin/projects",
            json={
                "name": "",
                "builder_id": str(uuid.uuid4()),
                "location": "Pune",
                "unit_types": [],
            },
            headers={"Authorization": f"Bearer {token}"},
        )

        assert response.status_code == 422


# --- Partnership Assignment Tests ---


class TestCreatePartnership:
    """Tests for POST /api/v1/admin/partnerships."""

    @pytest.mark.asyncio
    async def test_admin_creates_partnership_201(self, admin_client):
        """Admin can assign CP to project."""
        token = _create_admin_token()
        cp_id = str(uuid.uuid4())
        project_id = str(uuid.uuid4())
        builder_id = uuid.uuid4()

        # Mock project lookup
        mock_project = MagicMock()
        mock_project.builder_id = builder_id

        # Mock CP lookup
        mock_cp = MagicMock()
        mock_cp.id = uuid.UUID(cp_id)

        call_count = [0]

        async def mock_execute(stmt):
            call_count[0] += 1
            result = MagicMock()
            if call_count[0] == 1:
                result.scalar_one_or_none = MagicMock(return_value=mock_project)
            else:
                result.scalar_one_or_none = MagicMock(return_value=mock_cp)
            return result

        admin_client._mock_db.execute = mock_execute

        response = await admin_client.post(
            "/api/v1/admin/partnerships",
            json={"cp_id": cp_id, "project_id": project_id},
            headers={"Authorization": f"Bearer {token}"},
        )

        assert response.status_code == 201
        data = response.json()
        assert "partnership_id" in data

    @pytest.mark.asyncio
    async def test_project_not_found_returns_404(self, admin_client):
        """Non-existent project returns 404."""
        token = _create_admin_token()

        mock_result = MagicMock()
        mock_result.scalar_one_or_none = MagicMock(return_value=None)
        admin_client._mock_db.execute = AsyncMock(return_value=mock_result)

        response = await admin_client.post(
            "/api/v1/admin/partnerships",
            json={"cp_id": str(uuid.uuid4()), "project_id": str(uuid.uuid4())},
            headers={"Authorization": f"Bearer {token}"},
        )

        assert response.status_code == 404
        assert "Project not found" in response.json()["error"]["message"]

    @pytest.mark.asyncio
    async def test_cp_not_found_returns_404(self, admin_client):
        """Non-existent CP returns 404."""
        token = _create_admin_token()

        mock_project = MagicMock()
        mock_project.builder_id = uuid.uuid4()

        call_count = [0]

        async def mock_execute(stmt):
            call_count[0] += 1
            result = MagicMock()
            if call_count[0] == 1:
                result.scalar_one_or_none = MagicMock(return_value=mock_project)
            else:
                result.scalar_one_or_none = MagicMock(return_value=None)
            return result

        admin_client._mock_db.execute = mock_execute

        response = await admin_client.post(
            "/api/v1/admin/partnerships",
            json={"cp_id": str(uuid.uuid4()), "project_id": str(uuid.uuid4())},
            headers={"Authorization": f"Bearer {token}"},
        )

        assert response.status_code == 404
        assert "CP not found" in response.json()["error"]["message"]

    @pytest.mark.asyncio
    async def test_duplicate_partnership_returns_409(self, admin_client):
        """Duplicate CP-project partnership returns 409."""
        token = _create_admin_token()
        cp_id = str(uuid.uuid4())
        project_id = str(uuid.uuid4())

        mock_project = MagicMock()
        mock_project.builder_id = uuid.uuid4()
        mock_cp = MagicMock()

        call_count = [0]

        async def mock_execute(stmt):
            call_count[0] += 1
            result = MagicMock()
            if call_count[0] == 1:
                result.scalar_one_or_none = MagicMock(return_value=mock_project)
            else:
                result.scalar_one_or_none = MagicMock(return_value=mock_cp)
            return result

        admin_client._mock_db.execute = mock_execute
        admin_client._mock_db.flush = AsyncMock(
            side_effect=IntegrityError("duplicate", {}, Exception())
        )

        response = await admin_client.post(
            "/api/v1/admin/partnerships",
            json={"cp_id": cp_id, "project_id": project_id},
            headers={"Authorization": f"Bearer {token}"},
        )

        assert response.status_code == 409

    @pytest.mark.asyncio
    async def test_cp_cannot_create_partnership_403(self, admin_client):
        """CP user gets 403 when trying to create partnership."""
        token = _create_cp_token()

        response = await admin_client.post(
            "/api/v1/admin/partnerships",
            json={"cp_id": str(uuid.uuid4()), "project_id": str(uuid.uuid4())},
            headers={"Authorization": f"Bearer {token}"},
        )

        assert response.status_code == 403


# --- Partnership Removal Tests ---


class TestDeletePartnership:
    """Tests for DELETE /api/v1/admin/partnerships/{partnership_id}."""

    @pytest.mark.asyncio
    async def test_admin_deletes_partnership_204(self, admin_client):
        """Admin can remove a partnership."""
        token = _create_admin_token()
        partnership_id = str(uuid.uuid4())

        mock_partnership = MagicMock()
        mock_result = MagicMock()
        mock_result.scalar_one_or_none = MagicMock(return_value=mock_partnership)
        admin_client._mock_db.execute = AsyncMock(return_value=mock_result)

        response = await admin_client.delete(
            f"/api/v1/admin/partnerships/{partnership_id}",
            headers={"Authorization": f"Bearer {token}"},
        )

        assert response.status_code == 204

    @pytest.mark.asyncio
    async def test_partnership_not_found_returns_404(self, admin_client):
        """Non-existent partnership returns 404."""
        token = _create_admin_token()
        partnership_id = str(uuid.uuid4())

        mock_result = MagicMock()
        mock_result.scalar_one_or_none = MagicMock(return_value=None)
        admin_client._mock_db.execute = AsyncMock(return_value=mock_result)

        response = await admin_client.delete(
            f"/api/v1/admin/partnerships/{partnership_id}",
            headers={"Authorization": f"Bearer {token}"},
        )

        assert response.status_code == 404

    @pytest.mark.asyncio
    async def test_cp_cannot_delete_partnership_403(self, admin_client):
        """CP user gets 403 when trying to delete partnership."""
        token = _create_cp_token()
        partnership_id = str(uuid.uuid4())

        response = await admin_client.delete(
            f"/api/v1/admin/partnerships/{partnership_id}",
            headers={"Authorization": f"Bearer {token}"},
        )

        assert response.status_code == 403
