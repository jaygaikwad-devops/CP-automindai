"""Tour event endpoints for buyer session interactions.

Handles tour events such as room views, revisits, time tracking,
visit booking clicks, and WhatsApp share clicks.
"""

import logging
from typing import Any

from fastapi import APIRouter, HTTPException, status
from pydantic import BaseModel, Field

from app.services.dynamodb_session import SessionRepository
from app.services.lead_engine import calculate_score, check_and_alert, persist_score_update

logger = logging.getLogger(__name__)

router = APIRouter()

VALID_EVENT_TYPES = {
    "room_viewed",
    "room_revisited",
    "time_on_tour",
    "time_on_tour_3min_plus",
    "visit_booking_clicked",
    "whatsapp_share_clicked",
}


class TourEventRequest(BaseModel):
    """Request body for posting a tour event."""

    type: str = Field(
        ...,
        description="Event type: room_viewed, room_revisited, time_on_tour, "
        "visit_booking_clicked, whatsapp_share_clicked",
    )
    data: dict[str, Any] = Field(
        default_factory=dict,
        description="Additional event-specific payload data",
    )


class TourEventResponse(BaseModel):
    """Response body for tour event processing."""

    score: int
    classification: str


@router.post(
    "/{session_id}/events",
    response_model=TourEventResponse,
    status_code=status.HTTP_202_ACCEPTED,
    summary="Record a tour event",
    description="Accept tour interaction events and update lead score inline.",
)
async def post_tour_event(
    session_id: str,
    body: TourEventRequest,
) -> TourEventResponse:
    """Record a tour event and update lead score.

    Validates the session exists, adds the event to DynamoDB session history,
    recalculates the score, persists via dual-write, and triggers alerts
    if the threshold is crossed.

    Args:
        session_id: The buyer session identifier.
        body: The event type and associated data.

    Returns:
        202 response with updated score and classification.
    """
    # Validate event type
    if body.type not in VALID_EVENT_TYPES:
        raise HTTPException(
            status_code=status.HTTP_422_UNPROCESSABLE_ENTITY,
            detail=f"Invalid event type: {body.type}. "
            f"Must be one of: {', '.join(sorted(VALID_EVENT_TYPES))}",
        )

    repo = SessionRepository()

    # Validate session exists
    session = await repo.get_session(session_id)
    if session is None:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=f"Session not found: {session_id}",
        )

    # Add event to session history
    await repo.add_event(
        session_id=session_id,
        event_type=body.type,
        data=body.data,
    )

    # Build signal list from existing signals + new event
    existing_signals = session.get("signals", {})
    signal_list = [{"type": k} for k in existing_signals.keys()]

    # Map event types to signal types for scoring
    scoring_type = body.type
    if scoring_type == "time_on_tour":
        # Only time_on_tour_3min_plus is a scoring signal
        duration = body.data.get("duration_seconds", 0)
        if duration >= 180:
            scoring_type = "time_on_tour_3min_plus"
        else:
            # Not a scoring signal — return current score
            score = session.get("score", 0)
            classification = session.get("classification", "browsing")
            return TourEventResponse(score=score, classification=classification)
    elif scoring_type == "room_viewed":
        # room_viewed is tracked but doesn't directly score — only room_revisited does
        score = session.get("score", 0)
        classification = session.get("classification", "browsing")
        return TourEventResponse(score=score, classification=classification)

    signal_list.append({"type": scoring_type})

    # Calculate updated score
    score, classification, breakdown = calculate_score(signal_list)

    # Persist score update (DynamoDB → RDS dual-write)
    await persist_score_update(
        session_id=session_id,
        cp_id=session.get("cp_id", ""),
        project_id=session.get("project_id", ""),
        score=score,
        classification=classification,
        signals=breakdown,
    )

    # Check and alert if threshold crossed
    await check_and_alert(
        session_id=session_id,
        score=score,
        classification=classification,
        cp_id=session.get("cp_id", ""),
        project_id=session.get("project_id", ""),
    )

    return TourEventResponse(score=score, classification=classification)
