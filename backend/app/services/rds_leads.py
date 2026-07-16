"""RDS leads service for materialized lead data.

Handles upsert operations to the PostgreSQL leads table as part of
the dual-write pattern (DynamoDB → RDS).
"""

import json
import logging
import uuid
from typing import Any

from sqlalchemy import text

logger = logging.getLogger(__name__)


async def upsert_lead(
    session_id: str,
    cp_id: str,
    project_id: str,
    score: int,
    classification: str,
    signals: list[dict[str, Any]],
    buyer_name: str | None = None,
    buyer_phone: str | None = None,
) -> None:
    """Upsert a lead row in the RDS leads table.

    Uses INSERT ... ON CONFLICT to handle both new and existing leads.
    This is the materialized view used by the CP dashboard for queries.

    Args:
        session_id: The session identifier.
        cp_id: Channel partner ID.
        project_id: Project ID.
        score: Current lead score.
        classification: Lead classification.
        signals: List of applied signal dicts.
        buyer_name: Buyer's name if collected.
        buyer_phone: Buyer's phone if collected.
    """
    try:
        from app.core.database import async_session_factory

        async with async_session_factory() as db:
            await db.execute(
                text("""
                    INSERT INTO leads (id, session_id, cp_id, project_id, score, classification, signals, buyer_name, buyer_phone, created_at, updated_at)
                    VALUES (gen_random_uuid(), :session_id, :cp_id, :project_id, :score, :classification, :signals::jsonb, :buyer_name, :buyer_phone, NOW(), NOW())
                    ON CONFLICT (session_id)
                    DO UPDATE SET
                        score = EXCLUDED.score,
                        classification = EXCLUDED.classification,
                        signals = EXCLUDED.signals,
                        buyer_name = COALESCE(EXCLUDED.buyer_name, leads.buyer_name),
                        buyer_phone = COALESCE(EXCLUDED.buyer_phone, leads.buyer_phone),
                        updated_at = NOW()
                """),
                {
                    "session_id": session_id,
                    "cp_id": str(uuid.UUID(cp_id)) if cp_id else None,
                    "project_id": str(uuid.UUID(project_id)) if project_id else None,
                    "score": score,
                    "classification": classification,
                    "signals": json.dumps(signals),
                    "buyer_name": buyer_name,
                    "buyer_phone": buyer_phone,
                },
            )
            await db.commit()

        logger.info(f"RDS lead upserted: session_id={session_id}, score={score}, classification={classification}")

    except Exception as e:
        logger.error(f"RDS upsert_lead failed: {e}")
        raise
