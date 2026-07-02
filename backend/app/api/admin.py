"""Admin API endpoints for AutoMind AI Platform.

Handles project creation, partnership assignment, partnership removal,
asset upload, and processing pipeline trigger.
All endpoints require admin role authorization.
"""

import uuid

from fastapi import APIRouter, Depends, File, Form, HTTPException, UploadFile, status
from pydantic import BaseModel, Field
from sqlalchemy import func, select
from sqlalchemy.exc import IntegrityError
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.config import settings
from app.core.database import get_db
from app.core.exceptions import NotFoundException
from app.core.security import get_current_user
from app.models.cp import CP
from app.models.partnership import Partnership
from app.models.processing_job import ProcessingJob
from app.models.project import Project
from app.models.project_asset import ProjectAsset
from app.services.asset_validation import (
    ALLOWED_MIMES,
    MAX_COUNT,
    MAX_SIZE_BYTES,
    is_processing_eligible,
    is_upload_blocked_by_status,
    validate_asset_upload,
)

router = APIRouter()


# --- Authorization Dependency ---


async def require_admin(current_user: dict = Depends(get_current_user)) -> dict:
    """Require the current user to have admin role.

    Raises:
        HTTPException: 403 if user is not an admin.
    """
    if current_user.get("role") != "admin":
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="Admin access required",
        )
    return current_user


# --- Request/Response Models ---


class CreateProjectBody(BaseModel):
    """Request body for project creation."""

    name: str = Field(..., min_length=1, max_length=255)
    builder_id: str = Field(..., description="UUID of the builder")
    location: str = Field(..., min_length=1, max_length=500)
    unit_types: list[str] = Field(default_factory=list)


class CreateProjectResponse(BaseModel):
    """Response for successful project creation."""

    project_id: str
    status: str


class CreatePartnershipBody(BaseModel):
    """Request body for partnership assignment."""

    cp_id: str = Field(..., description="UUID of the CP")
    project_id: str = Field(..., description="UUID of the project")


class CreatePartnershipResponse(BaseModel):
    """Response for successful partnership creation."""

    partnership_id: str


# --- Endpoints ---


@router.post("/projects", response_model=CreateProjectResponse, status_code=status.HTTP_201_CREATED)
async def create_project(
    body: CreateProjectBody,
    admin_user: dict = Depends(require_admin),
    db: AsyncSession = Depends(get_db),
):
    """Create a new project with builder association.

    Admin-only endpoint. Sets initial tour_status to 'not_started'.
    """
    project_id = uuid.uuid4()

    project = Project(
        id=project_id,
        builder_id=uuid.UUID(body.builder_id),
        name=body.name,
        location=body.location,
        unit_types=body.unit_types,
        tour_status="not_started",
    )
    db.add(project)
    await db.flush()

    return CreateProjectResponse(project_id=str(project_id), status="not_started")


@router.post("/partnerships", response_model=CreatePartnershipResponse, status_code=status.HTTP_201_CREATED)
async def create_partnership(
    body: CreatePartnershipBody,
    admin_user: dict = Depends(require_admin),
    db: AsyncSession = Depends(get_db),
):
    """Assign a CP to a project, creating a partnership record.

    Looks up the project to get builder_id automatically.
    Returns 404 if project or CP not found, 409 if duplicate.
    """
    # Look up the project to get builder_id
    result = await db.execute(
        select(Project).where(Project.id == uuid.UUID(body.project_id))
    )
    project = result.scalar_one_or_none()
    if not project:
        raise NotFoundException(message="Project not found")

    # Look up the CP to verify it exists
    cp_result = await db.execute(
        select(CP).where(CP.id == uuid.UUID(body.cp_id))
    )
    cp = cp_result.scalar_one_or_none()
    if not cp:
        raise NotFoundException(message="CP not found")

    # Create partnership record
    partnership_id = uuid.uuid4()
    partnership = Partnership(
        id=partnership_id,
        cp_id=uuid.UUID(body.cp_id),
        builder_id=project.builder_id,
        project_id=uuid.UUID(body.project_id),
    )
    db.add(partnership)

    try:
        await db.flush()
    except IntegrityError:
        await db.rollback()
        raise HTTPException(
            status_code=status.HTTP_409_CONFLICT,
            detail="Partnership already exists for this CP and project",
        )

    return CreatePartnershipResponse(partnership_id=str(partnership_id))


