"""Tests for hot-lead alert notification service.

Tests WhatsApp delivery via Gupshup, SMS fallback via SNS,
message formatting, and delivery chain logic.

**Validates: Requirements 10.2, 10.3, 10.5, 10.7**
"""

import json
from unittest.mock import AsyncMock, MagicMock, patch

import pytest
import respx
import httpx

from app.services.notifications import (
    _build_whatsapp_message,
    _format_signal_summary,
    _send_via_gupshup,
    _send_via_sns,
    send_hot_lead_alert,
)


# --- Unit tests for message formatting ---

class TestFormatSignalSummary:
    """Tests for signal summary formatting."""

    def test_empty_signals_returns_placeholder(self):
        result = _format_signal_summary([])
        assert "General interest" in result

    def test_price_signal_formatted(self):
        result = _format_signal_summary([
            {"type": "price_question_asked", "points": 2}
        ])
        assert "price" in result.lower()
        assert "+2" in result

    def test_emi_signal_formatted(self):
        result = _format_signal_summary([
            {"type": "emi_question_asked", "points": 3}
        ])
        assert "EMI" in result or "emi" in result.lower()
        assert "+3" in result

    def test_multiple_signals_all_listed(self):
        signals = [
            {"type": "price_question_asked", "points": 2},
            {"type": "time_on_tour_3min_plus", "points": 2},
            {"type": "visit_booking_clicked", "points": 4},
        ]
        result = _format_signal_summary(signals)
        assert "+2" in result
        assert "+4" in result
        assert result.count("•") == 3


class TestBuildWhatsAppMessage:
    """Tests for WhatsApp message construction.

    **Validates: Requirements 10.2, 10.7**
    """

    def _base_call(self, **overrides):
        defaults = dict(
            buyer_name="Raj Kumar",
            project_name="Sunshine Heights",
            score=8,
            signals=[{"type": "emi_question_asked", "points": 3}],
            buyer_phone="9876543210",
            session_id="sess-abc123",
            project_tour_url="https://tour.automind.ai/t/sess-abc123",
        )
        defaults.update(overrides)
        return _build_whatsapp_message(**defaults)

    def test_contains_buyer_name(self):
        msg = self._base_call(buyer_name="Priya Sharma")
        assert "Priya Sharma" in msg

    def test_anonymous_buyer_when_name_missing(self):
        """Req 10.2: Use 'Anonymous Buyer' if name not collected."""
        msg = self._base_call(buyer_name=None)
        assert "Anonymous Buyer" in msg

    def test_contains_project_name(self):
        msg = self._base_call(project_name="Sky Towers")
        assert "Sky Towers" in msg

    def test_contains_score(self):
        msg = self._base_call(score=9)
        assert "9/10" in msg

    def test_contains_buyer_phone_when_available(self):
        """Req 10.2: Include buyer phone if collected."""
        msg = self._base_call(buyer_phone="9876543210")
        assert "9876543210" in msg

    def test_session_id_when_phone_missing(self):
        """Req 10.7: Include session ID + project link if phone not collected."""
        msg = self._base_call(buyer_phone=None, session_id="sess-xyz987")
        # Phone not in message
        assert "9876543210" not in msg
        # Session ID is referenced
        assert "sess-xyz" in msg

    def test_project_url_when_phone_missing(self):
        """Req 10.7: Include project tour URL when phone not available."""
        msg = self._base_call(buyer_phone=None, project_tour_url="https://tour.automind.ai/t/sess-xyz")
        assert "tour.automind.ai" in msg

    def test_hot_alert_emoji_present(self):
        msg = self._base_call()
        assert "🔥" in msg

    def test_signal_summary_in_message(self):
        signals = [
            {"type": "emi_question_asked", "points": 3},
            {"type": "visit_booking_clicked", "points": 4},
        ]
        msg = self._base_call(signals=signals)
        assert "+3" in msg
        assert "+4" in msg


# --- Tests for Gupshup delivery ---

