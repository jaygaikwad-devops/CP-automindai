"""CP Dashboard API endpoints.

Provides stats, hot leads list, lead detail, and real-time WebSocket
push for dashboard updates.

Requirements: 2.1, 2.2, 2.3, 2.4, 2.5
"""

import logging
import uuid
from datetime import datetime, timezone
from typing import Any

from fastapi import APIRouter, Depends, HTTPException, Query, WebSocket, WebSocketDisconnect, status
from pydantic import BaseModel
from sqlalchemy import func, select
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.database import get_db
from app.core.security import get_current_user
from app.models.lead import Lead
from app.models.partnership import Partnership
from app.models.project import Project
from app.models.share_link import ShareLink
from app.services.redis_cache import RedisCache, get_redis

logger = logging.getLogger(__name__)

router = APIRouter()

# ---- Dashboard WebSocket connection registry ----
# cp_id → set of active WebSocket connections
_cp_dashboard_connections: dict[str, set[WebSocket]] = {}


# ---- Response models ----


class DashboardStatsResponse(BaseModel):
    month: str
    tours_shared: int
    leads_generated: int
    hot_leads: int
    conversions: int


class SignalItem(BaseModel):
    type: str
    points: int


class LeadSummary(BaseModel):
    lead_id: str
    buyer_name: str | None
    buyer_phone: str | None
    project_name: str
    score: int
    classification: str
    signals: list[SignalItem]
    created_at: str


class SessionEvent(BaseModel):
    type: str
    timestamp: str
    data: dict[str, Any]


class LeadDetail(BaseModel):
    lead_id: str
    buyer_name: str | None
    buyer_phone: str | None
    project_name: str
    score: int
    classification: str
    signals: list[SignalItem]
    events: list[SessionEvent]


class HotLeadsResponse(BaseModel):
    leads: list[LeadSummary]
    total: int


# ---- Helper: resolve CP's project IDs ----


async def _get_cp_project_ids(cp_id: str, db: AsyncSession) -> list[uuid.UUID]:
    """Return list of project UUIDs the CP has access to."""
    try:
        cp_uuid = uuid.UUID(cp_id)
    except ValueError:
        return []
    result = await db.execute(
        select(Partnership.project_id).where(
            Partnership.cp_id == cp_uuid
        )
    )
    return [row[0] for row in result.all()]


# ---- 16.1: Dashboard stats ----


@router.get("/stats", response_model=DashboardStatsResponse)
async def get_dashboard_stats(
    current_user: dict = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
    redis: RedisCache = Depends(get_redis),
) -> DashboardStatsResponse:
    """Return current-month stats for the authenticated CP.

    Stats are cached in Redis for 60 seconds to reduce DB load.

    Requirements: 2.1, 2.5
    """
    cp_id = current_user.get("sub", "")
    month = datetime.now(timezone.utc).strftime("%Y-%m")
    cache_key = f"dashboard:{cp_id}:{month}"

    # Attempt cache hit
    cached = await redis.get_dashboard_stats(cp_id, month)
    if cached:
        return DashboardStatsResponse(month=month, **cached)

    project_ids = await _get_cp_project_ids(cp_id, db)

    if not project_ids:
        stats = DashboardStatsResponse(
            month=month,
            tours_shared=0,
            leads_generated=0,
            hot_leads=0,
            conversions=0,
        )
        await redis.set_dashboard_stats(cp_id, month, stats.model_dump(exclude={"month"}))
        return stats

    # Month boundaries
    now = datetime.now(timezone.utc)
    month_start = now.replace(day=1, hour=0, minute=0, second=0, microsecond=0)

    # Tours shared this month
    try:
        cp_uuid = uuid.UUID(cp_id)
    except ValueError:
        return DashboardStatsResponse(month=month, tours_shared=0, leads_generated=0, hot_leads=0, conversions=0)

    tours_result = await db.execute(
        select(func.count(ShareLink.id)).where(
            ShareLink.cp_id == cp_uuid,
            ShareLink.created_at >= month_start,
        )
    )
    tours_shared = tours_result.scalar_one() or 0

    # Leads generated (all leads for this CP's projects)
    leads_result = await db.execute(
        select(func.count(Lead.id)).where(
            Lead.cp_id == cp_uuid,
            Lead.created_at >= month_start,
        )
    )
    leads_generated = leads_result.scalar_one() or 0

    # Hot leads (score >= 7)
    hot_result = await db.execute(
        select(func.count(Lead.id)).where(
            Lead.cp_id == cp_uuid,
            Lead.score >= 7,
            Lead.created_at >= month_start,
        )
    )
    hot_leads = hot_result.scalar_one() or 0

    # Conversions (visit_booked classification)
    conv_result = await db.execute(
        select(func.count(Lead.id)).where(
            Lead.cp_id == cp_uuid,
            Lead.classification == "visit_booked",
            Lead.created_at >= month_start,
        )
    )
    conversions = conv_result.scalar_one() or 0

    stats_data = {
        "tours_shared": tours_shared,
        "leads_generated": leads_generated,
        "hot_leads": hot_leads,
        "conversions": conversions,
    }
    await redis.set_dashboard_stats(cp_id, month, stats_data)

    return DashboardStatsResponse(month=month, **stats_data)


# ---- 16.2: Hot leads list ----


