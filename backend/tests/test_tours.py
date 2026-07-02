"""Tests for Tour Events endpoint (POST /api/v1/tours/{session_id}/events).

Tests event validation, session lookup, score calculation, and response format.
"""

from contextlib import asynccontextmanager
from unittest.mock import AsyncMock, MagicMock, patch

import pytest
from httpx import ASGITransport, AsyncClient

from app.main import app


@pytest.fixture
def mock_session_repo():
    """Mock SessionRepository for testing without DynamoDB."""
    mock_repo = MagicMock()

    # Default session data
    session_data = {
        "session_id": "test-session-001",
        "cp_id": "cp-123",
        "project_id": "proj-456",
        "score": 0,
        "classification": "browsing",
        "signals": {},
        "alert_sent": False,
        "created_at": "2024-01-15T10:00:00Z",
        "PK": "SESSION#test-session-001",
        "SK": "META",
        "GSI1PK": "CP#cp-123",
        "GSI1SK": "SCORE#10#2024-01-15T10:00:00Z",
    }

    mock_repo.get_session = AsyncMock(return_value=session_data)
    mock_repo.add_event = AsyncMock(return_value={"PK": "SESSION#test-session-001", "SK": "EVENT#..."})
    mock_repo.update_score = AsyncMock(return_value=session_data)

    return mock_repo


@pytest.fixture
def patch_dependencies(mock_session_repo):
    """Patch DynamoDB and RDS dependencies for isolated testing."""
    with patch(
        "app.api.tours.SessionRepository", return_value=mock_session_repo
    ), patch(
        "app.services.dynamodb_session.SessionRepository.get_session",
        mock_session_repo.get_session,
    ), patch(
        "app.services.dynamodb_session.SessionRepository.add_event",
        mock_session_repo.add_event,
    ), patch(
        "app.services.dynamodb_session.SessionRepository.update_score",
        mock_session_repo.update_score,
    ), patch(
        "app.services.rds_leads.upsert_lead", new_callable=AsyncMock
    ) as mock_upsert, patch(
        "app.services.notifications.send_hot_lead_alert", new_callable=AsyncMock
    ) as mock_alert:
        yield {
            "repo": mock_session_repo,
            "upsert_lead": mock_upsert,
            "alert": mock_alert,
        }


@pytest.mark.asyncio
class TestPostTourEvent:
    """Tests for POST /api/v1/tours/{session_id}/events."""

    async def test_valid_room_revisited_event(self, patch_dependencies):
        """Should accept room_revisited event and return 202 with score."""
        async with AsyncClient(
            transport=ASGITransport(app=app), base_url="http://test"
        ) as client:
            response = await client.post(
                "/api/v1/tours/test-session-001/events",
                json={"type": "room_revisited", "data": {"room": "living_room"}},
            )

        assert response.status_code == 202
        data = response.json()
        assert "score" in data
        assert "classification" in data
        assert isinstance(data["score"], int)
        assert data["score"] >= 0

    async def test_valid_visit_booking_clicked(self, patch_dependencies):
        """Should accept visit_booking_clicked and return visit_booked classification."""
        async with AsyncClient(
            transport=ASGITransport(app=app), base_url="http://test"
        ) as client:
            response = await client.post(
                "/api/v1/tours/test-session-001/events",
                json={"type": "visit_booking_clicked", "data": {}},
            )

        assert response.status_code == 202
        data = response.json()
        assert data["score"] == 4
        assert data["classification"] == "visit_booked"

    async def test_valid_whatsapp_share_clicked(self, patch_dependencies):
        """Should accept whatsapp_share_clicked event."""
        async with AsyncClient(
            transport=ASGITransport(app=app), base_url="http://test"
        ) as client:
            response = await client.post(
                "/api/v1/tours/test-session-001/events",
                json={"type": "whatsapp_share_clicked", "data": {}},
            )

        assert response.status_code == 202
        data = response.json()
        assert data["score"] == 1

    async def test_room_viewed_returns_current_score(self, patch_dependencies):
        """room_viewed is tracked but doesn't directly score."""
        async with AsyncClient(
            transport=ASGITransport(app=app), base_url="http://test"
        ) as client:
            response = await client.post(
                "/api/v1/tours/test-session-001/events",
                json={"type": "room_viewed", "data": {"room_index": 2}},
            )

        assert response.status_code == 202
        data = response.json()
        assert data["score"] == 0  # room_viewed doesn't score

    async def test_time_on_tour_under_3min(self, patch_dependencies):
        """time_on_tour under 3 minutes doesn't score."""
        async with AsyncClient(
            transport=ASGITransport(app=app), base_url="http://test"
        ) as client:
            response = await client.post(
                "/api/v1/tours/test-session-001/events",
                json={"type": "time_on_tour", "data": {"duration_seconds": 120}},
            )

        assert response.status_code == 202
        data = response.json()
        assert data["score"] == 0

    async def test_time_on_tour_over_3min_scores(self, patch_dependencies):
        """time_on_tour >= 3 minutes triggers time_on_tour_3min_plus signal."""
        async with AsyncClient(
            transport=ASGITransport(app=app), base_url="http://test"
        ) as client:
            response = await client.post(
                "/api/v1/tours/test-session-001/events",
                json={"type": "time_on_tour", "data": {"duration_seconds": 200}},
            )

        assert response.status_code == 202
        data = response.json()
        assert data["score"] == 2  # time_on_tour_3min_plus weight

    async def test_invalid_event_type_returns_422(self, patch_dependencies):
        """Should reject invalid event types with 422."""
        async with AsyncClient(
            transport=ASGITransport(app=app), base_url="http://test"
        ) as client:
            response = await client.post(
                "/api/v1/tours/test-session-001/events",
                json={"type": "invalid_event", "data": {}},
            )

        assert response.status_code == 422

    async def test_session_not_found_returns_404(self, patch_dependencies):
        """Should return 404 when session doesn't exist."""
        patch_dependencies["repo"].get_session = AsyncMock(return_value=None)

        async with AsyncClient(
            transport=ASGITransport(app=app), base_url="http://test"
        ) as client:
            response = await client.post(
                "/api/v1/tours/nonexistent-session/events",
                json={"type": "room_revisited", "data": {}},
            )

        assert response.status_code == 404

    async def test_missing_type_field_returns_422(self, patch_dependencies):
        """Should return 422 when type field is missing."""
        async with AsyncClient(
            transport=ASGITransport(app=app), base_url="http://test"
        ) as client:
            response = await client.post(
                "/api/v1/tours/test-session-001/events",
                json={"data": {}},
            )

        assert response.status_code == 422
