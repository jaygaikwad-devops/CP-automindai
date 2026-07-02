"""Tests for Redis cache layer.

Uses fakeredis for testing without a real Redis server.
"""

import pytest
import fakeredis.aioredis

from app.services.redis_cache import (
    DASHBOARD_STATS_TTL,
    OTP_RATE_TTL,
    SESSION_SCORE_TTL,
    TOUR_SCRIPT_TTL,
    RedisCache,
)


@pytest.fixture
async def cache():
    """Create a RedisCache instance backed by fakeredis."""
    redis_cache = RedisCache()
    # Replace the internal client with a fakeredis instance
    redis_cache._redis = fakeredis.aioredis.FakeRedis(
        encoding="utf-8",
        decode_responses=True,
    )
    yield redis_cache
    await redis_cache.disconnect()


@pytest.mark.asyncio
class TestSessionScoreCache:
    """Tests for session score cache operations."""

    async def test_get_session_score_miss(self, cache):
        """Should return None when session is not cached."""
        result = await cache.get_session_score("nonexistent-session")
        assert result is None

    async def test_set_and_get_session_score(self, cache):
        """Should store and retrieve session score data."""
        score_data = {
            "score": 7,
            "classification": "hot",
            "signals": ["page_view", "chat_engaged"],
            "last_event_at": "2024-01-15T10:30:00Z",
        }

        await cache.set_session_score("sess-001", score_data)
        result = await cache.get_session_score("sess-001")

        assert result == score_data
        assert result["score"] == 7
        assert result["classification"] == "hot"

    async def test_set_session_score_ttl(self, cache):
        """Should set 24h TTL on session score keys."""
        await cache.set_session_score("sess-ttl", {"score": 5})

        ttl = await cache.client.ttl("session:sess-ttl")
        assert ttl > 0
        assert ttl <= SESSION_SCORE_TTL

    async def test_invalidate_session_score(self, cache):
        """Should remove cached session score."""
        await cache.set_session_score("sess-del", {"score": 3})
        assert await cache.get_session_score("sess-del") is not None

        await cache.invalidate_session_score("sess-del")
        assert await cache.get_session_score("sess-del") is None

    async def test_invalidate_nonexistent_session(self, cache):
        """Should not raise when invalidating non-existent key."""
        # Should not raise
        await cache.invalidate_session_score("no-such-session")


@pytest.mark.asyncio
class TestTourScriptCache:
    """Tests for tour script cache operations."""

    async def test_get_tour_script_miss(self, cache):
        """Should return None when tour script is not cached."""
        result = await cache.get_tour_script("proj-nonexistent")
        assert result is None

    async def test_set_and_get_tour_script(self, cache):
        """Should store and retrieve tour script JSON."""
        tour_data = {
            "project_id": "proj-123",
            "slides": [
                {"type": "image", "url": "https://cdn.example.com/img1.jpg"},
                {"type": "video", "url": "https://cdn.example.com/vid1.mp4"},
            ],
            "narration": "Welcome to the project tour...",
        }

        await cache.set_tour_script("proj-123", tour_data)
        result = await cache.get_tour_script("proj-123")

        assert result == tour_data
        assert len(result["slides"]) == 2

    async def test_set_tour_script_ttl(self, cache):
        """Should set 1h TTL on tour script keys."""
        await cache.set_tour_script("proj-ttl", {"slides": []})

        ttl = await cache.client.ttl("tour:proj-ttl")
        assert ttl > 0
        assert ttl <= TOUR_SCRIPT_TTL

    async def test_invalidate_tour_script(self, cache):
        """Should remove cached tour script on reprocessing."""
        await cache.set_tour_script("proj-inv", {"slides": []})
        assert await cache.get_tour_script("proj-inv") is not None

        await cache.invalidate_tour_script("proj-inv")
        assert await cache.get_tour_script("proj-inv") is None