@router.delete("/partnerships/{partnership_id}", status_code=status.HTTP_204_NO_CONTENT)
async def delete_partnership(
    partnership_id: str,
    admin_user: dict = Depends(require_admin),
    db: AsyncSession = Depends(get_db),
):
    """Remove a partnership, revoking CP access to the project.

    Returns 404 if partnership not found.
    """
    result = await db.execute(
        select(Partnership).where(Partnership.id == uuid.UUID(partnership_id))
    )
    partnership = result.scalar_one_or_none()

    if not partnership:
        raise NotFoundException(message="Partnership not found")

    await db.delete(partnership)
    await db.flush()



# --- Asset Upload Response Models ---


class AssetUploadResponse(BaseModel):
    """Response for successful asset upload."""

    asset_id: str
    s3_key: str


class ProcessingTriggerResponse(BaseModel):
    """Response for successful processing trigger."""

    job_id: str
    status: str


# --- Asset Upload Endpoint ---


@router.post(
    "/projects/{project_id}/assets",
    response_model=AssetUploadResponse,
    status_code=status.HTTP_201_CREATED,
)
async def upload_asset(
    project_id: str,
    file: UploadFile = File(...),
    asset_type: str = Form(...),
    admin_user: dict = Depends(require_admin),
    db: AsyncSession = Depends(get_db),
):
    """Upload an asset file for a project.

    Admin-only endpoint. Validates format, size, and count limits.
    Blocks uploads if project is processing_in_progress or tour_ready.
    """
    # Validate asset_type
    if asset_type not in ALLOWED_MIMES:
        raise HTTPException(
            status_code=status.HTTP_415_UNSUPPORTED_MEDIA_TYPE,
            detail={
                "error": "unsupported_format",
                "accepted_types": list(ALLOWED_MIMES.keys()),
            },
        )

    # Look up project
    result = await db.execute(
        select(Project).where(Project.id == uuid.UUID(project_id))
    )
    project = result.scalar_one_or_none()
    if not project:
        raise NotFoundException(message="Project not found")

    # Check project status
    if is_upload_blocked_by_status(project.tour_status):
        raise HTTPException(
            status_code=status.HTTP_409_CONFLICT,
            detail={
                "error": "upload_blocked",
                "message": f"Cannot upload assets while project is in '{project.tour_status}' status",
            },
        )

    # Read file content
    file_data = await file.read()
    file_size = len(file_data)
    mime_type = file.content_type or ""

    # Count existing assets of this type for this project
    count_result = await db.execute(
        select(func.count(ProjectAsset.id)).where(
            ProjectAsset.project_id == uuid.UUID(project_id),
            ProjectAsset.asset_type == asset_type,
        )
    )
    existing_count = count_result.scalar_one()

    # Validate the upload
    is_valid, error_code = validate_asset_upload(
        asset_type, mime_type, file_size, existing_count
    )

    if not is_valid:
        if error_code == 415:
            accepted = list(ALLOWED_MIMES.get(asset_type, set()))
            raise HTTPException(
                status_code=status.HTTP_415_UNSUPPORTED_MEDIA_TYPE,
                detail={
                    "error": "unsupported_format",
                    "accepted": accepted,
                },
            )
        elif error_code == 413:
            max_mb = MAX_SIZE_BYTES[asset_type] // (1024 * 1024)
            raise HTTPException(
                status_code=status.HTTP_413_REQUEST_ENTITY_TOO_LARGE,
                detail={
                    "error": "file_too_large",
                    "max_size_mb": max_mb,
                },
            )
        else:  # 409 - count exceeded
            raise HTTPException(
                status_code=status.HTTP_409_CONFLICT,
                detail={
                    "error": "count_exceeded",
                    "max_count": MAX_COUNT[asset_type],
                },
            )

    # Upload to S3
    filename = file.filename or f"{uuid.uuid4()}.bin"
    s3_key = f"projects/{project_id}/{asset_type}/{filename}"

    from app.services.s3_service import upload_file

    await upload_file(
        bucket=settings.s3_assets_bucket,
        key=s3_key,
        file_data=file_data,
        content_type=mime_type,
    )

    # Create asset record
    asset_id = uuid.uuid4()
    asset = ProjectAsset(
        id=asset_id,
        project_id=uuid.UUID(project_id),
        asset_type=asset_type,
        file_name=filename,
        s3_key=s3_key,
        file_size_bytes=file_size,
        mime_type=mime_type,
    )
    db.add(asset)
    await db.flush()

    return AssetUploadResponse(asset_id=str(asset_id), s3_key=s3_key)


