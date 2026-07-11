"""Tour endpoints for buyer session interactions and tour script loading.

Handles tour loading, events such as room views, revisits, time tracking,
visit booking clicks, and WhatsApp share clicks.
"""

import logging
import uuid
from datetime import timedelta
from typing import Any

from fastapi import APIRouter, Depends, HTTPException, status
from pydantic import BaseModel, Field
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.database import get_db
from app.core.security import create_access_token
from app.models.project import Project
from app.models.share_link import ShareLink
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


# ---- Demo Tour Scripts (production would load from S3) ----

DEMO_TOUR_SCRIPTS = {
    "Lodha Crown": {
        "schema_version": "1.0.0",
        "project_name": "Lodha Crown",
        "total_rooms": 7,
        "estimated_duration_seconds": 210,
        "rooms": [
            {
                "index": 0, "id": "entrance_lobby", "name": "Grand Entrance Lobby",
                "room_type": "lobby",
                "narration": {"text": "Welcome to Lodha Crown! Step into our grand double-height entrance lobby with Italian marble flooring and a stunning crystal chandelier. The lobby features 24/7 concierge service and CCTV security.", "duration_seconds": 25, "language": "en"},
                "visuals": {"primary_image_url": "https://images.unsplash.com/photo-1600607687939-ce8a6c25118c?w=1200", "labels": ["lobby", "chandelier", "marble"]},
                "features": [{"name": "Double-height Ceiling", "category": "architecture"}, {"name": "Italian Marble", "category": "flooring"}, {"name": "24/7 Concierge", "category": "service"}],
                "transition": {"type": "fade", "duration_ms": 300},
            },
            {
                "index": 1, "id": "living_room", "name": "Spacious Living Room",
                "room_type": "living_room",
                "narration": {"text": "The living room spans 250 square feet with floor-to-ceiling windows offering panoramic views of the Thane creek. Vitrified tile flooring and concealed air conditioning make this space perfect for family gatherings.", "duration_seconds": 30, "language": "en"},
                "visuals": {"primary_image_url": "https://images.unsplash.com/photo-1600210492486-724fe5c67fb0?w=1200", "labels": ["sofa", "window", "natural_light", "spacious"]},
                "features": [{"name": "250 sq ft Area", "category": "space"}, {"name": "Creek View", "category": "view"}, {"name": "Concealed AC", "category": "comfort"}, {"name": "Vitrified Tiles", "category": "flooring"}],
                "transition": {"type": "slide_left", "duration_ms": 300},
            },
            {
                "index": 2, "id": "master_bedroom", "name": "Master Bedroom Suite",
                "room_type": "bedroom",
                "narration": {"text": "The master bedroom is your private sanctuary. It features a walk-in wardrobe, en-suite bathroom with rain shower, and a private balcony. The room accommodates a king-size bed with space for a study nook.", "duration_seconds": 30, "language": "en"},
                "visuals": {"primary_image_url": "https://images.unsplash.com/photo-1616594039964-ae9021a400a0?w=1200", "labels": ["bed", "wardrobe", "balcony", "luxury"]},
                "features": [{"name": "Walk-in Wardrobe", "category": "storage"}, {"name": "En-suite Bathroom", "category": "bathroom"}, {"name": "Private Balcony", "category": "outdoor"}, {"name": "King-size Bed Space", "category": "space"}],
                "transition": {"type": "slide_left", "duration_ms": 300},
            },
            {
                "index": 3, "id": "kitchen", "name": "Modular Kitchen",
                "room_type": "kitchen",
                "narration": {"text": "The fully modular kitchen comes with granite countertops, stainless steel sink, chimney and hob pre-fitted. Ample storage with soft-close drawers and space for a full-size refrigerator. The kitchen connects to a utility balcony for washing machine placement.", "duration_seconds": 30, "language": "en"},
                "visuals": {"primary_image_url": "https://images.unsplash.com/photo-1556909114-f6e7ad7d3136?w=1200", "labels": ["counter", "cabinets", "modern", "appliances"]},
                "features": [{"name": "Granite Countertops", "category": "countertop"}, {"name": "Chimney & Hob", "category": "appliance"}, {"name": "Soft-close Drawers", "category": "storage"}, {"name": "Utility Balcony", "category": "utility"}],
                "transition": {"type": "slide_left", "duration_ms": 300},
            },
            {
                "index": 4, "id": "balcony", "name": "Panoramic Balcony",
                "room_type": "balcony",
                "narration": {"text": "Step onto your private balcony and enjoy breathtaking views of the Thane creek and the Western Ghats in the distance. The 80 sq ft balcony is perfect for morning tea or evening relaxation. Anti-skid flooring ensures safety even during monsoons.", "duration_seconds": 25, "language": "en"},
                "visuals": {"primary_image_url": "https://images.unsplash.com/photo-1600585154340-be6161a56a0c?w=1200", "labels": ["view", "skyline", "balcony", "greenery"]},
                "features": [{"name": "Creek & Mountain View", "category": "view"}, {"name": "80 sq ft Space", "category": "space"}, {"name": "Anti-skid Flooring", "category": "safety"}],
                "transition": {"type": "slide_left", "duration_ms": 300},
            },
            {
                "index": 5, "id": "bathroom", "name": "Premium Bathroom",
                "room_type": "bathroom",
                "narration": {"text": "The bathrooms feature premium Kohler or equivalent fittings, anti-skid tiles, rain shower, and hot-cold mixer. Wall-mounted western WC with concealed cistern adds a clean modern look.", "duration_seconds": 20, "language": "en"},
                "visuals": {"primary_image_url": "https://images.unsplash.com/photo-1620626011761-996317b8d101?w=1200", "labels": ["shower", "tiles", "modern", "clean"]},
                "features": [{"name": "Kohler Fittings", "category": "brand"}, {"name": "Rain Shower", "category": "fixture"}, {"name": "Anti-skid Tiles", "category": "safety"}],
                "transition": {"type": "slide_left", "duration_ms": 300},
            },
            {
                "index": 6, "id": "amenities", "name": "World-Class Amenities",
                "room_type": "amenities",
                "narration": {"text": "Lodha Crown offers over 20 world-class amenities including an infinity swimming pool, fully equipped gymnasium, children's play area, jogging track, multipurpose court, landscaped gardens, and a grand clubhouse with party hall. RERA registered: MH/2024/45678.", "duration_seconds": 35, "language": "en"},
                "visuals": {"primary_image_url": "https://images.unsplash.com/photo-1576013551627-0cc20b96c2a7?w=1200", "labels": ["pool", "gym", "garden", "clubhouse"]},
                "features": [{"name": "Infinity Pool", "category": "fitness"}, {"name": "Gymnasium", "category": "fitness"}, {"name": "Children's Play Area", "category": "recreation"}, {"name": "Jogging Track", "category": "fitness"}, {"name": "Clubhouse", "category": "social"}, {"name": "RERA: MH/2024/45678", "category": "legal"}],
                "transition": {"type": "fade", "duration_ms": 300},
            },
        ],
    },
}