class TestSendViaGupshup:
    """Tests for Gupshup WhatsApp delivery."""

    @pytest.mark.asyncio
    async def test_returns_false_when_not_configured(self):
        """Should return False gracefully when Gupshup API key is missing."""
        with patch("app.services.notifications.settings") as mock_settings:
            mock_settings.gupshup_api_key = ""
            mock_settings.gupshup_source_number = ""
            result = await _send_via_gupshup("9876543210", "test message")
        assert result is False

    @pytest.mark.asyncio
    async def test_returns_true_on_200(self):
        """Should return True when Gupshup returns 200."""
        with patch("app.services.notifications.settings") as mock_settings:
            mock_settings.gupshup_api_key = "test-key"
            mock_settings.gupshup_source_number = "919999999999"
            mock_settings.gupshup_app_name = "AutoMindTest"

            with respx.mock:
                respx.post("https://api.gupshup.io/sm/api/v1/msg").mock(
                    return_value=httpx.Response(200, json={"status": "submitted"})
                )
                result = await _send_via_gupshup("9876543210", "test message")

        assert result is True

    @pytest.mark.asyncio
    async def test_returns_false_on_4xx(self):
        """Should return False when Gupshup returns 4xx."""
        with patch("app.services.notifications.settings") as mock_settings:
            mock_settings.gupshup_api_key = "test-key"
            mock_settings.gupshup_source_number = "919999999999"
            mock_settings.gupshup_app_name = "AutoMindTest"

            with respx.mock:
                respx.post("https://api.gupshup.io/sm/api/v1/msg").mock(
                    return_value=httpx.Response(401, json={"error": "unauthorized"})
                )
                result = await _send_via_gupshup("9876543210", "test message")

        assert result is False

    @pytest.mark.asyncio
    async def test_returns_false_on_timeout(self):
        """Should return False on network timeout."""
        with patch("app.services.notifications.settings") as mock_settings:
            mock_settings.gupshup_api_key = "test-key"
            mock_settings.gupshup_source_number = "919999999999"
            mock_settings.gupshup_app_name = "AutoMindTest"

            with respx.mock:
                respx.post("https://api.gupshup.io/sm/api/v1/msg").mock(
                    side_effect=httpx.TimeoutException("timeout")
                )
                result = await _send_via_gupshup("9876543210", "test message")

        assert result is False


# --- Tests for SNS fallback ---

class TestSendViaSns:
    """Tests for AWS SNS SMS fallback."""

    @pytest.mark.asyncio
    async def test_returns_false_when_not_configured(self):
        """Should return False gracefully when SNS not configured."""
        with patch("app.services.notifications.settings") as mock_settings:
            mock_settings.sns_topic_arn = ""
            mock_settings.aws_access_key_id = ""
            mock_settings.aws_secret_access_key = ""
            mock_settings.aws_region = "ap-south-1"
            result = await _send_via_sns("", "test")
        assert result is False

    @pytest.mark.asyncio
    async def test_sends_sms_via_sns(self):
        """Should call SNS publish with correct phone and message."""
        mock_sns = AsyncMock()
        mock_sns.publish = AsyncMock(return_value={"MessageId": "test-msg-id"})
        mock_ctx = AsyncMock()
        mock_ctx.__aenter__ = AsyncMock(return_value=mock_sns)
        mock_ctx.__aexit__ = AsyncMock(return_value=False)

        with patch("app.services.notifications.settings") as mock_settings, \
             patch("aioboto3.Session") as mock_session_cls:
            mock_settings.sns_topic_arn = "arn:aws:sns:ap-south-1:123:test"
            mock_settings.aws_access_key_id = ""
            mock_settings.aws_secret_access_key = ""
            mock_settings.aws_region = "ap-south-1"
            mock_session_cls.return_value.client = MagicMock(return_value=mock_ctx)

            result = await _send_via_sns("9876543210", "Test alert message")

        assert result is True
        mock_sns.publish.assert_called_once()
        call_kwargs = mock_sns.publish.call_args[1]
        assert "+919876543210" in call_kwargs["PhoneNumber"]

    @pytest.mark.asyncio
    async def test_adds_country_code_if_missing(self):
        """Should prepend +91 to 10-digit phone numbers."""
        mock_sns = AsyncMock()
        mock_sns.publish = AsyncMock(return_value={"MessageId": "test"})
        mock_ctx = AsyncMock()
        mock_ctx.__aenter__ = AsyncMock(return_value=mock_sns)
        mock_ctx.__aexit__ = AsyncMock(return_value=False)

        with patch("app.services.notifications.settings") as mock_settings, \
             patch("aioboto3.Session") as mock_session_cls:
            mock_settings.sns_topic_arn = "arn:aws:sns:ap-south-1:123:test"
            mock_settings.aws_access_key_id = ""
            mock_settings.aws_secret_access_key = ""
            mock_settings.aws_region = "ap-south-1"
            mock_session_cls.return_value.client = MagicMock(return_value=mock_ctx)

            await _send_via_sns("9876543210", "msg")
            call_kwargs = mock_sns.publish.call_args[1]
            assert call_kwargs["PhoneNumber"] == "+919876543210"

    @pytest.mark.asyncio
    async def test_preserves_existing_country_code(self):
        """Should not double-add country code for +91 numbers."""
        mock_sns = AsyncMock()
        mock_sns.publish = AsyncMock(return_value={"MessageId": "test"})
        mock_ctx = AsyncMock()
        mock_ctx.__aenter__ = AsyncMock(return_value=mock_sns)
        mock_ctx.__aexit__ = AsyncMock(return_value=False)

        with patch("app.services.notifications.settings") as mock_settings, \
             patch("aioboto3.Session") as mock_session_cls:
            mock_settings.sns_topic_arn = "arn:aws:sns:ap-south-1:123:test"
            mock_settings.aws_access_key_id = ""
            mock_settings.aws_secret_access_key = ""
            mock_settings.aws_region = "ap-south-1"
            mock_session_cls.return_value.client = MagicMock(return_value=mock_ctx)

            await _send_via_sns("+919876543210", "msg")
            call_kwargs = mock_sns.publish.call_args[1]
            assert call_kwargs["PhoneNumber"] == "+919876543210"


