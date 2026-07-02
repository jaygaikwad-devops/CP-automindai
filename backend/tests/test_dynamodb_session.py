"""Tests for DynamoDB session repository.

Uses unittest.mock to mock the aioboto3 DynamoDB resource for testing
session CRUD operations, event tracking, and GSI1 queries.
"""

import time
from contextlib import asynccontextmanager
from decimal import Decimal
from unittest.mock import AsyncMock, MagicMock, patch

import pytest

from app.services.dynamodb_session import SessionRepository, TTL_30_DAYS, reset_session

TABLE_NAME = "automind_sessions_test"


class FakeDynamoDBTable:
    """In-memory DynamoDB table simulator for testing."""

    def __init__(self):
        self._items: dict[tuple[str, str], dict] = {}
        self._gsi1_items: dict[tuple[str, str], dict] = {}

    async def put_item(self, Item: dict):
        pk = Item["PK"]
        sk = Item["SK"]
        self._items[(pk, sk)] = Item
        if "GSI1PK" in Item and "GSI1SK" in Item:
            self._gsi1_items[(pk, sk)] = Item

    async def get_item(self, Key: dict):
        pk = Key["PK"]
        sk = Key["SK"]
        item = self._items.get((pk, sk))
        if item:
            return {"Item": item}
        return {}

    async def update_item(
        self,
        Key: dict,
        UpdateExpression: str,
        ExpressionAttributeValues: dict,
        ReturnValues: str = "ALL_NEW",
    ):
        pk = Key["PK"]
        sk = Key["SK"]
        item = self._items.get((pk, sk))
        if item is None:
            return {}

        # Parse simple SET expressions
        # "SET score = :score, classification = :classification, ..."
        set_part = UpdateExpression.replace("SET ", "")
        assignments = [a.strip() for a in set_part.split(",")]
        for assignment in assignments:
            attr_name, placeholder = [x.strip() for x in assignment.split("=")]
            item[attr_name] = ExpressionAttributeValues[placeholder]

        self._items[(pk, sk)] = item
        # Update GSI1 index
        if "GSI1PK" in item and "GSI1SK" in item:
            self._gsi1_items[(pk, sk)] = item

        return {"Attributes": item}

    async def query(self, **kwargs):
        key_condition = kwargs.get("KeyConditionExpression")
        index_name = kwargs.get("IndexName")
        limit = kwargs.get("Limit")

        results = []

        # Extract values from boto3 condition expressions
        # key_condition is an And object with _values = (Equals, BeginsWith)
        pk_condition = key_condition._values[0]  # Equals
        sk_condition = key_condition._values[1]  # BeginsWith

        pk_val = pk_condition._values[1]  # (Key, value) -> value
        sk_prefix = sk_condition._values[1]  # (Key, value) -> value

        if index_name == "GSI1":
            # GSI1 query: filter by GSI1PK and GSI1SK prefix
            for (pk, sk), item in self._gsi1_items.items():
                if item.get("GSI1PK") == pk_val and item.get(
                    "GSI1SK", ""
                ).startswith(sk_prefix):
                    results.append(item)

            # Sort by GSI1SK
            results.sort(key=lambda x: x.get("GSI1SK", ""))
        else:
            # Main table query
            for (pk, sk), item in self._items.items():
                if pk == pk_val and sk.startswith(sk_prefix):
                    results.append(item)

            # Sort by SK
            results.sort(key=lambda x: x.get("SK", ""))

        if limit:
            results = results[:limit]

        return {"Items": results}


class FakeDynamoDBResource:
    """Fake DynamoDB resource that returns the shared fake table."""

    def __init__(self, table: FakeDynamoDBTable):
        self._table = table

    async def Table(self, name: str):
        return self._table

    async def __aenter__(self):
        return self

    async def __aexit__(self, *args):
        pass


@pytest.fixture
def fake_table():
    """Create a fake in-memory DynamoDB table."""
    return FakeDynamoDBTable()


@pytest.fixture
def repo(fake_table):
    """Create a SessionRepository with mocked aioboto3 session."""
    reset_session()
    repository = SessionRepository(table_name=TABLE_NAME)

    # Patch _get_session to return a mock that yields our fake resource
    fake_resource = FakeDynamoDBResource(fake_table)

    @asynccontextmanager
    async def mock_resource(*args, **kwargs):
        yield fake_resource

    mock_session = MagicMock()
    mock_session.resource = mock_resource

    with patch("app.services.dynamodb_session._get_session", return_value=mock_session):
        yield repository

    reset_session()