@router.get("/hot-leads", response_model=HotLeadsResponse)
async def get_hot_leads(
    limit: int = Query(default=50, ge=1, le=50),
    offset: int = Query(default=0, ge=0),
    current_user: dict = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
) -> HotLeadsResponse:
    """Return hot leads for the authenticated CP, sorted by score descending.

    Returns up to 50 leads. Each lead includes signal breakdown.

    Requirements: 2.2
    """
    cp_id = current_user.get("sub", "")

    # Join Lead with Project to get project name
    try:
        cp_uuid = uuid.UUID(cp_id)
    except ValueError:
        return HotLeadsResponse(leads=[], total=0)

    stmt = (
        select(Lead, Project.name.label("project_name"))
        .join(Project, Lead.project_id == Project.id)
        .where(Lead.cp_id == cp_uuid)
        .order_by(Lead.score.desc())
        .limit(limit)
        .offset(offset)
    )
    result = await db.execute(stmt)
    rows = result.all()

    # Count total for pagination
    count_stmt = select(func.count(Lead.id)).where(
        Lead.cp_id == cp_uuid
    )
    total = (await db.execute(count_stmt)).scalar_one() or 0

    leads = []
    for lead, project_name in rows:
        signals = [
            SignalItem(type=s["type"], points=s.get("points", 0))
            for s in (lead.signals or [])
        ]
        leads.append(LeadSummary(
            lead_id=str(lead.id),
            buyer_name=lead.buyer_name,
            buyer_phone=lead.buyer_phone,
            project_name=project_name or "Unknown",
            score=lead.score,
            classification=lead.classification,
            signals=signals,
            created_at=lead.created_at.isoformat() if lead.created_at else "",
        ))

    return HotLeadsResponse(leads=leads, total=total)


# ---- 16.4: Lead detail ----


@router.get("/leads/{lead_id}", response_model=LeadDetail)
async def get_lead_detail(
    lead_id: str,
    current_user: dict = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
) -> LeadDetail:
    """Return full detail for a single lead.

    Enforces multi-tenant isolation: returns 403 if lead belongs to another CP.
    Fetches chronological session events from DynamoDB.

    Requirements: 2.4
    """
    cp_id = current_user.get("sub", "")

    stmt = (
        select(Lead, Project.name.label("project_name"))
        .join(Project, Lead.project_id == Project.id)
        .where(Lead.id == uuid.UUID(lead_id))
    )
    result = await db.execute(stmt)
    row = result.first()

    if not row:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Lead not found")

    lead, project_name = row

    # Multi-tenant isolation: 403 if lead doesn't belong to CP
    if str(lead.cp_id) != cp_id:
        raise HTTPException(status_code=status.HTTP_403_FORBIDDEN, detail="Access denied")

    signals = [
        SignalItem(type=s["type"], points=s.get("points", 0))
        for s in (lead.signals or [])
    ]

    # Fetch session events from DynamoDB
    events: list[SessionEvent] = []
    try:
        from app.services.dynamodb_session import SessionRepository
        repo = SessionRepository()
        raw_events = await repo.get_session_events(lead.session_id)
        events = [
            SessionEvent(
                type=e.get("type", "unknown"),
                timestamp=e.get("timestamp", ""),
                data=e.get("data", {}),
            )
            for e in raw_events
        ]
    except Exception as e:
        logger.warning(f"Could not fetch session events for {lead.session_id}: {e}")

    return LeadDetail(
        lead_id=str(lead.id),
        buyer_name=lead.buyer_name,
        buyer_phone=lead.buyer_phone,
        project_name=project_name or "Unknown",
        score=lead.score,
        classification=lead.classification,
        signals=signals,
        events=events,
    )


# ---- 16.5: Dashboard WebSocket push ----


@router.websocket("/ws")
async def dashboard_websocket(
    websocket: WebSocket,
    current_user: dict = Depends(get_current_user),
) -> None:
    """WebSocket endpoint for real-time CP dashboard updates.

    CPs connect here to receive push notifications when a new hot lead
    is detected (within 3 seconds per Requirement 2.3).

    The server pushes `hot_lead_update` events; the client just listens.

    Requirements: 2.3
    """
    cp_id = current_user.get("sub", "")
    await websocket.accept()

    if cp_id not in _cp_dashboard_connections:
        _cp_dashboard_connections[cp_id] = set()
    _cp_dashboard_connections[cp_id].add(websocket)

    logger.info(f"CP dashboard WebSocket connected: cp_id={cp_id}")

    try:
        # Keep connection alive — client sends pings, server echos
        while True:
            data = await websocket.receive_text()
            if data == "ping":
                await websocket.send_text("pong")
    except WebSocketDisconnect:
        logger.info(f"CP dashboard WebSocket disconnected: cp_id={cp_id}")
    finally:
        if cp_id in _cp_dashboard_connections:
            _cp_dashboard_connections[cp_id].discard(websocket)


async def push_hot_lead_update(cp_id: str, lead_data: dict) -> None:
    """Push a hot_lead_update event to all connected CP dashboard clients.

    Called by `check_and_alert` after a lead crosses the threshold.
    Updates are delivered within 3 seconds per Requirement 2.3.

    Args:
        cp_id: The CP to notify.
        lead_data: Lead summary dict to push.
    """
    connections = _cp_dashboard_connections.get(cp_id, set())
    if not connections:
        return

    message = {"type": "hot_lead_update", "lead": lead_data}
    dead = set()

    for ws in connections:
        try:
            import json as _json
            await ws.send_text(_json.dumps(message))
        except Exception:
            dead.add(ws)

    # Prune dead connections
    if dead:
        _cp_dashboard_connections[cp_id] -= dead
