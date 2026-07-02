"""Multi-tenant data isolation middleware.

Provides FastAPI dependencies for enforcing project access
based on partnership records.
"""

import uuid

from fastapi import Depends, HTTPException, status
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.database import get_db
from app.core.security import get_current_user
from app.models.partnership import Partnership


async def require_project_access(
    project_id: str,
    current_user: dict = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
) -> dict:
    """Verify the current user has access to the specified project.

    Rules:
    - Admin role: access all projects unconditionally
    - CP role: must have a valid partnership record for the project
    - All other roles: denied

    Args:
        project_id: The UUID string of the project to access.
        current_user: The decoded JWT payload.
        db: Database session.

    Returns:
        The current_user dict if access is granted.

    Raises:
        HTTPException: 403 if access is denied.
    """
    role = current_user.get("role", "")

    # Admins can access everything
    if role == "admin":
        return current_user

    # CPs need a partnership record
    if role == "cp":
        cp_id = current_user.get("cp_id")
        if not cp_id:
            raise HTTPException(
                status_code=status.HTTP_403_FORBIDDEN,
                detail="Access denied: no CP identity found",
            )

        result = await db.execute(
            select(Partnership).where(
                Partnership.cp_id == uuid.UUID(cp_id),
                Partnership.project_id == uuid.UUID(project_id),
            )
        )
        partnership = result.scalar_one_or_none()

        if partnership is None:
            raise HTTPException(
                status_code=status.HTTP_403_FORBIDDEN,
                detail="Access denied: no partnership for this project",
            )

        return current_user

    # All other roles are denied
    raise HTTPException(
        status_code=status.HTTP_403_FORBIDDEN,
        detail="Access denied",
    )