@pytest.mark.asyncio
class TestCreateSession:
    """Tests for create_session method."""

    async def test_create_session_returns_item(self, repo):
        """Should create a session and return the full item."""
        result = await repo.create_session(
            session_id="sess-001",
            cp_id="cp-123",
            project_id="proj-456",
            link_id="link-789",
            device_type="mobile",
            user_agent="Mozilla/5.0",
            referrer="https://example.com",
        )

        assert result["session_id"] == "sess-001"
        assert result["cp_id"] == "cp-123"
        assert result["project_id"] == "proj-456"
        assert result["link_id"] == "link-789"
        assert result["device_type"] == "mobile"
        assert result["user_agent"] == "Mozilla/5.0"
        assert result["referrer"] == "https://example.com"
        assert result["score"] == 0
        assert result["classification"] == "cold"
        assert result["signals"] == {}
        assert result["alert_sent"] is False
        assert result["PK"] == "SESSION#sess-001"
        assert result["SK"] == "META"
        assert result["GSI1PK"] == "CP#cp-123"
        assert result["GSI1SK"].startswith("SCORE#10#")

    async def test_create_session_sets_ttl(self, repo):
        """Should set TTL to approximately 30 days from now."""
        before = int(time.time())
        result = await repo.create_session(
            session_id="sess-002",
            cp_id="cp-123",
            project_id="proj-456",
            link_id="link-789",
        )
        after = int(time.time())

        assert before + TTL_30_DAYS <= result["ttl"] <= after + TTL_30_DAYS

    async def test_create_session_defaults(self, repo):
        """Should use empty string defaults for optional fields."""
        result = await repo.create_session(
            session_id="sess-003",
            cp_id="cp-123",
            project_id="proj-456",
            link_id="link-789",
        )

        assert result["device_type"] == ""
        assert result["user_agent"] == ""
        assert result["referrer"] == ""


@pytest.mark.asyncio
class TestGetSession:
    """Tests for get_session method."""

    async def test_get_existing_session(self, repo):
        """Should retrieve a previously created session."""
        await repo.create_session(
            session_id="sess-get-001",
            cp_id="cp-100",
            project_id="proj-200",
            link_id="link-300",
            device_type="desktop",
        )

        result = await repo.get_session("sess-get-001")

        assert result is not None
        assert result["session_id"] == "sess-get-001"
        assert result["cp_id"] == "cp-100"
        assert result["device_type"] == "desktop"

    async def test_get_nonexistent_session(self, repo):
        """Should return None for a session that doesn't exist."""
        result = await repo.get_session("nonexistent-session")
        assert result is None


@pytest.mark.asyncio
class TestUpdateScore:
    """Tests for update_score method."""

    async def test_update_score_success(self, repo):
        """Should update score, classification, signals, and GSI1SK."""
        await repo.create_session(
            session_id="sess-score-001",
            cp_id="cp-100",
            project_id="proj-200",
            link_id="link-300",
        )

        result = await repo.update_score(
            session_id="sess-score-001",
            score=8,
            classification="hot",
            signals={"pages_viewed": 5, "chat_engaged": True},
            alert_sent=True,
        )

        assert result is not None
        assert result["score"] == 8
        assert result["classification"] == "hot"
        assert result["signals"] == {"pages_viewed": 5, "chat_engaged": True}
        assert result["alert_sent"] is True
        # GSI1SK should reflect inverted score: 10 - 8 = 02
        assert "SCORE#02#" in result["GSI1SK"]

    async def test_update_score_nonexistent(self, repo):
        """Should return None when session doesn't exist."""
        result = await repo.update_score(
            session_id="nonexistent",
            score=5,
            classification="warm",
            signals={},
        )
        assert result is None

    async def test_update_score_preserves_created_at(self, repo):
        """Should preserve the original created_at in GSI1SK."""
        await repo.create_session(
            session_id="sess-preserve",
            cp_id="cp-100",
            project_id="proj-200",
            link_id="link-300",
        )
        session = await repo.get_session("sess-preserve")
        original_created_at = session["created_at"]

        result = await repo.update_score(
            session_id="sess-preserve",
            score=7,
            classification="hot",
            signals={},
        )

        # GSI1SK should contain original created_at
        assert original_created_at in result["GSI1SK"]