@pytest.mark.asyncio
class TestDashboardStatsCache:
    """Tests for dashboard stats cache operations."""

    async def test_get_dashboard_stats_miss(self, cache):
        """Should return None when dashboard stats are not cached."""
        result = await cache.get_dashboard_stats("cp-unknown", "2024-01")
        assert result is None

    async def test_set_and_get_dashboard_stats(self, cache):
        """Should store and retrieve dashboard statistics."""
        stats = {
            "tours_shared": 45,
            "leads": 12,
            "hot_leads": 3,
            "conversions": 1,
        }

        await cache.set_dashboard_stats("cp-100", "2024-01", stats)
        result = await cache.get_dashboard_stats("cp-100", "2024-01")

        assert result == stats
        assert result["tours_shared"] == 45
        assert result["hot_leads"] == 3

    async def test_set_dashboard_stats_ttl(self, cache):
        """Should set 60s TTL on dashboard stats keys."""
        await cache.set_dashboard_stats("cp-ttl", "2024-02", {"tours_shared": 0})

        ttl = await cache.client.ttl("dashboard:cp-ttl:2024-02")
        assert ttl > 0
        assert ttl <= DASHBOARD_STATS_TTL

    async def test_dashboard_stats_different_months(self, cache):
        """Should cache stats independently per CP and month."""
        stats_jan = {"tours_shared": 10, "leads": 5, "hot_leads": 1, "conversions": 0}
        stats_feb = {"tours_shared": 20, "leads": 8, "hot_leads": 3, "conversions": 2}

        await cache.set_dashboard_stats("cp-200", "2024-01", stats_jan)
        await cache.set_dashboard_stats("cp-200", "2024-02", stats_feb)

        assert await cache.get_dashboard_stats("cp-200", "2024-01") == stats_jan
        assert await cache.get_dashboard_stats("cp-200", "2024-02") == stats_feb


@pytest.mark.asyncio
class TestOtpRateLimiting:
    """Tests for OTP rate limiting and attempt tracking."""

    async def test_check_otp_rate_limit_no_requests(self, cache):
        """Should return not limited when no prior requests exist."""
        is_limited, remaining = await cache.check_otp_rate_limit("+919876543210")
        assert is_limited is False
        assert remaining == 0

    async def test_increment_otp_rate_first_call(self, cache):
        """Should return 1 on first increment and set TTL."""
        count = await cache.increment_otp_rate("+919876543210")
        assert count == 1

        ttl = await cache.client.ttl("otp_rate:+919876543210")
        assert ttl > 0
        assert ttl <= OTP_RATE_TTL

    async def test_increment_otp_rate_subsequent(self, cache):
        """Should increment counter on subsequent calls."""
        phone = "+919876599999"
        await cache.increment_otp_rate(phone)
        await cache.increment_otp_rate(phone)
        count = await cache.increment_otp_rate(phone)
        assert count == 3

    async def test_rate_limit_reached_at_5(self, cache):
        """Should be rate limited after 5 OTP requests."""
        phone = "+919876500000"
        for _ in range(5):
            await cache.increment_otp_rate(phone)

        is_limited, remaining = await cache.check_otp_rate_limit(phone)
        assert is_limited is True
        assert remaining > 0

    async def test_rate_limit_not_reached_under_5(self, cache):
        """Should not be rate limited with fewer than 5 requests."""
        phone = "+919876511111"
        for _ in range(4):
            await cache.increment_otp_rate(phone)

        is_limited, remaining = await cache.check_otp_rate_limit(phone)
        assert is_limited is False
        assert remaining > 0

    async def test_increment_otp_attempts(self, cache):
        """Should track failed OTP verification attempts."""
        phone = "+919876522222"
        count1 = await cache.increment_otp_attempts(phone)
        count2 = await cache.increment_otp_attempts(phone)
        count3 = await cache.increment_otp_attempts(phone)

        assert count1 == 1
        assert count2 == 2
        assert count3 == 3

        ttl = await cache.client.ttl(f"otp_attempts:{phone}")
        assert ttl > 0
        assert ttl <= OTP_RATE_TTL

    async def test_reset_otp_attempts(self, cache):
        """Should reset OTP attempt counter on successful auth."""
        phone = "+919876533333"
        await cache.increment_otp_attempts(phone)
        await cache.increment_otp_attempts(phone)

        await cache.reset_otp_attempts(phone)

        # After reset, incrementing starts from 1 again
        count = await cache.increment_otp_attempts(phone)
        assert count == 1


@pytest.mark.asyncio
class TestRedisCacheConnection:
    """Tests for Redis connection lifecycle."""

    async def test_client_raises_when_not_connected(self):
        """Should raise RuntimeError when accessing client before connect."""
        cache = RedisCache()
        with pytest.raises(RuntimeError, match="Redis not connected"):
            _ = cache.client

    async def test_connect_and_disconnect(self):
        """Should connect and disconnect without errors using fakeredis."""
        cache = RedisCache()
        # Manually inject fakeredis
        cache._redis = fakeredis.aioredis.FakeRedis(
            encoding="utf-8", decode_responses=True
        )
        assert cache._redis is not None

        await cache.disconnect()
        assert cache._redis is None
