"""WebSocket handler for tour chat with inline lead scoring.

Provides real-time chat with Priya (AI avatar) and handles:
- Connection management with JWT session_token validation
- Chat message handling with RAG integration (Bedrock KB)
- Inline lead scoring after question classification
- Keepalive ping every 30 seconds
- 5-minute idle timeout
"""

import asyncio
import json
import logging
import time
from typing import Any

from fastapi import APIRouter, WebSocket, WebSocketDisconnect, Query
from jose import JWTError, jwt

from app.core.config import settings
from app.services.dynamodb_session import SessionRepository
from app.services.lead_engine import (
    calculate_score,
    check_and_alert,
    classify_question,
    persist_score_update,
)

logger = logging.getLogger(__name__)

router = APIRouter()

# Connection registry: session_id -> WebSocket
_active_connections: dict[str, WebSocket] = {}

KEEPALIVE_INTERVAL = 30  # seconds
IDLE_TIMEOUT = 300  # 5 minutes
MAX_MESSAGE_LENGTH = 500
MIN_MESSAGE_LENGTH = 1
KB_TIMEOUT = 10  # seconds


class ConnectionManager:
    """Manage active WebSocket connections."""

    def __init__(self):
        self._connections: dict[str, WebSocket] = {}

    async def connect(self, session_id: str, websocket: WebSocket) -> None:
        """Register a WebSocket connection."""
        await websocket.accept()
        self._connections[session_id] = websocket

    def disconnect(self, session_id: str) -> None:
        """Remove a WebSocket connection."""
        self._connections.pop(session_id, None)

    def get_connection(self, session_id: str) -> WebSocket | None:
        """Get active connection for a session."""
        return self._connections.get(session_id)

    @property
    def active_connections(self) -> dict[str, WebSocket]:
        """Get all active connections."""
        return self._connections


manager = ConnectionManager()


def validate_session_token(token: str) -> dict | None:
    """Validate a JWT session token.

    Args:
        token: JWT token string.

    Returns:
        Decoded payload dict or None if invalid.
    """
    try:
        payload = jwt.decode(
            token,
            settings.jwt_secret_key,
            algorithms=[settings.jwt_algorithm],
        )
        return payload
    except JWTError:
        return None


async def retrieve_and_generate_response(
    session_id: str, message: str, project_id: str
) -> str:
    """Call Bedrock Knowledge Base for RAG response.

    Currently returns a placeholder — real Bedrock integration comes later.

    Args:
        session_id: The buyer session identifier.
        message: The user's chat message.
        project_id: The project ID for KB context.

    Returns:
        Generated response text.
    """
    # Placeholder for Bedrock KB integration
    # Real implementation will call bedrock-agent-runtime RetrieveAndGenerate
    await asyncio.sleep(0.1)  # Simulate minimal latency
    return (
        f"Thank you for your question about this property. "
        f"I'd be happy to help you learn more. "
        f"Please feel free to ask me anything about the project features, "
        f"pricing, or amenities."
    )


async def handle_chat_message(
    websocket: WebSocket,
    session_id: str,
    message: str,
    session: dict[str, Any],
) -> None:
    """Process a chat message with RAG and inline scoring.

    Args:
        websocket: Active WebSocket connection.
        session_id: The buyer session identifier.
        message: The chat message text.
        session: Current session data from DynamoDB.
    """
    # Validate message length
    if len(message) < MIN_MESSAGE_LENGTH or len(message) > MAX_MESSAGE_LENGTH:
        await websocket.send_json({
            "type": "error",
            "code": "INVALID_MESSAGE",
            "message": f"Message must be between {MIN_MESSAGE_LENGTH} and {MAX_MESSAGE_LENGTH} characters.",
        })
        return

    # Classify the question for lead scoring
    signal_type, weight = classify_question(message)

    # Send talking_start
    await websocket.send_json({"type": "talking_start"})

    # Call Bedrock KB with timeout
    project_id = session.get("project_id", "")
    try:
        response_text = await asyncio.wait_for(
            retrieve_and_generate_response(session_id, message, project_id),
            timeout=KB_TIMEOUT,
        )
    except asyncio.TimeoutError:
        response_text = (
            "I apologize, but I'm having trouble retrieving that information right now. "
            "Please try again in a moment, or feel free to ask a different question."
        )
        await websocket.send_json({
            "type": "error",
            "code": "KB_TIMEOUT",
            "message": "Knowledge base response timed out.",
        })

    # Stream response tokens
    tokens = response_text.split(" ")
    for i, token in enumerate(tokens):
        prefix = " " if i > 0 else ""
        await websocket.send_json({
            "type": "chat_token",
            "token": prefix + token,
            "sequence": i + 1,
        })

    # Send chat_end with full response
    await websocket.send_json({
        "type": "chat_end",
        "full_response": response_text,
    })

    # Send talking_end
    await websocket.send_json({"type": "talking_end"})

    # Inline lead scoring
    if signal_type:
        existing_signals = session.get("signals", {})
        signal_list = [{"type": k} for k in existing_signals.keys()]
        signal_list.append({"type": signal_type})

        score, classification, breakdown = calculate_score(signal_list)

        # Persist score update (DynamoDB → RDS dual-write)
        await persist_score_update(
            session_id=session_id,
            cp_id=session.get("cp_id", ""),
            project_id=project_id,
            score=score,
            classification=classification,
            signals=breakdown,
        )

        # Send score_update event
        await websocket.send_json({
            "type": "score_update",
            "score": score,
            "classification": classification,
        })

        # Check and alert if threshold crossed
        await check_and_alert(
            session_id=session_id,
            score=score,
            classification=classification,
            cp_id=session.get("cp_id", ""),
            project_id=project_id,
        )

    # Record chat event in session history
    repo = SessionRepository()
    await repo.add_event(
        session_id=session_id,
        event_type="chat_message",
        data={"message": message, "signal": signal_type},
    )