@pytest.mark.asyncio
class TestAddEvent:
    """Tests for add_event method."""

    async def test_add_event_returns_item(self, repo):
        """Should create an event item with correct structure."""
        result = await repo.add_event(
            session_id="sess-evt-001",
            event_type="page_view",
            data={"page": "/floor-plan", "duration_ms": 3200},
        )

        assert result["PK"] == "SESSION#sess-evt-001"
        assert result["SK"].startswith("EVENT#")
        assert "page_view" in result["SK"]
        assert result["type"] == "page_view"
        assert result["data"] == {"page": "/floor-plan", "duration_ms": 3200}
        assert "timestamp" in result

    async def test_add_event_sets_ttl(self, repo):
        """Should set TTL on event items."""
        before = int(time.time())
        result = await repo.add_event(
            session_id="sess-evt-002",
            event_type="chat_message",
            data={"message": "Hello"},
        )
        after = int(time.time())

        assert before + TTL_30_DAYS <= result["ttl"] <= after + TTL_30_DAYS


@pytest.mark.asyncio
class TestGetSessionEvents:
    """Tests for get_session_events method."""

    async def test_get_events_empty(self, repo):
        """Should return empty list when no events exist."""
        result = await repo.get_session_events("sess-no-events")
        assert result == []

    async def test_get_events_returns_sorted(self, repo):
        """Should return events sorted by timestamp."""
        import asyncio

        # Add events with slight delays to ensure different timestamps
        await repo.add_event("sess-multi", "page_view", {"page": "/home"})
        await asyncio.sleep(0.01)
        await repo.add_event("sess-multi", "chat_start", {"agent": "ai"})
        await asyncio.sleep(0.01)
        await repo.add_event("sess-multi", "page_view", {"page": "/pricing"})

        events = await repo.get_session_events("sess-multi")

        assert len(events) == 3
        assert events[0]["type"] == "page_view"
        assert events[1]["type"] == "chat_start"
        assert events[2]["type"] == "page_view"
        # Verify SK ordering
        assert events[0]["SK"] < events[1]["SK"] < events[2]["SK"]


@pytest.mark.asyncio
class TestGetCpHotLeads:
    """Tests for get_cp_hot_leads method."""

    async def test_get_leads_sorted_by_score(self, repo):
        """Should return leads sorted by score descending (highest first)."""
        # Create sessions with different scores
        await repo.create_session(
            session_id="low-score",
            cp_id="cp-leads",
            project_id="proj-1",
            link_id="link-1",
        )
        await repo.create_session(
            session_id="high-score",
            cp_id="cp-leads",
            project_id="proj-1",
            link_id="link-2",
        )
        await repo.create_session(
            session_id="mid-score",
            cp_id="cp-leads",
            project_id="proj-1",
            link_id="link-3",
        )

        # Update scores
        await repo.update_score("low-score", 2, "cold", {})
        await repo.update_score("high-score", 9, "hot", {"chat": True})
        await repo.update_score("mid-score", 5, "warm", {})

        leads = await repo.get_cp_hot_leads("cp-leads")

        assert len(leads) == 3
        # Highest score first (inverted: 10-9=01 < 10-5=05 < 10-2=08)
        assert leads[0]["session_id"] == "high-score"
        assert leads[1]["session_id"] == "mid-score"
        assert leads[2]["session_id"] == "low-score"

    async def test_get_leads_respects_limit(self, repo):
        """Should respect the limit parameter."""
        for i in range(5):
            await repo.create_session(
                session_id=f"sess-limit-{i}",
                cp_id="cp-limit",
                project_id="proj-1",
                link_id=f"link-{i}",
            )

        leads = await repo.get_cp_hot_leads("cp-limit", limit=3)
        assert len(leads) == 3

    async def test_get_leads_empty_for_unknown_cp(self, repo):
        """Should return empty list for CP with no sessions."""
        leads = await repo.get_cp_hot_leads("cp-unknown")
        assert leads == []

    async def test_get_leads_filters_by_cp(self, repo):
        """Should only return sessions for the specified CP."""
        await repo.create_session(
            session_id="sess-cp1",
            cp_id="cp-alpha",
            project_id="proj-1",
            link_id="link-1",
        )
        await repo.create_session(
            session_id="sess-cp2",
            cp_id="cp-beta",
            project_id="proj-1",
            link_id="link-2",
        )

        leads_alpha = await repo.get_cp_hot_leads("cp-alpha")
        leads_beta = await repo.get_cp_hot_leads("cp-beta")

        assert len(leads_alpha) == 1
        assert leads_alpha[0]["session_id"] == "sess-cp1"
        assert len(leads_beta) == 1
        assert leads_beta[0]["session_id"] == "sess-cp2"
