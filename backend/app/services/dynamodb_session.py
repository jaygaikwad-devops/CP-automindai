"""DynamoDB session repository for AutoMind AI Platform.

Handles session CRUD, event tracking, and GSI1 queries for CP hot leads.
Uses aioboto3 for async DynamoDB access with connection reuse.
"""

import time
from datetime import datetime, timezone
from typing import Any

import aioboto3
from boto3.dynamodb.conditions import Key

from app.core.config import settings

# Module-level session for connection reuse across requests
_aioboto3_session: aioboto3.Session | None = None

TTL_30_DAYS = 30 * 24 * 60 * 60


def _get_session() -> aioboto3.Session:
    """Get or create a shared aioboto3 session for connection reuse."""
    global _aioboto3_session
    if _aioboto3_session is None:
        _aioboto3_session = aioboto3.Session(
            aws_access_key_id=settings.aws_access_key_id or None,
            aws_secret_access_key=settings.aws_secret_access_key or None,
            region_name=settings.aws_region,
        )
    return _aioboto3_session


def reset_session() -> None:
    """Reset the shared session. Useful for testing or credential rotation."""
    global _aioboto3_session
    _aioboto3_session = None


class SessionRepository:
    """DynamoDB repository for buyer session data.

    Manages session metadata and events in the automind_sessions table.
    Uses GSI1 for querying CP hot leads sorted by score.
    """

    def __init__(self, table_name: str | None = None) -> None:
        self._table_name = table_name or settings.dynamodb_table_name

    def _get_resource_kwargs(self) -> dict[str, Any]:
        """Build kwargs for the DynamoDB resource context manager."""
        kwargs: dict[str, Any] = {
            "region_name": settings.aws_region,
        }
        if settings.aws_access_key_id:
            kwargs["aws_access_key_id"] = settings.aws_access_key_id
        if settings.aws_secret_access_key:
            kwargs["aws_secret_access_key"] = settings.aws_secret_access_key
        return kwargs

    async def create_session(
        self,
        session_id: str,
        cp_id: str,
        project_id: str,
        link_id: str,
        device_type: str = "",
        user_agent: str = "",
        referrer: str = "",
    ) -> dict[str, Any]:
        """Create a new buyer session in DynamoDB.

        Args:
            session_id: Unique session identifier.
            cp_id: Channel partner ID owning this session.
            project_id: Project ID associated with the session.
            link_id: Share link ID that initiated the session.
            device_type: Device type (mobile, desktop, tablet).
            user_agent: Browser user agent string.
            referrer: HTTP referrer URL.

        Returns:
            The created session item as a dict.
        """
        now = datetime.now(timezone.utc).isoformat()
        ttl = int(time.time()) + TTL_30_DAYS

        # Initial score is 0, classification is "cold"
        initial_score = 0
        classification = "cold"

        # GSI1SK: SCORE#{inverted_score_zero_padded}#{created_at}
        inverted_score = 10 - initial_score
        gsi1sk = f"SCORE#{inverted_score:02d}#{now}"

        item: dict[str, Any] = {
            "PK": f"SESSION#{session_id}",
            "SK": "META",
            "GSI1PK": f"CP#{cp_id}",
            "GSI1SK": gsi1sk,
            "session_id": session_id,
            "cp_id": cp_id,
            "project_id": project_id,
            "link_id": link_id,
            "score": initial_score,
            "classification": classification,
            "signals": {},
            "buyer_name": "",
            "buyer_phone": "",
            "device_type": device_type,
            "user_agent": user_agent,
            "referrer": referrer,
            "alert_sent": False,
            "created_at": now,
            "ttl": ttl,
        }

        session = _get_session()
        async with session.resource("dynamodb", **self._get_resource_kwargs()) as dynamodb:
            table = await dynamodb.Table(self._table_name)
            await table.put_item(Item=item)

        return item

    async def get_session(self, session_id: str) -> dict[str, Any] | None:
        """Retrieve a session's META item by session ID.

        Args:
            session_id: The session identifier.

        Returns:
            The session item dict, or None if not found.
        """
        session = _get_session()
        async with session.resource("dynamodb", **self._get_resource_kwargs()) as dynamodb:
            table = await dynamodb.Table(self._table_name)
            response = await table.get_item(
                Key={
                    "PK": f"SESSION#{session_id}",
                    "SK": "META",
                }
            )
        return response.get("Item")

    async def update_score(
        self,
        session_id: str,
        score: int,
        classification: str,
        signals: dict[str, Any],
        alert_sent: bool = False,
    ) -> dict[str, Any] | None:
        """Update a session's score, classification, signals, and alert status.

        Also updates GSI1SK to reflect the new score for sorted queries.

        Args:
            session_id: The session identifier.
            score: New engagement score (0-10).
            classification: Lead classification (cold, warm, hot).
            signals: Dict of signal data contributing to the score.
            alert_sent: Whether an alert has been sent for this session.

        Returns:
            The updated item attributes, or None if session not found.
        """
        # First get the session to retrieve created_at for GSI1SK rebuild
        existing = await self.get_session(session_id)
        if existing is None:
            return None

        created_at = existing["created_at"]
        inverted_score = 10 - score
        gsi1sk = f"SCORE#{inverted_score:02d}#{created_at}"

        session = _get_session()
        async with session.resource("dynamodb", **self._get_resource_kwargs()) as dynamodb:
            table = await dynamodb.Table(self._table_name)
            response = await table.update_item(
                Key={
                    "PK": f"SESSION#{session_id}",
                    "SK": "META",
                },
                UpdateExpression=(
                    "SET score = :score, classification = :classification, "
                    "signals = :signals, alert_sent = :alert_sent, GSI1SK = :gsi1sk"
                ),
                ExpressionAttributeValues={
                    ":score": score,
                    ":classification": classification,
                    ":signals": signals,
                    ":alert_sent": alert_sent,
                    ":gsi1sk": gsi1sk,
                },
                ReturnValues="ALL_NEW",
            )
        return response.get("Attributes")

    async def update_buyer_info(
        self,
        session_id: str,
        buyer_name: str | None = None,
        buyer_phone: str | None = None,
    ) -> None:
        """Update buyer contact information on a session.

        Called when buyer submits the contact/brochure form.

        Args:
            session_id: The session identifier.
            buyer_name: Buyer's name.
            buyer_phone: Buyer's phone number.
        """
        update_parts = []
        values = {}

        if buyer_name:
            update_parts.append("buyer_name = :bn")
            values[":bn"] = buyer_name
        if buyer_phone:
            update_parts.append("buyer_phone = :bp")
            values[":bp"] = buyer_phone

        if not update_parts:
            return

        session = _get_session()
        async with session.resource("dynamodb", **self._get_resource_kwargs()) as dynamodb:
            table = await dynamodb.Table(self._table_name)
            await table.update_item(
                Key={"PK": f"SESSION#{session_id}", "SK": "META"},
                UpdateExpression=f"SET {', '.join(update_parts)}",
                ExpressionAttributeValues=values,
            )

    async def add_event(
        self,
        session_id: str,
        event_type: str,
        data: dict[str, Any],
    ) -> dict[str, Any]:
        """Add an event to a session's event history.

        Args:
            session_id: The session identifier.
            event_type: Type of event (e.g., page_view, chat_message).
            data: Event-specific payload data.

        Returns:
            The created event item as a dict.
        """
        now = datetime.now(timezone.utc).isoformat()
        ttl = int(time.time()) + TTL_30_DAYS

        item: dict[str, Any] = {
            "PK": f"SESSION#{session_id}",
            "SK": f"EVENT#{now}#{event_type}",
            "type": event_type,
            "data": data,
            "timestamp": now,
            "ttl": ttl,
        }

        session = _get_session()
        async with session.resource("dynamodb", **self._get_resource_kwargs()) as dynamodb:
            table = await dynamodb.Table(self._table_name)
            await table.put_item(Item=item)

        return item

    async def get_session_events(self, session_id: str) -> list[dict[str, Any]]:
        """Get all events for a session, sorted by timestamp.

        Args:
            session_id: The session identifier.

        Returns:
            List of event items sorted by SK (timestamp ascending).
        """
        session = _get_session()
        async with session.resource("dynamodb", **self._get_resource_kwargs()) as dynamodb:
            table = await dynamodb.Table(self._table_name)
            response = await table.query(
                KeyConditionExpression=(
                    Key("PK").eq(f"SESSION#{session_id}")
                    & Key("SK").begins_with("EVENT#")
                ),
            )
        return response.get("Items", [])

    async def get_cp_hot_leads(
        self, cp_id: str, limit: int = 50
    ) -> list[dict[str, Any]]:
        """Query CP hot leads sorted by score (highest first).

        Uses GSI1 with GSI1PK = CP#{cp_id} and GSI1SK begins_with SCORE#.
        Results are sorted by inverted score so highest scores come first.

        Args:
            cp_id: Channel partner ID.
            limit: Maximum number of results to return (default 50).

        Returns:
            List of session META items sorted by score descending.
        """
        session = _get_session()
        async with session.resource("dynamodb", **self._get_resource_kwargs()) as dynamodb:
            table = await dynamodb.Table(self._table_name)
            response = await table.query(
                IndexName="GSI1",
                KeyConditionExpression=(
                    Key("GSI1PK").eq(f"CP#{cp_id}")
                    & Key("GSI1SK").begins_with("SCORE#")
                ),
                Limit=limit,
            )
        return response.get("Items", [])
