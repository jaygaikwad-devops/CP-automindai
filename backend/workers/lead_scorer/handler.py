"""Lead Scorer Lambda handler for non-chat events.

Processes behavioural signals that occur outside the WebSocket chat flow:
- room_revisited
- time_on_tour_3min_plus
- visit_booking_clicked
- returned_within_24h
- whatsapp_share_clicked

Reads the current session from DynamoDB, applies the signal via
calculate_score, persists the score update (DynamoDB → RDS dual-write),
and triggers a CP alert if the threshold is crossed.
"""

import json
import logging
import asyncio
from typing import Any

logger = logging.getLogger(__name__)
logger.setLevel(logging.INFO)

VALID_EVENT_TYPES = {
    "room_revisited",
    "time_on_tour_3min_plus",
    "visit_booking_clicked",
    "returned_within_24h",
    "whatsapp_share_clicked",
}


async def _process_event(session_id: str, event_type: str, data: dict) -> dict[str, Any]:
    """Process a single non-chat scoring event.

    Args:
        session_id: The buyer session identifier.
        event_type: One of the valid non-chat event types.
        data: Additional event payload data.

    Returns:
        Dict with score and classification.

    Raises:
        ValueError: If event_type is invalid or session not found.
    """
    from app.services.dynamodb_session import SessionRepository
    from app.services.lead_engine import (
        calculate_score,
        check_and_alert,
        persist_score_update,
    )

    if event_type not in VALID_EVENT_TYPES:
        raise ValueError(f"Invalid event type: {event_type}")

    repo = SessionRepository()

    # Read current session from DynamoDB
    session = await repo.get_session(session_id)
    if session is None:
        raise ValueError(f"Session not found: {session_id}")

    # Add event to session history
    await repo.add_event(session_id=session_id, event_type=event_type, data=data)

    # Get existing signals and add new one
    existing_signals = session.get("signals", {})
    signal_list = [{"type": k} for k in existing_signals.keys()]
    signal_list.append({"type": event_type})

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

    return {"score": score, "classification": classification}


def handler(event: dict, context: Any) -> dict:
    """AWS Lambda entry point for lead scoring non-chat events.

    Expected event payload (direct invocation or API Gateway proxy):
    {
        "session_id": "uuid",
        "event_type": "room_revisited",
        "data": { ... }
    }

    Returns:
        Response dict with statusCode 202 and score/classification body.
    """
    logger.info(f"Lead scorer invoked with event: {json.dumps(event)}")

    try:
        # Support both direct invocation and API Gateway proxy
        if "body" in event:
            body = json.loads(event["body"]) if isinstance(event["body"], str) else event["body"]
            session_id = event.get("pathParameters", {}).get("session_id", "")
        else:
            body = event
            session_id = event.get("session_id", "")

        event_type = body.get("event_type") or body.get("type", "")
        data = body.get("data", {})

        if not session_id:
            return {
                "statusCode": 400,
                "body": json.dumps({"error": "session_id is required"}),
            }

        if not event_type:
            return {
                "statusCode": 400,
                "body": json.dumps({"error": "event_type is required"}),
            }

        # Run the async processing
        result = asyncio.get_event_loop().run_until_complete(
            _process_event(session_id, event_type, data)
        )

        return {
            "statusCode": 202,
            "body": json.dumps(result),
            "headers": {"Content-Type": "application/json"},
        }

    except ValueError as e:
        logger.warning(f"Validation error: {e}")
        return {
            "statusCode": 400,
            "body": json.dumps({"error": str(e)}),
        }
    except Exception as e:
        logger.error(f"Error processing event: {e}", exc_info=True)
        return {
            "statusCode": 500,
            "body": json.dumps({"error": "Internal server error"}),
        }