# ---- Tour Script Loading Endpoint ----


class TourLoadResponse(BaseModel):
    """Response for loading a tour via share link."""
    tour_script: dict
    session_id: str
    session_token: str
    project_name: str


@router.get(
    "/link/{link_id}",
    response_model=TourLoadResponse,
    summary="Load tour by share link",
    description="Load tour script and create anonymous session for a share link.",
)
async def load_tour(
    link_id: str,
    db: AsyncSession = Depends(get_db),
) -> TourLoadResponse:
    """Load tour script and create a buyer session from a share link.

    Looks up the share link, finds the project's tour script,
    creates an anonymous session, and returns everything the
    frontend needs to render the tour.
    """
    # Look up share link
    try:
        link_uuid = uuid.UUID(link_id)
    except ValueError:
        raise HTTPException(status_code=400, detail="Invalid link ID")

    result = await db.execute(select(ShareLink).where(ShareLink.id == link_uuid))
    share_link = result.scalar_one_or_none()

    if not share_link:
        raise HTTPException(status_code=404, detail="Tour link not found or expired")

    # Get project
    proj_result = await db.execute(select(Project).where(Project.id == share_link.project_id))
    project = proj_result.scalar_one_or_none()

    if not project or project.tour_status != "tour_ready":
        raise HTTPException(status_code=404, detail="Tour not available for this project")

    # Get tour script (from demo data or S3 in production)
    tour_script = DEMO_TOUR_SCRIPTS.get(project.name)
    if not tour_script:
        # Generate a default tour script for any project
        tour_script = {
            "schema_version": "1.0.0",
            "project_name": project.name,
            "total_rooms": 5,
            "estimated_duration_seconds": 150,
            "rooms": [
                {"index": 0, "id": "living", "name": "Living Room", "room_type": "living_room", "narration": {"text": f"Welcome to {project.name}. This spacious living room features modern design and natural lighting.", "duration_seconds": 25, "language": "en"}, "visuals": {"primary_image_url": "https://images.unsplash.com/photo-1600210492486-724fe5c67fb0?w=1200", "labels": []}, "features": [{"name": "Modern Design", "category": "design"}], "transition": {"type": "fade", "duration_ms": 300}},
                {"index": 1, "id": "bedroom", "name": "Master Bedroom", "room_type": "bedroom", "narration": {"text": "The master bedroom offers a peaceful retreat with ample wardrobe space.", "duration_seconds": 25, "language": "en"}, "visuals": {"primary_image_url": "https://images.unsplash.com/photo-1616594039964-ae9021a400a0?w=1200", "labels": []}, "features": [{"name": "Spacious", "category": "space"}], "transition": {"type": "slide_left", "duration_ms": 300}},
                {"index": 2, "id": "kitchen", "name": "Kitchen", "room_type": "kitchen", "narration": {"text": "A fully modular kitchen with premium countertops and ample storage.", "duration_seconds": 25, "language": "en"}, "visuals": {"primary_image_url": "https://images.unsplash.com/photo-1556909114-f6e7ad7d3136?w=1200", "labels": []}, "features": [{"name": "Modular", "category": "design"}], "transition": {"type": "slide_left", "duration_ms": 300}},
                {"index": 3, "id": "balcony", "name": "Balcony", "room_type": "balcony", "narration": {"text": "Enjoy stunning views from your private balcony.", "duration_seconds": 20, "language": "en"}, "visuals": {"primary_image_url": "https://images.unsplash.com/photo-1600585154340-be6161a56a0c?w=1200", "labels": []}, "features": [{"name": "City View", "category": "view"}], "transition": {"type": "slide_left", "duration_ms": 300}},
                {"index": 4, "id": "amenities", "name": "Amenities", "room_type": "amenities", "narration": {"text": f"{project.name} offers premium amenities including pool, gym, and landscaped gardens.", "duration_seconds": 30, "language": "en"}, "visuals": {"primary_image_url": "https://images.unsplash.com/photo-1576013551627-0cc20b96c2a7?w=1200", "labels": []}, "features": [{"name": "Pool", "category": "fitness"}, {"name": "Gym", "category": "fitness"}], "transition": {"type": "fade", "duration_ms": 300}},
            ],
        }

    # Create anonymous session
    cp_id = str(share_link.cp_id)
    project_id = str(share_link.project_id)
    session_id = str(uuid.uuid4())

    repo = SessionRepository()
    await repo.create_session(
        session_id=session_id,
        cp_id=cp_id,
        project_id=project_id,
        link_id=link_id,
    )

    # Generate session token
    session_token = create_access_token(
        data={
            "sub": session_id,
            "phone": "",
            "role": "buyer",
            "session_id": session_id,
            "cp_id": cp_id,
            "project_id": project_id,
        },
        expires_delta=timedelta(hours=1),
    )

    return TourLoadResponse(
        tour_script=tour_script,
        session_id=session_id,
        session_token=session_token,
        project_name=project.name,
    )


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