@router.websocket("/tour/{session_id}")
async def websocket_tour(
    websocket: WebSocket,
    session_id: str,
    session_token: str = Query(default=""),
) -> None:
    """WebSocket endpoint for tour chat.

    Handles connection lifecycle with JWT validation, keepalive pings,
    idle timeout, and chat message processing.

    Args:
        websocket: The WebSocket connection.
        session_id: The buyer session identifier from the URL path.
        session_token: JWT token passed as query parameter.
    """
    # Validate session token
    if not session_token:
        await websocket.close(code=4001, reason="Missing session_token")
        return

    payload = validate_session_token(session_token)
    if payload is None:
        await websocket.close(code=4001, reason="Invalid session_token")
        return

    # Validate session exists in DynamoDB
    repo = SessionRepository()
    session = await repo.get_session(session_id)
    if session is None:
        await websocket.close(code=4004, reason="Session not found")
        return

    # Accept connection
    await manager.connect(session_id, websocket)
    last_activity = time.time()

    try:
        # Start keepalive task
        keepalive_task = asyncio.create_task(_keepalive(websocket, session_id))

        while True:
            # Wait for message with idle timeout
            try:
                raw_message = await asyncio.wait_for(
                    websocket.receive_text(),
                    timeout=IDLE_TIMEOUT,
                )
            except asyncio.TimeoutError:
                # Idle timeout — close connection
                await websocket.send_json({
                    "type": "error",
                    "code": "IDLE_TIMEOUT",
                    "message": "Connection closed due to inactivity.",
                })
                break

            last_activity = time.time()

            # Parse message
            try:
                data = json.loads(raw_message)
            except json.JSONDecodeError:
                await websocket.send_json({
                    "type": "error",
                    "code": "INVALID_JSON",
                    "message": "Message must be valid JSON.",
                })
                continue

            action = data.get("action", "")

            if action == "chat":
                message_text = data.get("message", "")
                # Refresh session data for latest signals
                session = await repo.get_session(session_id) or session
                await handle_chat_message(websocket, session_id, message_text, session)
            elif action == "room_navigate":
                # Room navigation is handled by the tours REST endpoint
                await websocket.send_json({
                    "type": "ack",
                    "action": "room_navigate",
                })
            else:
                await websocket.send_json({
                    "type": "error",
                    "code": "UNKNOWN_ACTION",
                    "message": f"Unknown action: {action}",
                })

    except WebSocketDisconnect:
        logger.info(f"WebSocket disconnected: session_id={session_id}")
    except Exception as e:
        logger.error(f"WebSocket error for session {session_id}: {e}", exc_info=True)
    finally:
        manager.disconnect(session_id)
        # Cancel keepalive task
        if "keepalive_task" in locals():
            keepalive_task.cancel()
            try:
                await keepalive_task
            except asyncio.CancelledError:
                pass


async def _keepalive(websocket: WebSocket, session_id: str) -> None:
    """Send keepalive ping every 30 seconds.

    Args:
        websocket: The WebSocket connection.
        session_id: The session identifier for logging.
    """
    try:
        while True:
            await asyncio.sleep(KEEPALIVE_INTERVAL)
            try:
                await websocket.send_json({"type": "ping"})
            except Exception:
                break
    except asyncio.CancelledError:
        pass
