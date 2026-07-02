"""Tests for WebSocket tour chat endpoint.

Tests connection management, chat message handling, validation,
inline scoring, and keepalive/timeout behaviour.
"""

import json
from datetime import timedelta
from unittest.mock import AsyncMock, MagicMock, patch

import pytest
from httpx import ASGITransport, AsyncClient
from starlette.testclient import TestClient

from app.core.security import create_access_token
from app.main import app


def _create_test_token(session_id: str = "test-session-001") -> str:
    """Create a valid JWT for testing."""
    return create_access_token(
        data={"sub": session_id, "type": "session"},
        expires_delta=timedelta(hours=1),
    )


@pytest.fixture
def mock_session_repo():
    """Mock SessionRepository for WebSocket tests."""
    mock_repo = MagicMock()

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
    mock_repo.add_event = AsyncMock(return_value={})
    mock_repo.update_score = AsyncMock(return_value=session_data)

    return mock_repo


@pytest.fixture
def patch_ws_dependencies(mock_session_repo):
    """Patch all dependencies for WebSocket tests."""
    with patch(
        "app.api.websocket.SessionRepository", return_value=mock_session_repo
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
    ), patch(
        "app.services.notifications.send_hot_lead_alert", new_callable=AsyncMock
    ):
        yield mock_session_repo


class TestWebSocketConnection:
    """Tests for WebSocket connection management."""

    def test_connect_with_valid_token(self, patch_ws_dependencies):
        """Should accept connection with valid session_token."""
        token = _create_test_token()
        client = TestClient(app)

        with client.websocket_connect(
            f"/ws/tour/test-session-001?session_token={token}"
        ) as ws:
            # Connection accepted — send a message to verify
            ws.send_json({"action": "chat", "message": "Hello"})
            # Should get talking_start as first response
            data = ws.receive_json()
            assert data["type"] == "talking_start"

    def test_connect_without_token_closes(self, patch_ws_dependencies):
        """Should close connection when session_token is missing."""
        client = TestClient(app)

        with pytest.raises(Exception):
            with client.websocket_connect("/ws/tour/test-session-001") as ws:
                ws.receive_json()

    def test_connect_with_invalid_token_closes(self, patch_ws_dependencies):
        """Should close connection when session_token is invalid."""
        client = TestClient(app)

        with pytest.raises(Exception):
            with client.websocket_connect(
                "/ws/tour/test-session-001?session_token=invalid-token"
            ) as ws:
                ws.receive_json()

    def test_connect_with_nonexistent_session_closes(self, patch_ws_dependencies):
        """Should close connection when session doesn't exist in DynamoDB."""
        patch_ws_dependencies.get_session = AsyncMock(return_value=None)
        token = _create_test_token("nonexistent")
        client = TestClient(app)

        with pytest.raises(Exception):
            with client.websocket_connect(
                f"/ws/tour/nonexistent?session_token={token}"
            ) as ws:
                ws.receive_json()


class TestWebSocketChat:
    """Tests for chat message handling."""

    def test_chat_message_produces_response_flow(self, patch_ws_dependencies):
        """Should produce talking_start → tokens → chat_end → talking_end flow."""
        token = _create_test_token()
        client = TestClient(app)

        with client.websocket_connect(
            f"/ws/tour/test-session-001?session_token={token}"
        ) as ws:
            ws.send_json({"action": "chat", "message": "Tell me about the property"})

            # Expect talking_start
            msg = ws.receive_json()
            assert msg["type"] == "talking_start"

            # Collect tokens until chat_end
            tokens = []
            while True:
                msg = ws.receive_json()
                if msg["type"] == "chat_token":
                    tokens.append(msg["token"])
                    assert "sequence" in msg
                elif msg["type"] == "chat_end":
                    assert "full_response" in msg
                    break

            # Expect talking_end
            msg = ws.receive_json()
            assert msg["type"] == "talking_end"

            # Tokens should form the response
            assert len(tokens) > 0

    def test_empty_message_returns_error(self, patch_ws_dependencies):
        """Should return error for empty message."""
        token = _create_test_token()
        client = TestClient(app)

        with client.websocket_connect(
            f"/ws/tour/test-session-001?session_token={token}"
        ) as ws:
            ws.send_json({"action": "chat", "message": ""})

            msg = ws.receive_json()
            assert msg["type"] == "error"
            assert msg["code"] == "INVALID_MESSAGE"

    def test_long_message_returns_error(self, patch_ws_dependencies):
        """Should return error for message > 500 chars."""
        token = _create_test_token()
        client = TestClient(app)

        with client.websocket_connect(
            f"/ws/tour/test-session-001?session_token={token}"
        ) as ws:
            ws.send_json({"action": "chat", "message": "x" * 501})

            msg = ws.receive_json()
            assert msg["type"] == "error"
            assert msg["code"] == "INVALID_MESSAGE"

    def test_price_question_triggers_score_update(self, patch_ws_dependencies):
        """Should send score_update when price question is detected."""
        token = _create_test_token()
        client = TestClient(app)

        with client.websocket_connect(
            f"/ws/tour/test-session-001?session_token={token}"
        ) as ws:
            ws.send_json({"action": "chat", "message": "What is the price?"})

            # Consume talking_start, tokens, chat_end, talking_end
            messages = []
            for _ in range(50):  # Safety limit
                msg = ws.receive_json()
                messages.append(msg)
                if msg["type"] == "score_update":
                    break

            # Should contain score_update
            score_updates = [m for m in messages if m["type"] == "score_update"]
            assert len(score_updates) == 1
            assert "score" in score_updates[0]
            assert "classification" in score_updates[0]

    def test_invalid_json_returns_error(self, patch_ws_dependencies):
        """Should return error for invalid JSON."""
        token = _create_test_token()
        client = TestClient(app)

        with client.websocket_connect(
            f"/ws/tour/test-session-001?session_token={token}"
        ) as ws:
            ws.send_text("not valid json {{{")

            msg = ws.receive_json()
            assert msg["type"] == "error"
            assert msg["code"] == "INVALID_JSON"

    def test_unknown_action_returns_error(self, patch_ws_dependencies):
        """Should return error for unknown action."""
        token = _create_test_token()
        client = TestClient(app)

        with client.websocket_connect(
            f"/ws/tour/test-session-001?session_token={token}"
        ) as ws:
            ws.send_json({"action": "unknown_action"})

            msg = ws.receive_json()
            assert msg["type"] == "error"
            assert msg["code"] == "UNKNOWN_ACTION"

    def test_room_navigate_returns_ack(self, patch_ws_dependencies):
        """Should acknowledge room_navigate action."""
        token = _create_test_token()
        client = TestClient(app)

        with client.websocket_connect(
            f"/ws/tour/test-session-001?session_token={token}"
        ) as ws:
            ws.send_json({"action": "room_navigate", "room_index": 3})

            msg = ws.receive_json()
            assert msg["type"] == "ack"
            assert msg["action"] == "room_navigate"
