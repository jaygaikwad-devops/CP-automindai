"""Hot-lead alert notification service for AutoMind AI Platform.

Sends real-time WhatsApp alerts to Channel Partners via Gupshup API
when a buyer's lead score crosses the alert threshold (≥ 7).

Delivery chain:
  1. Primary:  WhatsApp via Gupshup REST API
  2. Fallback: SMS via AWS SNS (if Gupshup fails after 1 retry)

Design:
  - One alert per session per threshold crossing (idempotency enforced
    by DynamoDB `alert_sent` flag, checked in `check_and_alert`)
  - Message delivered within 10 seconds of threshold crossing
  - If buyer phone is not yet collected, include session ID + project link

Requirements: 10.2, 10.3, 10.5, 10.7
"""

import asyncio
import json
import logging
from typing import Any

import aioboto3
import httpx
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.config import settings

logger = logging.getLogger(__name__)

# Gupshup API endpoint
GUPSHUP_API_URL = "https://api.gupshup.io/sm/api/v1/msg"
GUPSHUP_TIMEOUT = 10  # seconds
GUPSHUP_RETRY_DELAY = 5  # seconds before SMS fallback


def _format_signal_summary(signals: list[dict]) -> str:
    """Format signal breakdown into a readable summary for the alert message.

    Args:
        signals: List of applied signal dicts with 'type' and 'points'.

    Returns:
        Multi-line string of signal contributions.
    """
    if not signals:
        return "• General interest"

    label_map = {
        "price_question_asked": "Asked about price",
        "emi_question_asked": "Asked about EMI/loan",
        "rera_question_asked": "Asked about RERA",
        "amenities_question_asked": "Asked about amenities",
        "time_on_tour_3min_plus": "Spent 3+ min on tour",
        "room_revisited": "Revisited rooms",
        "returned_within_24h": "Returned within 24h",
        "whatsapp_share_clicked": "Shared via WhatsApp",
        "visit_booking_clicked": "Clicked visit booking 🎯",
    }

    lines = []
    for signal in signals:
        label = label_map.get(signal["type"], signal["type"])
        points = signal.get("points", 0)
        lines.append(f"• {label} (+{points})")

    return "\n".join(lines)


def _build_whatsapp_message(
    buyer_name: str | None,
    project_name: str,
    score: int,
    signals: list[dict],
    buyer_phone: str | None,
    session_id: str,
    project_tour_url: str,
) -> str:
    """Build the WhatsApp alert message for the CP.

    Requirements:
    - Buyer name (or "Anonymous Buyer" if not collected)
    - Project name
    - Lead_Score
    - Triggered signals with point contributions
    - Buyer phone (or session ID + project link if not collected)

    Args:
        buyer_name: Buyer's name if collected, else None.
        project_name: Name of the project.
        score: Lead score (0–10).
        signals: List of triggered signals with points.
        buyer_phone: Buyer's phone if collected, else None.
        session_id: Session identifier.
        project_tour_url: URL to the project tour.

    Returns:
        Formatted WhatsApp message string.
    """
    name = buyer_name or "Anonymous Buyer"
    signal_summary = _format_signal_summary(signals)

    # Contact line: phone if available, session+link otherwise
    if buyer_phone:
        contact_line = f"📞 Call now: {buyer_phone}"
    else:
        contact_line = (
            f"🔗 Session: {session_id[:8]}...\n"
            f"🏠 Tour: {project_tour_url}"
        )

    message = (
        f"🔥 *Hot Lead Alert!*\n\n"
        f"👤 Buyer: {name}\n"
        f"🏢 Project: {project_name}\n"
        f"⭐ Score: {score}/10\n\n"
        f"📊 *Signals:*\n{signal_summary}\n\n"
        f"{contact_line}"
    )
    return message


async def _send_via_gupshup(cp_phone: str, message: str) -> bool:
    """Send WhatsApp message via Gupshup API.

    Args:
        cp_phone: CP's phone number (with country code, e.g. "919876543210").
        message: Message text to send.

    Returns:
        True if delivery succeeded (HTTP 2xx), False otherwise.
    """
    if not settings.gupshup_api_key or not settings.gupshup_source_number:
        logger.warning("Gupshup not configured — skipping WhatsApp delivery")
        return False

    payload = {
        "channel": "whatsapp",
        "source": settings.gupshup_source_number,
        "destination": cp_phone,
        "message": json.dumps({
            "type": "text",
            "text": message,
        }),
        "src.name": settings.gupshup_app_name or "AutoMindAI",
    }

    headers = {
        "apikey": settings.gupshup_api_key,
        "Content-Type": "application/x-www-form-urlencoded",
    }

    try:
        async with httpx.AsyncClient(timeout=GUPSHUP_TIMEOUT) as client:
            response = await client.post(
                GUPSHUP_API_URL,
                data=payload,
                headers=headers,
            )
            if response.status_code in range(200, 300):
                logger.info(f"Gupshup WhatsApp sent to {cp_phone}: {response.status_code}")
                return True
            else:
                logger.warning(
                    f"Gupshup returned {response.status_code} for {cp_phone}: {response.text}"
                )
                return False
    except (httpx.TimeoutException, httpx.ConnectError) as e:
        logger.warning(f"Gupshup request failed for {cp_phone}: {e}")
        return False


