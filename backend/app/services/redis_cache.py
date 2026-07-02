"""Redis cache layer for AutoMind AI Platform.

Provides caching for session scores, tour scripts, dashboard stats,
and OTP rate limiting using redis.asyncio with connection pooling.
"""

import json
import logging
from typing import Any

import redis.asyncio as aioredis

from app.core.config import settings

logger = logging.getLogger(__name__)

# TTL constants (seconds)
SESSION_SCORE_TTL = 86400  # 24 hours
TOUR_SCRIPT_TTL = 3600  # 1 hour
DASHBOARD_STATS_TTL = 60  # 60 seconds
OTP_RATE_TTL = 900  # 15 minutes

# Key prefixes
SESSION_KEY_PREFIX = "session:"
TOUR_KEY_PREFIX = "tour:"
DASHBOARD_KEY_PREFIX = "dashboard:"
OTP_RATE_KEY_PREFIX = "otp_rate:"
OTP_ATTEMPTS_KEY_PREFIX = "otp_attempts:"


class RedisCache:
    """Redis cache with connection pooling for AutoMind services.

    Handles session score caching, tour script caching,
    dashboard statistics caching, and OTP rate limiting.
    """

    def __init__(self, redis_url: str | None = None) -> None:
        self._redis_url = redis_url or settings.redis_url
        self._redis: aioredis.Redis | None = None

    async def connect(self) -> None:
        """Initialize the Redis connection pool."""
        if self._redis is None:
            self._redis = aioredis.from_url(
                self._redis_url,
                encoding="utf-8",
                decode_responses=True,
                max_connections=20,
            )
            logger.info("Redis connection pool initialized")

    async def disconnect(self) -> None:
        """Close the Redis connection pool."""
        if self._redis is not None:
            await self._redis.aclose()
            self._redis = None
            logger.info("Redis connection pool closed")

    @property
    def client(self) -> aioredis.Redis:
        """Get the Redis client, raising if not connected."""
        if self._redis is None:
            raise RuntimeError("Redis not connected. Call connect() first.")
        return self._redis

    # --- Session Score Cache (TTL 24h) ---

    async def get_session_score(self, session_id: str) -> dict[str, Any] | None:
        """Retrieve cached session score data.

        Args:
            session_id: The session identifier.

        Returns:
            Cached score dict with score, classification, signals, last_event_at
            or None if not cached.
        """
        key = f"{SESSION_KEY_PREFIX}{session_id}"
        data = await self.client.get(key)
        if data is None:
            return None
        return json.loads(data)

    async def set_session_score(self, session_id: str, score_data: dict[str, Any]) -> None:
        """Cache session score data with 24h TTL.

        Args:
            session_id: The session identifier.
            score_data: Dict containing score, classification, signals, last_event_at.
        """
        key = f"{SESSION_KEY_PREFIX}{session_id}"
        await self.client.set(key, json.dumps(score_data), ex=SESSION_SCORE_TTL)

    async def invalidate_session_score(self, session_id: str) -> None:
        """Remove cached session score.

        Args:
            session_id: The session identifier.
        """
        key = f"{SESSION_KEY_PREFIX}{session_id}"
        await self.client.delete(key)

    # --- Tour Script Cache (TTL 1h) ---

    async def get_tour_script(self, project_id: str) -> dict[str, Any] | None:
        """Retrieve cached tour script JSON.

        Args:
            project_id: The project identifier.

        Returns:
            Cached tour script dict or None if not cached.
        """
        key = f"{TOUR_KEY_PREFIX}{project_id}"
        data = await self.client.get(key)
        if data is None:
            return None
        return json.loads(data)

    async def set_tour_script(self, project_id: str, tour_script_json: dict[str, Any]) -> None:
        """Cache tour script JSON with 1h TTL.

        Args:
            project_id: The project identifier.
            tour_script_json: The tour script data to cache.
        """
        key = f"{TOUR_KEY_PREFIX}{project_id}"
        await self.client.set(key, json.dumps(tour_script_json), ex=TOUR_SCRIPT_TTL)

    async def invalidate_tour_script(self, project_id: str) -> None:
        """Remove cached tour script (e.g., on reprocessing).

        Args:
            project_id: The project identifier.
        """
        key = f"{TOUR_KEY_PREFIX}{project_id}"
        await self.client.delete(key)

    # --- Dashboard Stats Cache (TTL 60s) ---

    async def get_dashboard_stats(self, cp_id: str, month: str) -> dict[str, Any] | None:
        """Retrieve cached dashboard statistics.

        Args:
            cp_id: Channel partner identifier.
            month: Month string (e.g., "2024-01").

        Returns:
            Cached stats dict or None if not cached.
        """
        key = f"{DASHBOARD_KEY_PREFIX}{cp_id}:{month}"
        data = await self.client.get(key)
        if data is None:
            return None
        return json.loads(data)

    async def set_dashboard_stats(
        self, cp_id: str, month: str, stats: dict[str, Any]
    ) -> None:
        """Cache dashboard statistics with 60s TTL.

        Args:
            cp_id: Channel partner identifier.
            month: Month string (e.g., "2024-01").
            stats: Dict with tours_shared, leads, hot_leads, conversions.
        """
        key = f"{DASHBOARD_KEY_PREFIX}{cp_id}:{month}"
        await self.client.set(key, json.dumps(stats), ex=DASHBOARD_STATS_TTL)

    # --- OTP Rate Limiting (TTL 900s / 15 minutes) ---

    async def check_otp_rate_limit(self, phone: str) -> tuple[bool, int]:
        """Check if a phone number has exceeded OTP rate limit.

        Args:
            phone: The phone number to check.

        Returns:
            Tuple of (is_limited: bool, remaining_seconds: int).
            is_limited is True if the counter has reached the max (5 attempts).
            remaining_seconds is the TTL on the rate limit key.
        """
        key = f"{OTP_RATE_KEY_PREFIX}{phone}"
        count = await self.client.get(key)
        if count is None:
            return (False, 0)

        ttl = await self.client.ttl(key)
        remaining = max(ttl, 0)

        # Rate limited if 5 or more OTP requests in the window
        is_limited = int(count) >= 5
        return (is_limited, remaining)

    async def increment_otp_rate(self, phone: str) -> int:
        """Increment OTP request counter for rate limiting.

        Sets 900s TTL on first increment.

        Args:
            phone: The phone number.

        Returns:
            Current count after increment.
        """
        key = f"{OTP_RATE_KEY_PREFIX}{phone}"
        count = await self.client.incr(key)
        # Set TTL only on first increment (when count becomes 1)
        if count == 1:
            await self.client.expire(key, OTP_RATE_TTL)
        return count

    async def increment_otp_attempts(self, phone: str) -> int:
        """Track failed OTP verification attempts.

        Sets 900s TTL on first increment.

        Args:
            phone: The phone number.

        Returns:
            Current attempt count after increment.
        """
        key = f"{OTP_ATTEMPTS_KEY_PREFIX}{phone}"
        count = await self.client.incr(key)
        if count == 1:
            await self.client.expire(key, OTP_RATE_TTL)
        return count

    async def reset_otp_attempts(self, phone: str) -> None:
        """Reset OTP attempt counter on successful authentication.

        Args:
            phone: The phone number.
        """
        key = f"{OTP_ATTEMPTS_KEY_PREFIX}{phone}"
        await self.client.delete(key)


# Singleton instance for application-wide reuse
_redis_cache: RedisCache | None = None


async def get_redis() -> RedisCache:
    """FastAPI dependency that provides the Redis cache singleton.

    Returns:
        The shared RedisCache instance with active connection pool.

    Raises:
        RuntimeError: If Redis has not been initialized via init_redis().
    """
    global _redis_cache
    if _redis_cache is None:
        raise RuntimeError("Redis cache not initialized. Call init_redis() on startup.")
    return _redis_cache


async def init_redis(redis_url: str | None = None) -> RedisCache:
    """Initialize the Redis cache singleton. Call during app startup.

    Args:
        redis_url: Optional Redis URL override. Defaults to settings.redis_url.

    Returns:
        The initialized RedisCache instance.
    """
    global _redis_cache
    _redis_cache = RedisCache(redis_url=redis_url)
    await _redis_cache.connect()
    return _redis_cache


async def close_redis() -> None:
    """Close the Redis cache connection. Call during app shutdown."""
    global _redis_cache
    if _redis_cache is not None:
        await _redis_cache.disconnect()
        _redis_cache = None
