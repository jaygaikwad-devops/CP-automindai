"""RDS leads service for materialized lead data.

Handles upsert operations to the PostgreSQL leads table as part of
the dual-write pattern (DynamoDB → RDS).
"""

import logging
from typing import Any

logger = logging.getLogger(__name__)


async def upsert_lead(
    session_id: str,
    cp_id: str,
    project_id: str,
    score: int,
    classification: str,
    signals: list[dict[str, Any]],
) -> None:
    """Upsert a lead row in the RDS leads table.

    This is the materialized view used by the CP dashboard for queries.
    DynamoDB remains the source of truth.

    Args:
        session_id: The session identifier.
        cp_id: Channel partner ID.
        project_id: Project ID.
        score: Current lead score.
        classification: Lead classification.
        signals: List of applied signal dicts.
    """
    # Placeholder for actual database operations
    # In production, this uses asyncpg to write to PostgreSQL
    logger.info(
        f"RDS upsert: session_id={session_id}, score={score}, "
        f"classification={classification}"
    )
