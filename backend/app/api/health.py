"""Health check endpoint."""

from fastapi import APIRouter

router = APIRouter()


@router.get("/health")
async def health_check() -> dict:
    """Health check endpoint for ALB and container health probes.

    Returns 200 with {"status": "ok"} when the service is healthy.
    """
    return {"status": "ok"}
