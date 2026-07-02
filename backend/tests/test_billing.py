"""Integration tests for billing API endpoints.

Tests credit pack listing, purchase order creation, and webhook processing.
"""

import json
import hashlib
import hmac
import uuid
from unittest.mock import AsyncMock, MagicMock, patch

import pytest
from httpx import ASGITransport, AsyncClient

from app.core.config import settings
from app.core.database import get_db
from app.core.security import create_access_token
from app.services.redis_cache import get_redis


# --- Test Fixtures ---


def _create_cp_token(sub: str = "cp-sub-123") -> str:
    """Create a JWT token with cp role."""
    return create_access_token(
        data={"sub": sub, "phone": "9876543210", "role": "cp"}
    )


def _create_admin_token() -> str:
    """Create a JWT token with admin role."""
    return create_access_token(
        data={"sub": "admin-sub", "phone": "9999999999", "role": "admin"}
    )


@pytest.fixture
async def billing_client():
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


# --- GET /api/v1/billing/packs ---


class TestListPacks:
    """Tests for GET /api/v1/billing/packs."""

    @pytest.mark.asyncio
    async def test_list_packs_returns_all_packs(self, billing_client):
        """Should return all 3 credit packs without auth."""
        response = await billing_client.get("/api/v1/billing/packs")

        assert response.status_code == 200
        data = response.json()
        assert len(data) == 3

        pack_types = [p["pack_type"] for p in data]
        assert "starter" in pack_types
        assert "growth" in pack_types
        assert "agency" in pack_types

    @pytest.mark.asyncio
    async def test_list_packs_starter_details(self, billing_client):
        """Starter pack has correct pricing and credits."""
        response = await billing_client.get("/api/v1/billing/packs")
        data = response.json()

        starter = next(p for p in data if p["pack_type"] == "starter")
        assert starter["amount_paise"] == 99900
        assert starter["credits"] == 2
        assert starter["name"] == "Starter Pack"

    @pytest.mark.asyncio
    async def test_list_packs_growth_details(self, billing_client):
        """Growth pack has correct pricing and credits."""
        response = await billing_client.get("/api/v1/billing/packs")
        data = response.json()

        growth = next(p for p in data if p["pack_type"] == "growth")
        assert growth["amount_paise"] == 399900
        assert growth["credits"] == 10
        assert growth["name"] == "Growth Pack"

    @pytest.mark.asyncio
    async def test_list_packs_agency_details(self, billing_client):
        """Agency pack has correct pricing and credits."""
        response = await billing_client.get("/api/v1/billing/packs")
        data = response.json()

        agency = next(p for p in data if p["pack_type"] == "agency")
        assert agency["amount_paise"] == 1499900
        assert agency["credits"] == 50
        assert agency["name"] == "Agency Pack"


# --- POST /api/v1/billing/purchase ---


class TestPurchaseCredits:
    """Tests for POST /api/v1/billing/purchase."""

    @pytest.mark.asyncio
    @patch("app.api.billing._get_razorpay_client")
    async def test_purchase_creates_order_201(self, mock_rz_client, billing_client):
        """CP can create a purchase order for starter pack."""
        mock_client = MagicMock()
        mock_client.order.create.return_value = {"id": "order_test123"}
        mock_rz_client.return_value = mock_client

        token = _create_cp_token()
        response = await billing_client.post(
            "/api/v1/billing/purchase",
            json={"pack_type": "starter"},
            headers={"Authorization": f"Bearer {token}"},
        )

        assert response.status_code == 201
        data = response.json()
        assert data["order_id"] == "order_test123"
        assert data["amount_paise"] == 99900
        assert data["credits"] == 2
        assert "razorpay_key_id" in data

    @pytest.mark.asyncio
    @patch("app.api.billing._get_razorpay_client")
    async def test_purchase_growth_pack(self, mock_rz_client, billing_client):
        """CP can purchase growth pack."""
        mock_client = MagicMock()
        mock_client.order.create.return_value = {"id": "order_growth_456"}
        mock_rz_client.return_value = mock_client

        token = _create_cp_token()
        response = await billing_client.post(
            "/api/v1/billing/purchase",
            json={"pack_type": "growth"},
            headers={"Authorization": f"Bearer {token}"},
        )

        assert response.status_code == 201
        data = response.json()
        assert data["credits"] == 10
        assert data["amount_paise"] == 399900

    @pytest.mark.asyncio
    async def test_purchase_invalid_pack_type_422(self, billing_client):
        """Invalid pack type returns 422."""
        token = _create_cp_token()
        response = await billing_client.post(
            "/api/v1/billing/purchase",
            json={"pack_type": "invalid"},
            headers={"Authorization": f"Bearer {token}"},
        )

        assert response.status_code == 422

    @pytest.mark.asyncio
    async def test_purchase_without_auth_403(self, billing_client):
        """Purchase without token returns 403."""
        response = await billing_client.post(
            "/api/v1/billing/purchase",
            json={"pack_type": "starter"},
        )

        assert response.status_code == 403

    @pytest.mark.asyncio
    async def test_purchase_admin_not_cp_403(self, billing_client):
        """Admin cannot purchase (only CP role allowed)."""
        token = _create_admin_token()
        response = await billing_client.post(
            "/api/v1/billing/purchase",
            json={"pack_type": "starter"},
            headers={"Authorization": f"Bearer {token}"},
        )

        assert response.status_code == 403


