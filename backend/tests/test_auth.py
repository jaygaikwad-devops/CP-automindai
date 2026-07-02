"""Tests for authentication API endpoints.

Tests OTP request, OTP verification, CP registration, and anonymous sessions.
Uses mocks for Cognito and dependency overrides for Redis.
"""

import uuid
from datetime import timedelta
from unittest.mock import AsyncMock, MagicMock, patch

import pytest
from httpx import ASGITransport, AsyncClient

from app.core.database import get_db
from app.core.security import create_access_token
from app.core.validators import validate_indian_phone, validate_rera_id
from app.services.redis_cache import RedisCache, get_redis


# --- Unit tests for validators ---


class TestValidateIndianPhone:
    """Unit tests for validate_indian_phone."""

    def test_valid_phone_starting_with_9(self):
        assert validate_indian_phone("9876543210") is True

    def test_valid_phone_starting_with_8(self):
        assert validate_indian_phone("8765432109") is True

    def test_valid_phone_starting_with_7(self):
        assert validate_indian_phone("7654321098") is True

    def test_valid_phone_starting_with_6(self):
        assert validate_indian_phone("6543210987") is True

    def test_invalid_starts_with_5(self):
        assert validate_indian_phone("5432109876") is False

    def test_invalid_starts_with_0(self):
        assert validate_indian_phone("0123456789") is False

    def test_invalid_too_short(self):
        assert validate_indian_phone("987654321") is False

    def test_invalid_too_long(self):
        assert validate_indian_phone("98765432101") is False

    def test_invalid_non_numeric(self):
        assert validate_indian_phone("98765abc10") is False

    def test_invalid_empty(self):
        assert validate_indian_phone("") is False

    def test_invalid_with_spaces(self):
        assert validate_indian_phone("987 654 32") is False

    def test_invalid_with_country_code(self):
        assert validate_indian_phone("+919876543210") is False


class TestValidateReraId:
    """Unit tests for validate_rera_id."""

    def test_valid_rera_mh(self):
        assert validate_rera_id("RERA/MH/2024/12345") is True

    def test_valid_rera_ka(self):
        assert validate_rera_id("RERA/KA/2023/1") is True

    def test_valid_rera_dl(self):
        assert validate_rera_id("RERA/DL/2020/99999") is True

    def test_invalid_lowercase_prefix(self):
        assert validate_rera_id("rera/MH/2024/12345") is False

    def test_invalid_lowercase_state(self):
        assert validate_rera_id("RERA/mh/2024/12345") is False

    def test_invalid_3letter_state(self):
        assert validate_rera_id("RERA/MAH/2024/12345") is False

    def test_invalid_short_year(self):
        assert validate_rera_id("RERA/MH/24/12345") is False

    def test_invalid_no_number(self):
        assert validate_rera_id("RERA/MH/2024/") is False

    def test_invalid_empty(self):
        assert validate_rera_id("") is False

    def test_invalid_random_string(self):
        assert validate_rera_id("something/else") is False

    def test_invalid_alpha_number(self):
        assert validate_rera_id("RERA/MH/2024/abc") is False


# --- Integration tests for auth endpoints ---


def _create_mock_redis():
    """Create a mock RedisCache instance."""
    redis_mock = AsyncMock(spec=RedisCache)
    redis_mock.check_otp_rate_limit = AsyncMock(return_value=(False, 0))
    redis_mock.increment_otp_rate = AsyncMock(return_value=1)
    redis_mock.increment_otp_attempts = AsyncMock(return_value=1)
    redis_mock.reset_otp_attempts = AsyncMock()
    redis_mock.client = AsyncMock()
    redis_mock.client.get = AsyncMock(return_value=None)
    redis_mock.client.ttl = AsyncMock(return_value=900)
    return redis_mock


@pytest.fixture
async def client():
    """Async test client with mocked dependencies."""
    from app.main import app

    mock_redis = _create_mock_redis()
    mock_db = AsyncMock()
    mock_db.add = MagicMock()
    mock_db.commit = AsyncMock()
    mock_db.execute = AsyncMock(return_value=MagicMock(scalar_one_or_none=MagicMock(return_value=None)))

    async def override_get_redis():
        return mock_redis

    async def override_get_db():
        yield mock_db

    app.dependency_overrides[get_redis] = override_get_redis
    app.dependency_overrides[get_db] = override_get_db

    transport = ASGITransport(app=app)
    async with AsyncClient(transport=transport, base_url="http://test") as ac:
        ac._mock_redis = mock_redis  # Store reference for test access
        ac._mock_db = mock_db
        yield ac

    app.dependency_overrides.clear()