# --- Processing Trigger Endpoint ---


@router.post(
    "/projects/{project_id}/process",
    response_model=ProcessingTriggerResponse,
    status_code=status.HTTP_202_ACCEPTED,
)
async def trigger_processing(
    project_id: str,
    admin_user: dict = Depends(require_admin),
    db: AsyncSession = Depends(get_db),
):
    """Trigger the processing pipeline for a project.

    Admin-only endpoint. Validates that minimum assets are present:
    at least 10 images and exactly 1 floor plan.
    Deducts 1 credit from the CP's balance before processing.
    """
    # Look up project
    result = await db.execute(
        select(Project).where(Project.id == uuid.UUID(project_id))
    )
    project = result.scalar_one_or_none()
    if not project:
        raise NotFoundException(message="Project not found")

    # Find the CP associated with this project via partnership
    from sqlalchemy import text as sa_text
    from app.models.credit_transaction import CreditTransaction

    partnership_result = await db.execute(
        select(Partnership.cp_id).where(Partnership.project_id == uuid.UUID(project_id))
    )
    partnership_row = partnership_result.first()
    if not partnership_row:
        raise HTTPException(
            status_code=status.HTTP_422_UNPROCESSABLE_ENTITY,
            detail={"error": "no_cp_assigned", "message": "No CP assigned to this project"},
        )
    cp_uuid = partnership_row[0]

    # Credit check — atomic deduction in single transaction
    # Lock the row to prevent concurrent deductions
    credit_result = await db.execute(
        sa_text("SELECT credit_balance FROM cps WHERE id = :cp_id FOR UPDATE"),
        {"cp_id": str(cp_uuid)},
    )
    row = credit_result.first()
    balance = row[0] if row else 0

    if balance < 1:
        raise HTTPException(
            status_code=status.HTTP_402_PAYMENT_REQUIRED,
            detail={"error": "insufficient_credits", "balance": balance},
        )

    # Deduct 1 credit
    await db.execute(
        sa_text("UPDATE cps SET credit_balance = credit_balance - 1 WHERE id = :cp_id"),
        {"cp_id": str(cp_uuid)},
    )

    # Record deduction transaction (SAME transaction — rolls back together if anything fails)
    deduction = CreditTransaction(
        cp_id=cp_uuid,
        type="deduction",
        amount=-1,
        project_id=uuid.UUID(project_id),
    )
    db.add(deduction)

    # Count assets by type using group_by
    count_result = await db.execute(
        select(ProjectAsset.asset_type, func.count(ProjectAsset.id))
        .where(ProjectAsset.project_id == uuid.UUID(project_id))
        .group_by(ProjectAsset.asset_type)
    )
    asset_counts: dict[str, int] = {}
    for row in count_result.all():
        asset_counts[row[0]] = row[1]

    image_count = asset_counts.get("image", 0)
    floor_plan_count = asset_counts.get("floor_plan", 0)

    # Validate eligibility
    eligible, error_reason = is_processing_eligible(image_count, floor_plan_count)
    if not eligible:
        raise HTTPException(
            status_code=status.HTTP_422_UNPROCESSABLE_ENTITY,
            detail={"error": error_reason},
        )

    # Update project status
    project.tour_status = "processing_in_progress"

    # Create processing job
    job_id = uuid.uuid4()
    job = ProcessingJob(
        id=job_id,
        project_id=uuid.UUID(project_id),
        status="queued",
    )
    db.add(job)
    await db.flush()

    # Send SQS message
    import aioboto3

    sqs_session = aioboto3.Session(
        aws_access_key_id=settings.aws_access_key_id or None,
        aws_secret_access_key=settings.aws_secret_access_key or None,
        region_name=settings.aws_region,
    )

    if settings.sqs_processing_queue_url:
        import json

        async with sqs_session.client("sqs") as sqs_client:
            await sqs_client.send_message(
                QueueUrl=settings.sqs_processing_queue_url,
                MessageBody=json.dumps({
                    "job_id": str(job_id),
                    "project_id": project_id,
                    "job_type": "image_analysis",
                }),
            )

    return ProcessingTriggerResponse(
        job_id=str(job_id), status="processing_in_progress"
    )
