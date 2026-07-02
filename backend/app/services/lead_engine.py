"""Lead scoring engine for AutoMind AI Platform.

Implements score calculation, classification, question classification,
dual-write persistence, and alert threshold checking.
"""

import logging
from typing import Any

logger = logging.getLogger(__name__)

# Signal weights as per design
SIGNAL_WEIGHTS: dict[str, int] = {
    "time_on_tour_3min_plus": 2,
    "room_revisited": 1,  # max 2 distinct rooms
    "price_question_asked": 2,
    "emi_question_asked": 3,
    "rera_question_asked": 1,
    "amenities_question_asked": 1,
    "returned_within_24h": 2,
    "whatsapp_share_clicked": 1,
    "visit_booking_clicked": 4,
}

# Maximum contribution from room_revisited signals
MAX_ROOM_REVISITED_CONTRIBUTION = 2

# Alert threshold
ALERT_THRESHOLD = 7

# Question classification keywords
_PRICE_KEYWORDS = {"price", "cost", "rate"}
_EMI_KEYWORDS = {"emi", "loan", "mortgage", "installment"}
_RERA_KEYWORDS = {"rera", "registration"}
_AMENITIES_KEYWORDS = {"amenities", "gym", "pool", "garden", "parking", "clubhouse"}


def calculate_score(session_signals: list[dict]) -> tuple[int, str, list[dict]]:
    """Calculate lead score from accumulated session signals.

    Each signal type is counted at most once, except room_revisited
    which counts up to 2 distinct rooms. Final score is capped at 10.

    Args:
        session_signals: List of signal dicts with 'type' key.

    Returns:
        Tuple of (score, classification, applied_signals_breakdown).
        applied_signals_breakdown is a list of dicts with 'type' and 'points'.
    """
    score = 0
    applied_signals: set[str] = set()
    room_revisit_count = 0
    has_visit_booking = False
    breakdown: list[dict] = []

    for signal in session_signals:
        signal_type = signal.get("type", "")

        if signal_type == "visit_booking_clicked":
            has_visit_booking = True
            if signal_type not in applied_signals:
                weight = SIGNAL_WEIGHTS[signal_type]
                score += weight
                applied_signals.add(signal_type)
                breakdown.append({"type": signal_type, "points": weight})
        elif signal_type == "room_revisited":
            if room_revisit_count < MAX_ROOM_REVISITED_CONTRIBUTION:
                weight = SIGNAL_WEIGHTS[signal_type]
                score += weight
                room_revisit_count += 1
                breakdown.append({"type": signal_type, "points": weight})
        else:
            if signal_type not in applied_signals and signal_type in SIGNAL_WEIGHTS:
                weight = SIGNAL_WEIGHTS[signal_type]
                score += weight
                applied_signals.add(signal_type)
                breakdown.append({"type": signal_type, "points": weight})

    # Cap at 10
    score = min(score, 10)

    # Classification
    classification = classify_lead(score, has_visit_booking)

    return score, classification, breakdown


def classify_lead(score: int, has_visit_booking: bool) -> str:
    """Classify a lead based on score and visit booking status.

    Args:
        score: Lead score (0-10).
        has_visit_booking: Whether visit_booking_clicked was triggered.

    Returns:
        Classification string: "browsing", "warm", "hot", or "visit_booked".
    """
    if has_visit_booking:
        return "visit_booked"
    elif score >= 7:
        return "hot"
    elif score >= 4:
        return "warm"
    else:
        return "browsing"


def classify_question(message: str) -> tuple[str | None, int]:
    """Classify a chat message into a scoring signal category.

    Uses keyword matching to detect price, EMI, RERA, or amenities questions.

    Args:
        message: The chat message text.

    Returns:
        Tuple of (signal_type, weight) or (None, 0) for general messages.
    """
    lower_message = message.lower()
    words = set(lower_message.split())

    # Check each category by looking for keywords in the message words
    # Also check substrings for compound words
    if _has_keyword(lower_message, words, _PRICE_KEYWORDS):
        return "price_question_asked", SIGNAL_WEIGHTS["price_question_asked"]

    if _has_keyword(lower_message, words, _EMI_KEYWORDS):
        return "emi_question_asked", SIGNAL_WEIGHTS["emi_question_asked"]

    if _has_keyword(lower_message, words, _RERA_KEYWORDS):
        return "rera_question_asked", SIGNAL_WEIGHTS["rera_question_asked"]

    if _has_keyword(lower_message, words, _AMENITIES_KEYWORDS):
        return "amenities_question_asked", SIGNAL_WEIGHTS["amenities_question_asked"]

    return None, 0