class TestOTPRequest:
    """Tests for POST /api/v1/auth/otp/request."""

    @pytest.mark.asyncio
    async def test_valid_phone_returns_200(self, client):
        """Valid phone number returns OTP sent response."""
        with patch("app.api.auth._get_cognito_session") as mock_session:
            cognito_client = AsyncMock()
            cognito_client.initiate_auth = AsyncMock(return_value={"Session": "test"})
            mock_ctx = AsyncMock()
            mock_ctx.__aenter__ = AsyncMock(return_value=cognito_client)
            mock_ctx.__aexit__ = AsyncMock(return_value=False)
            mock_session.return_value.client = MagicMock(return_value=mock_ctx)

            response = await client.post(
                "/api/v1/auth/otp/request",
                json={"phone": "9876543210"},
            )

        assert response.status_code == 200
        data = response.json()
        assert data["message"] == "OTP sent"
        assert data["expires_in"] == 300

    @pytest.mark.asyncio
    async def test_invalid_phone_returns_422(self, client):
        """Invalid phone number returns 422."""
        response = await client.post(
            "/api/v1/auth/otp/request",
            json={"phone": "1234567890"},
        )
        assert response.status_code == 422

    @pytest.mark.asyncio
    async def test_short_phone_returns_422(self, client):
        """Phone number too short returns 422."""
        response = await client.post(
            "/api/v1/auth/otp/request",
            json={"phone": "987654"},
        )
        assert response.status_code == 422

    @pytest.mark.asyncio
    async def test_rate_limited_returns_429(self, client):
        """Rate limited phone returns 429."""
        client._mock_redis.check_otp_rate_limit = AsyncMock(return_value=(True, 600))

        response = await client.post(
            "/api/v1/auth/otp/request",
            json={"phone": "9876543210"},
        )

        assert response.status_code == 429
        data = response.json()
        assert data["detail"]["error"]["code"] == "rate_limited"
        assert data["detail"]["error"]["retry_after"] == 600


class TestOTPVerify:
    """Tests for POST /api/v1/auth/otp/verify."""

    @pytest.mark.asyncio
    async def test_valid_otp_returns_token(self, client):
        """Valid OTP returns JWT token."""
        with patch("app.api.auth._get_cognito_session") as mock_session:
            cognito_client = AsyncMock()
            cognito_client.initiate_auth = AsyncMock(
                return_value={"Session": "test-session"}
            )
            cognito_client.respond_to_auth_challenge = AsyncMock(
                return_value={
                    "AuthenticationResult": {
                        "AccessToken": "test-access-token",
                        "IdToken": "test-id-token",
                    }
                }
            )
            cognito_client.get_user = AsyncMock(
                return_value={
                    "Username": "test-cognito-sub",
                    "UserAttributes": [
                        {"Name": "phone_number", "Value": "+919876543210"},
                        {"Name": "custom:rera_id", "Value": "RERA/MH/2024/123"},
                    ],
                }
            )
            mock_ctx = AsyncMock()
            mock_ctx.__aenter__ = AsyncMock(return_value=cognito_client)
            mock_ctx.__aexit__ = AsyncMock(return_value=False)
            mock_session.return_value.client = MagicMock(return_value=mock_ctx)

            response = await client.post(
                "/api/v1/auth/otp/verify",
                json={"phone": "9876543210", "otp": "123456"},
            )

        assert response.status_code == 200
        data = response.json()
        assert "token" in data
        assert data["expires_in"] == 86400
        assert data["is_new_user"] is False

    @pytest.mark.asyncio
    async def test_invalid_otp_returns_401(self, client):
        """Invalid OTP returns 401 with attempts remaining."""
        with patch("app.api.auth._get_cognito_session") as mock_session:
            cognito_client = AsyncMock()
            cognito_client.initiate_auth = AsyncMock(
                side_effect=Exception("Invalid OTP")
            )
            mock_ctx = AsyncMock()
            mock_ctx.__aenter__ = AsyncMock(return_value=cognito_client)
            mock_ctx.__aexit__ = AsyncMock(return_value=False)
            mock_session.return_value.client = MagicMock(return_value=mock_ctx)

            response = await client.post(
                "/api/v1/auth/otp/verify",
                json={"phone": "9876543210", "otp": "000000"},
            )

        assert response.status_code == 401
        data = response.json()
        assert data["detail"]["error"]["code"] == "invalid_otp"
        assert "attempts_remaining" in data["detail"]["error"]

    @pytest.mark.asyncio
    async def test_locked_phone_returns_423(self, client):
        """Locked phone number returns 423."""
        client._mock_redis.client.get = AsyncMock(return_value="3")
        client._mock_redis.client.ttl = AsyncMock(return_value=800)

        response = await client.post(
            "/api/v1/auth/otp/verify",
            json={"phone": "9876543210", "otp": "123456"},
        )

        assert response.status_code == 423
        data = response.json()
        assert data["detail"]["error"]["code"] == "locked"
        assert "unlock_at" in data["detail"]["error"]

    @pytest.mark.asyncio
    async def test_invalid_phone_returns_422(self, client):
        """Invalid phone in verify returns 422."""
        response = await client.post(
            "/api/v1/auth/otp/verify",
            json={"phone": "123", "otp": "123456"},
        )
        assert response.status_code == 422