async def _send_via_sns(cp_phone: str, message: str) -> bool:
    """Send SMS via AWS SNS as Gupshup fallback.

    Args:
        cp_phone: CP's phone number (E.164 format, e.g. "+919876543210").
        message: SMS text (truncated to 160 chars for compatibility).

    Returns:
        True if SNS publish succeeded, False otherwise.
    """
    if not settings.sns_topic_arn and not cp_phone:
        logger.warning("SNS not configured — skipping SMS fallback")
        return False

    # Ensure E.164 format
    phone_e164 = cp_phone if cp_phone.startswith("+") else f"+91{cp_phone}"
    # Trim message for SMS
    sms_text = message[:160] if len(message) > 160 else message

    try:
        session = aioboto3.Session(
            aws_access_key_id=settings.aws_access_key_id or None,
            aws_secret_access_key=settings.aws_secret_access_key or None,
            region_name=settings.aws_region,
        )
        async with session.client("sns") as sns:
            await sns.publish(
                PhoneNumber=phone_e164,
                Message=sms_text,
                MessageAttributes={
                    "AWS.SNS.SMS.SMSType": {
                        "DataType": "String",
                        "StringValue": "Transactional",
                    }
                },
            )
        logger.info(f"SNS SMS fallback sent to {cp_phone}")
        return True
    except Exception as e:
        logger.error(f"SNS fallback failed for {cp_phone}: {e}")
        return False


async def get_cp_phone_from_db(cp_id: str) -> str | None:
    """Fetch CP phone number from RDS.

    Args:
        cp_id: The CP's UUID.

    Returns:
        Phone string or None if not found.
    """
    try:
        from app.core.database import async_session_factory
        from app.models.cp import CP
        import uuid

        async with async_session_factory() as db:
            result = await db.execute(
                select(CP).where(CP.id == uuid.UUID(cp_id))
            )
            cp = result.scalar_one_or_none()
            return cp.phone if cp else None
    except Exception as e:
        logger.warning(f"Could not fetch CP phone for cp_id={cp_id}: {e}")
        return None


async def get_project_name_from_db(project_id: str) -> str:
    """Fetch project name from RDS.

    Args:
        project_id: The project's UUID.

    Returns:
        Project name string or a fallback.
    """
    try:
        from app.core.database import async_session_factory
        from app.models.project import Project
        import uuid

        async with async_session_factory() as db:
            result = await db.execute(
                select(Project).where(Project.id == uuid.UUID(project_id))
            )
            project = result.scalar_one_or_none()
            return project.name if project else "Unknown Project"
    except Exception as e:
        logger.warning(f"Could not fetch project name for project_id={project_id}: {e}")
        return "Unknown Project"


async def send_hot_lead_alert(
    cp_id: str,
    project_id: str,
    session_id: str,
    score: int,
    classification: str,
    buyer_name: str | None = None,
    buyer_phone: str | None = None,
    signals: list[dict] | None = None,
) -> bool:
    """Send a hot lead alert to the CP via WhatsApp, with SMS fallback.

    Delivery chain:
    1. Try Gupshup WhatsApp
    2. On failure, wait 5 seconds, retry Gupshup once
    3. On second failure, fallback to AWS SNS SMS

    Requirement 10.3: Alert delivered within 10 seconds of threshold crossing.
    Requirement 10.5: Retry + SNS fallback.
    Requirement 10.7: Fallback to session ID + project link if phone not collected.

    Args:
        cp_id: Channel partner ID to notify.
        project_id: Project UUID for context.
        session_id: Buyer session that triggered the alert.
        score: Current lead score.
        classification: Lead classification ("hot" or "visit_booked").
        buyer_name: Buyer's collected name (or None if anonymous).
        buyer_phone: Buyer's collected phone (or None).
        signals: List of triggered signal dicts with 'type' and 'points'.

    Returns:
        True if alert was delivered via any channel, False if all failed.
    """
    signals = signals or []

    # Fetch CP phone and project name concurrently
    cp_phone, project_name = await asyncio.gather(
        get_cp_phone_from_db(cp_id),
        get_project_name_from_db(project_id),
    )

    if not cp_phone:
        logger.warning(f"No phone for CP {cp_id} — cannot send alert")
        return False

    # Build project tour URL
    project_tour_url = f"https://tour.automind.ai/t/{session_id}"

    # Build message
    message = _build_whatsapp_message(
        buyer_name=buyer_name,
        project_name=project_name,
        score=score,
        signals=signals,
        buyer_phone=buyer_phone,
        session_id=session_id,
        project_tour_url=project_tour_url,
    )

    logger.info(
        f"Sending hot lead alert: cp_id={cp_id}, session={session_id}, "
        f"score={score}, classification={classification}"
    )

    # Attempt 1: Gupshup
    delivered = await _send_via_gupshup(cp_phone, message)
    if delivered:
        return True

    # Wait before retry (Req 10.5: retry once after 5 seconds)
    logger.info(f"Gupshup attempt 1 failed for {cp_phone}, retrying after {GUPSHUP_RETRY_DELAY}s")
    await asyncio.sleep(GUPSHUP_RETRY_DELAY)

    # Attempt 2: Gupshup retry
    delivered = await _send_via_gupshup(cp_phone, message)
    if delivered:
        return True

    # Attempt 3: SNS SMS fallback
    logger.warning(f"Gupshup failed twice for {cp_phone}, falling back to SNS SMS")
    delivered = await _send_via_sns(cp_phone, message)

    if not delivered:
        logger.error(
            f"All alert delivery channels failed for CP {cp_id} "
            f"(session={session_id}, score={score})"
        )

    return delivered