def _has_keyword(lower_message: str, words: set[str], keywords: set[str]) -> bool:
    """Check if any keyword appears in the message (word or substring match)."""
    for keyword in keywords:
        if keyword in words:
            return True
        # Also check if keyword appears as substring (e.g., "pricing" contains "price")
        if keyword in lower_message:
            return True
    return False


async def persist_score_update(
    session_id: str,
    cp_id: str,
    project_id: str,
    score: int,
    classification: str,
    signals: list[dict],
) -> None:
    """Dual-write pattern: DynamoDB first (source of truth), then RDS (materialized).

    DynamoDB write MUST succeed. RDS write is best-effort — log error, don't fail.

    Args:
        session_id: The session identifier.
        cp_id: Channel partner ID.
        project_id: Project ID.
        score: Calculated lead score.
        classification: Lead classification.
        signals: List of applied signal dicts.
    """
    from app.services.dynamodb_session import SessionRepository

    # 1. Write to DynamoDB — source of truth (MUST succeed)
    repo = SessionRepository()
    signals_map = {s["type"]: s["points"] for s in signals}
    await repo.update_score(
        session_id=session_id,
        score=score,
        classification=classification,
        signals=signals_map,
    )

    # 2. Write to RDS — materialized for dashboard (best-effort)
    try:
        # Import here to avoid circular imports and to handle case where
        # RDS might not be available
        from app.services.rds_leads import upsert_lead

        await upsert_lead(
            session_id=session_id,
            cp_id=cp_id,
            project_id=project_id,
            score=score,
            classification=classification,
            signals=signals,
        )
    except Exception as e:
        # Log but do NOT fail — DynamoDB is the source of truth
        logger.error(f"RDS write failed for session {session_id}: {e}")


async def check_and_alert(
    session_id: str,
    score: int,
    classification: str,
    cp_id: str,
    project_id: str,
) -> bool:
    """Check if score crosses alert threshold and trigger notification.

    Triggers alert when score reaches >= 7 for the first time in a session.
    Marks alert_sent = True in DynamoDB to prevent duplicates.

    Args:
        session_id: The session identifier.
        score: Current lead score.
        classification: Current classification.
        cp_id: Channel partner ID.
        project_id: Project ID.

    Returns:
        True if alert was triggered, False otherwise.
    """
    if score < ALERT_THRESHOLD:
        return False

    from app.services.dynamodb_session import SessionRepository

    repo = SessionRepository()
    session = await repo.get_session(session_id)

    if session is None:
        return False

    # Check if alert was already sent
    if session.get("alert_sent", False):
        return False

    # Mark alert as sent
    signals_map = session.get("signals", {})
    await repo.update_score(
        session_id=session_id,
        score=score,
        classification=classification,
        signals=signals_map,
        alert_sent=True,
    )

    # Trigger notification (best-effort)
    try:
        from app.services.notifications import send_hot_lead_alert

        await send_hot_lead_alert(
            cp_id=cp_id,
            project_id=project_id,
            session_id=session_id,
            score=score,
            classification=classification,
        )
    except Exception as e:
        logger.error(f"Alert notification failed for session {session_id}: {e}")

    # Push real-time update to CP dashboard (best-effort)
    try:
        from app.api.dashboard import push_hot_lead_update

        lead_data = {
            "lead_id": session_id,
            "buyer_name": session.get("buyer_name"),
            "buyer_phone": session.get("buyer_phone"),
            "project_name": "",  # Will be "Unknown" on client if empty
            "score": score,
            "classification": classification,
            "signals": [
                {"type": k, "points": v.get("points", 0) if isinstance(v, dict) else 0}
                for k, v in signals_map.items()
            ],
            "created_at": session.get("created_at", ""),
        }
        await push_hot_lead_update(cp_id, lead_data)
    except Exception as e:
        logger.warning(f"Dashboard push failed for cp_id={cp_id}: {e}")

    return True