# --- POST /api/v1/billing/webhook ---


class TestWebhook:
    """Tests for POST /api/v1/billing/webhook."""

    def _generate_signature(self, body: str, secret: str) -> str:
        """Generate a valid HMAC-SHA256 signature for testing."""
        return hmac.new(
            secret.encode("utf-8"),
            body.encode("utf-8"),
            hashlib.sha256,
        ).hexdigest()

    @pytest.mark.asyncio
    @patch("app.api.billing._get_razorpay_client")
    async def test_webhook_invalid_signature_400(self, mock_rz_client, billing_client):
        """Invalid signature returns 400."""
        import razorpay.errors

        mock_client = MagicMock()
        mock_client.utility.verify_webhook_signature.side_effect = (
            razorpay.errors.SignatureVerificationError("bad sig")
        )
        mock_rz_client.return_value = mock_client

        payload = json.dumps({"event": "payment.captured", "payload": {}})

        response = await billing_client.post(
            "/api/v1/billing/webhook",
            content=payload,
            headers={
                "Content-Type": "application/json",
                "X-Razorpay-Signature": "invalid_sig",
            },
        )

        assert response.status_code == 400
        assert response.json()["detail"]["error"] == "invalid_signature"

    @pytest.mark.asyncio
    async def test_webhook_missing_signature_400(self, billing_client):
        """Missing signature header returns 400."""
        payload = json.dumps({"event": "payment.captured"})

        response = await billing_client.post(
            "/api/v1/billing/webhook",
            content=payload,
            headers={"Content-Type": "application/json"},
        )

        assert response.status_code == 400

    @pytest.mark.asyncio
    @patch("app.api.billing._get_razorpay_client")
    async def test_webhook_payment_captured_credits_cp(self, mock_rz_client, billing_client):
        """Valid payment.captured webhook credits the CP."""
        cp_sub = "cp-sub-123"
        pack_type = "starter"
        cp_id = uuid.uuid4()

        mock_client = MagicMock()
        mock_client.utility.verify_webhook_signature.return_value = True
        mock_client.order.fetch.return_value = {"receipt": f"{cp_sub}:{pack_type}"}
        mock_rz_client.return_value = mock_client

        # Mock db.execute for CP lookup and credit update
        mock_result = MagicMock()
        mock_result.first.return_value = (cp_id,)
        billing_client._mock_db.execute = AsyncMock(return_value=mock_result)

        payload = json.dumps({
            "event": "payment.captured",
            "payload": {
                "payment": {
                    "entity": {
                        "order_id": "order_abc123",
                    }
                }
            },
        })

        response = await billing_client.post(
            "/api/v1/billing/webhook",
            content=payload,
            headers={
                "Content-Type": "application/json",
                "X-Razorpay-Signature": "valid_sig",
            },
        )

        assert response.status_code == 200
        assert response.json()["status"] == "ok"

    @pytest.mark.asyncio
    @patch("app.api.billing._get_razorpay_client")
    async def test_webhook_non_captured_event_ignored(self, mock_rz_client, billing_client):
        """Non payment.captured events are acknowledged but not processed."""
        mock_client = MagicMock()
        mock_client.utility.verify_webhook_signature.return_value = True
        mock_rz_client.return_value = mock_client

        payload = json.dumps({"event": "payment.failed", "payload": {}})

        response = await billing_client.post(
            "/api/v1/billing/webhook",
            content=payload,
            headers={
                "Content-Type": "application/json",
                "X-Razorpay-Signature": "valid_sig",
            },
        )

        assert response.status_code == 200
        assert response.json()["status"] == "ok"
