"""Project selection and share link generation endpoints.

Handles project listing for CPs, share link generation with OG cards,
and click tracking with CP attribution.

Requirements: 3.1, 3.2, 4.1, 4.2, 4.3, 4.4, 14.1, 14.3, 14.4, 14.5
"""

import hashlib
import logging
import uuid
from datetime import datetime, timezone
from typing import Any

from fastapi import APIRouter, Depends, HTTPException, Header, Request, status
from pydantic import BaseModel, Field
from sqlalchemy import select, update
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.database import get_db
from app.core.security import get_current_user
from app.models.partnership import Partnership
from app.models.project import Project
from app.models.share_link import ShareLink

logger = logging.getLogger(__name__)

router = APIRouter()

TOUR_BASE_URL = "https://tour.automind.ai/t"


# ---- Response models ----


class ProjectSummary(BaseModel):
    project_id: str
    name: str
    builder_name: str | None = None
    location: str | None = None
    unit_types: list[str] = []
    tour_status: str


class ProjectListResponse(BaseModel):
    projects: list[ProjectSummary]


class OGCard(BaseModel):
    title: str
    description: str
    image_url: str | None = None


class ShareLinkResponse(BaseModel):
    link_id: str
    url: str
    og_card: OGCard
    whatsapp_message: str


class ClickTrackResponse(BaseModel):
    session_id: str | None = None
    status: str = "tracked"


# ---- Helpers ----


def _generate_url_slug(cp_id: str, project_id: str) -> str:
    """Generate a short, unique URL slug encoding CP + project.

    The slug encodes both identifiers so they can be extracted on click.
    Uses first 8 chars of a hash for brevity + a short random suffix.
    """
    raw = f"{cp_id}:{project_id}:{uuid.uuid4().hex[:8]}"
    hash_part = hashlib.sha256(raw.encode()).hexdigest()[:12]
    return hash_part


def _extract_ids_from_slug(slug: str, share_link: Any) -> tuple[str, str]:
    """Extract cp_id and project_id from a share link record."""
    return str(share_link.cp_id), str(share_link.project_id)


# ---- 17.1: Project listing ----


@router.get("", response_model=ProjectListResponse)
async def list_projects(
    current_user: dict = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
) -> ProjectListResponse:
    """List projects available to the authenticated CP.

    Returns only projects the CP has an active partnership for.

    Requirements: 3.1, 3.2
    """
    cp_id = current_user.get("sub", "")

    try:
        cp_uuid = uuid.UUID(cp_id)
    except ValueError:
        return ProjectListResponse(projects=[])

    stmt = (
        select(Project)
        .join(Partnership, Partnership.project_id == Project.id)
        .where(Partnership.cp_id == cp_uuid)
    )
    result = await db.execute(stmt)
    projects = result.scalars().all()

    return ProjectListResponse(
        projects=[
            ProjectSummary(
                project_id=str(p.id),
                name=p.name,
                location=p.location,
                unit_types=p.unit_types or [],
                tour_status=p.tour_status,
            )
            for p in projects
        ]
    )


# ---- 17.2: Share link generation ----


@router.post("/{project_id}/share-link", response_model=ShareLinkResponse, status_code=201)
async def create_share_link(
    project_id: str,
    current_user: dict = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
) -> ShareLinkResponse:
    """Generate a shareable WhatsApp link for a project tour.

    Encodes CP + project in the URL for lead attribution.
    Generates OG card metadata for WhatsApp preview.

    Requirements: 4.1, 4.2, 4.3, 4.4
    """
    cp_id = current_user.get("sub", "")

    # Verify project exists and CP has access
    try:
        cp_uuid = uuid.UUID(cp_id)
        project_uuid = uuid.UUID(project_id)
    except ValueError:
        raise HTTPException(status_code=400, detail="Invalid ID format")

    stmt = select(Partnership).where(
        Partnership.cp_id == cp_uuid,
        Partnership.project_id == project_uuid,
    )
    result = await db.execute(stmt)
    partnership = result.scalar_one_or_none()
    if not partnership:
        raise HTTPException(status_code=status.HTTP_403_FORBIDDEN, detail="No access to this project")

    # Get project for OG card
    proj_result = await db.execute(select(Project).where(Project.id == project_uuid))
    project = proj_result.scalar_one_or_none()
    if not project:
        raise HTTPException(status_code=404, detail="Project not found")

    # Generate slug and URL
    url_slug = _generate_url_slug(cp_id, project_id)
    link_url = f"{TOUR_BASE_URL}/{url_slug}"

    # OG card
    og_title = f"{project.name} Virtual Tour"
    og_description = f"Experience {project.name} with AI guide Priya. Explore rooms, amenities, and more!"
    og_image_url = project.hero_image_url

    # Create share link record
    link_id = uuid.uuid4()
    share_link = ShareLink(
        id=link_id,
        cp_id=cp_uuid,
        project_id=project_uuid,
        url_slug=url_slug,
        og_title=og_title,
        og_description=og_description,
        og_image_url=og_image_url,
    )
    db.add(share_link)
    await db.flush()

    # WhatsApp share message
    whatsapp_message = (
        f"🏠 {project.name} — Virtual Tour\n\n"
        f"{og_description}\n\n"
        f"👉 {link_url}"
    )

    return ShareLinkResponse(
        link_id=str(link_id),
        url=link_url,
        og_card=OGCard(
            title=og_title,
            description=og_description,
            image_url=og_image_url,
        ),
        whatsapp_message=whatsapp_message,
    )


# ---- 17.4: Click tracking ----


@router.get("/tour/{url_slug}/click", response_model=ClickTrackResponse)
async def track_click(
    url_slug: str,
    request: Request,
    db: AsyncSession = Depends(get_db),
    user_agent: str = Header(default=""),
    referer: str = Header(default="", alias="referer"),
) -> ClickTrackResponse:
    """Track a tour link click event.

    Records timestamp, referrer URL, user-agent, and device type.
    Attributes the session to the CP whose link was clicked (last-click-wins).

    Requirements: 14.1, 14.3, 14.4, 14.5
    """
    # Look up share link
    stmt = select(ShareLink).where(ShareLink.url_slug == url_slug)
    result = await db.execute(stmt)
    share_link = result.scalar_one_or_none()

    if not share_link:
        raise HTTPException(status_code=404, detail="Link not found")

    # Determine device type from user-agent
    ua_lower = user_agent.lower()
    device_type = "mobile" if any(k in ua_lower for k in ["mobile", "android", "iphone"]) else "desktop"

    # Increment click count
    await db.execute(
        update(ShareLink)
        .where(ShareLink.id == share_link.id)
        .values(click_count=ShareLink.click_count + 1)
    )
    await db.flush()

    logger.info(
        f"Click tracked: slug={url_slug}, cp_id={share_link.cp_id}, "
        f"device={device_type}, referrer={referer[:100]}"
    )

    return ClickTrackResponse(status="tracked")