# --- Integration tests for delivery chain ---

class TestSendHotLeadAlert:
    """Integration tests for the full alert delivery chain.

    **Validates: Requirements 10.2, 10.3, 10.5, 10.7**
    """

    @pytest.mark.asyncio
    async def test_gupshup_success_returns_true(self):
        """Primary delivery via Gupshup succeeds → return True."""
        with patch("app.services.notifications.get_cp_phone_from_db", return_value="9876543210"), \
             patch("app.services.notifications.get_project_name_from_db", return_value="Sunshine Heights"), \
             patch("app.services.notifications._send_via_gupshup", return_value=True) as mock_gupshup, \
             patch("app.services.notifications._send_via_sns") as mock_sns:

            result = await send_hot_lead_alert(
                cp_id="cp-123",
                project_id="proj-456",
                session_id="sess-789",
                score=8,
                classification="hot",
                buyer_name="Raj Kumar",
                buyer_phone="9123456789",
                signals=[{"type": "emi_question_asked", "points": 3}],
            )

        assert result is True
        mock_gupshup.assert_called_once()
        mock_sns.assert_not_called()

    @pytest.mark.asyncio
    async def test_gupshup_first_fail_retries_then_succeeds(self):
        """Gupshup fails first, succeeds on retry → return True, SNS not called."""
        with patch("app.services.notifications.get_cp_phone_from_db", return_value="9876543210"), \
             patch("app.services.notifications.get_project_name_from_db", return_value="Sky Tower"), \
             patch("app.services.notifications.asyncio.sleep"), \
             patch("app.services.notifications._send_via_gupshup", side_effect=[False, True]) as mock_gupshup, \
             patch("app.services.notifications._send_via_sns") as mock_sns:

            result = await send_hot_lead_alert(
                cp_id="cp-123",
                project_id="proj-456",
                session_id="sess-001",
                score=7,
                classification="hot",
            )

        assert result is True
        assert mock_gupshup.call_count == 2
        mock_sns.assert_not_called()

    @pytest.mark.asyncio
    async def test_gupshup_fails_twice_falls_back_to_sns(self):
        """Req 10.5: Gupshup fails both attempts → fallback to SNS."""
        with patch("app.services.notifications.get_cp_phone_from_db", return_value="9876543210"), \
             patch("app.services.notifications.get_project_name_from_db", return_value="Green Valley"), \
             patch("app.services.notifications.asyncio.sleep"), \
             patch("app.services.notifications._send_via_gupshup", return_value=False) as mock_gupshup, \
             patch("app.services.notifications._send_via_sns", return_value=True) as mock_sns:

            result = await send_hot_lead_alert(
                cp_id="cp-123",
                project_id="proj-456",
                session_id="sess-002",
                score=9,
                classification="hot",
            )

        assert result is True
        assert mock_gupshup.call_count == 2
        mock_sns.assert_called_once()

    @pytest.mark.asyncio
    async def test_all_channels_fail_returns_false(self):
        """If Gupshup and SNS both fail → return False."""
        with patch("app.services.notifications.get_cp_phone_from_db", return_value="9876543210"), \
             patch("app.services.notifications.get_project_name_from_db", return_value="Park View"), \
             patch("app.services.notifications.asyncio.sleep"), \
             patch("app.services.notifications._send_via_gupshup", return_value=False), \
             patch("app.services.notifications._send_via_sns", return_value=False):

            result = await send_hot_lead_alert(
                cp_id="cp-123",
                project_id="proj-456",
                session_id="sess-003",
                score=8,
                classification="hot",
            )

        assert result is False

    @pytest.mark.asyncio
    async def test_no_cp_phone_returns_false(self):
        """Should return False if CP phone cannot be fetched."""
        with patch("app.services.notifications.get_cp_phone_from_db", return_value=None), \
             patch("app.services.notifications.get_project_name_from_db", return_value="Test"):

            result = await send_hot_lead_alert(
                cp_id="cp-unknown",
                project_id="proj-456",
                session_id="sess-004",
                score=7,
                classification="hot",
            )

        assert result is False

    @pytest.mark.asyncio
    async def test_anonymous_buyer_message_completeness(self):
        """Req 10.2/10.7: Anonymous buyer gets session+URL instead of phone."""
        captured_messages = []

        async def capture_gupshup(phone, message):
            captured_messages.append(message)
            return True

        with patch("app.services.notifications.get_cp_phone_from_db", return_value="9876543210"), \
             patch("app.services.notifications.get_project_name_from_db", return_value="City Heights"), \
             patch("app.services.notifications._send_via_gupshup", side_effect=capture_gupshup):

            await send_hot_lead_alert(
                cp_id="cp-123",
                project_id="proj-456",
                session_id="sess-anon-111",
                score=7,
                classification="hot",
                buyer_name=None,      # No name
                buyer_phone=None,     # No phone
                signals=[{"type": "price_question_asked", "points": 2}],
            )

        assert len(captured_messages) == 1
        msg = captured_messages[0]

        # Must contain Anonymous Buyer
        assert "Anonymous Buyer" in msg
        # Must contain project name
        assert "City Heights" in msg
        # Must contain score
        assert "7/10" in msg
        # Must contain session reference (not phone)
        assert "sess-anon" in msg
        # Must contain tour URL
        assert "tour.automind.ai" in msg

    @pytest.mark.asyncio
    async def test_message_contains_all_required_fields(self):
        """Req 10.2: Alert includes buyer name, project, score, signals, phone."""
        captured_messages = []

        async def capture_gupshup(phone, message):
            captured_messages.append(message)
            return True

        with patch("app.services.notifications.get_cp_phone_from_db", return_value="9876543210"), \
             patch("app.services.notifications.get_project_name_from_db", return_value="Emerald Gardens"), \
             patch("app.services.notifications._send_via_gupshup", side_effect=capture_gupshup):

            await send_hot_lead_alert(
                cp_id="cp-123",
                project_id="proj-456",
                session_id="sess-456",
                score=8,
                classification="hot",
                buyer_name="Priya Mehta",
                buyer_phone="9123456789",
                signals=[
                    {"type": "emi_question_asked", "points": 3},
                    {"type": "visit_booking_clicked", "points": 4},
                ],
            )

        msg = captured_messages[0]
        assert "Priya Mehta" in msg        # buyer name
        assert "Emerald Gardens" in msg    # project name
        assert "8/10" in msg               # score
        assert "+3" in msg                 # EMI signal
        assert "+4" in msg                 # visit booking signal
        assert "9123456789" in msg         # buyer phone