class TestRegister:
    """Tests for POST /api/v1/auth/register."""

    @pytest.mark.asyncio
    async def test_invalid_rera_returns_422(self, client):
        """Invalid RERA ID format returns 422."""
        token = create_access_token(
            data={"sub": "test-sub", "phone": "9876543210", "role": "cp"}
        )

        response = await client.post(
            "/api/v1/auth/register",
            json={"name": "Raj Kumar", "rera_id": "INVALID/FORMAT"},
            headers={"Authorization": f"Bearer {token}"},
        )

        assert response.status_code == 422
        data = response.json()
        assert data["detail"]["error"]["code"] == "invalid_rera_format"

    @pytest.mark.asyncio
    async def test_valid_registration(self, client):
        """Valid registration creates CP record."""
        token = create_access_token(
            data={"sub": "test-sub-new", "phone": "9876543210", "role": "cp"}
        )

        with patch("app.api.auth._get_cognito_session") as mock_cognito_session:
            # Mock Cognito
            cognito_client = AsyncMock()
            cognito_client.admin_update_user_attributes = AsyncMock()
            cognito_mock_ctx = AsyncMock()
            cognito_mock_ctx.__aenter__ = AsyncMock(return_value=cognito_client)
            cognito_mock_ctx.__aexit__ = AsyncMock(return_value=False)
            mock_cognito_session.return_value.client = MagicMock(
                return_value=cognito_mock_ctx
            )

            response = await client.post(
                "/api/v1/auth/register",
                json={"name": "Raj Kumar", "rera_id": "RERA/MH/2024/12345"},
                headers={"Authorization": f"Bearer {token}"},
            )

        assert response.status_code == 201
        data = response.json()
        assert data["name"] == "Raj Kumar"
        assert data["rera_id"] == "RERA/MH/2024/12345"
        assert "cp_id" in data

    @pytest.mark.asyncio
    async def test_no_auth_returns_403(self, client):
        """Request without auth returns 403."""
        response = await client.post(
            "/api/v1/auth/register",
            json={"name": "Raj Kumar", "rera_id": "RERA/MH/2024/12345"},
        )
        assert response.status_code == 403


class TestAnonymousSession:
    """Tests for POST /api/v1/auth/session/anonymous."""

    @pytest.mark.asyncio
    async def test_valid_link_creates_session(self, client):
        """Valid link_id creates anonymous session."""
        link_id = str(uuid.uuid4())

        # Set up mock db to return a share link
        mock_share_link = MagicMock()
        mock_share_link.cp_id = uuid.uuid4()
        mock_share_link.project_id = uuid.uuid4()

        mock_result = MagicMock()
        mock_result.scalar_one_or_none = MagicMock(return_value=mock_share_link)
        client._mock_db.execute = AsyncMock(return_value=mock_result)

        with patch("app.api.auth.SessionRepository") as mock_repo_cls:
            # Mock session repository
            mock_repo = AsyncMock()
            mock_repo.create_session = AsyncMock(return_value={})
            mock_repo.get_session = AsyncMock(return_value=None)
            mock_repo_cls.return_value = mock_repo

            response = await client.post(
                "/api/v1/auth/session/anonymous",
                json={"link_id": link_id},
            )

        assert response.status_code == 200
        data = response.json()
        assert "session_id" in data
        assert "session_token" in data

    @pytest.mark.asyncio
    async def test_invalid_link_returns_404(self, client):
        """Non-existent link_id returns 404."""
        link_id = str(uuid.uuid4())

        # Set up mock db to return None (link not found)
        mock_result = MagicMock()
        mock_result.scalar_one_or_none = MagicMock(return_value=None)
        client._mock_db.execute = AsyncMock(return_value=mock_result)

        response = await client.post(
            "/api/v1/auth/session/anonymous",
            json={"link_id": link_id},
        )

        assert response.status_code == 404
        data = response.json()
        assert data["error"]["code"] == "not_found"
        assert "Share link not found" in data["error"]["message"]
