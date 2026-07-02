"""Authentication API endpoints for AutoMind AI Platform.

Handles OTP request/verify, CP registration, and anonymous buyer sessions.
"""

import uuid
from datetime import datetime, timedelta, timezone

import aioboto3
from fastapi import APIRouter, Cookie, Depends, HTTPException, Response, status
from pydantic import BaseModel, Field
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.config import settings
from app.core.database import get_db
from app.core.exceptions import NotFoundException
from app.core.security import create_access_token, get_current_user
from app.core.validators import validate_indian_phone, validate_rera_id
from app.models.cp import CP
from app.models.share_link import ShareLink
from app.services.dynamodb_session import SessionRepository
from app.services.redis_cache import RedisCache, get_redis

router = APIRouter()


# --- Request/Response Models ---


class OTPRequestBody(BaseModel):
    """Request body for OTP request endpoint."""

    phone: str = Field(..., description="10-digit Indian mobile number")


class OTPRequestResponse(BaseModel):
    """Response for successful OTP request."""

    message: str = "OTP sent"
    expires_in: int = 300


class OTPVerifyBody(BaseModel):
    """Request body for OTP verification endpoint."""

    phone: str = Field(..., description="10-digit Indian mobile number")
    otp: str = Field(..., description="6-digit OTP code")


class OTPVerifyResponse(BaseModel):
    """Response for successful OTP verification."""

    token: str
    expires_in: int = 86400
    is_new_user: bool


class RegisterBody(BaseModel):
    """Request body for CP registration endpoint."""

    name: str = Field(..., min_length=1, max_length=255)
    rera_id: str = Field(..., description="RERA ID in format RERA/{state}/{year}/{number}")


class RegisterResponse(BaseModel):
    """Response for successful CP registration."""

    cp_id: str
    name: str
    rera_id: str


class AnonymousSessionBody(BaseModel):
    """Request body for anonymous session creation."""

    link_id: str = Field(..., description="Share link UUID")


class AnonymousSessionResponse(BaseModel):
    """Response for anonymous session creation."""

    session_id: str
    session_token: str


# --- Helper to get Cognito client ---


def _get_cognito_session() -> aioboto3.Session:
    """Get an aioboto3 session for Cognito calls."""
    return aioboto3.Session(
        aws_access_key_id=settings.aws_access_key_id or None,
        aws_secret_access_key=settings.aws_secret_access_key or None,
        region_name=settings.aws_region,
    )


# --- Endpoints ---


@router.post("/otp/request", response_model=OTPRequestResponse)
async def request_otp(
    body: OTPRequestBody,
    redis: RedisCache = Depends(get_redis),
):
    """Request an OTP for phone number authentication.

    Validates the phone number, checks rate limits, and initiates
    Cognito custom auth challenge to send OTP via SMS.
    """
    # Validate phone number format
    if not validate_indian_phone(body.phone):
        raise HTTPException(
            status_code=status.HTTP_422_UNPROCESSABLE_ENTITY,
            detail={
                "error": {
                    "code": "invalid_phone",
                    "message": "Invalid phone number. Must be 10 digits starting with 6-9.",
                }
            },
        )

    # Check rate limit
    is_limited, remaining_seconds = await redis.check_otp_rate_limit(body.phone)
    if is_limited:
        raise HTTPException(
            status_code=status.HTTP_429_TOO_MANY_REQUESTS,
            detail={
                "error": {
                    "code": "rate_limited",
                    "message": "Too many OTP requests. Please try again later.",
                    "retry_after": remaining_seconds,
                }
            },
        )

    # Increment rate counter
    await redis.increment_otp_rate(body.phone)

    # Initiate Cognito custom auth
    if settings.environment == "development":
        # Dev mode: skip Cognito, OTP is always 123456
        pass
    else:
        session = _get_cognito_session()
        async with session.client("cognito-idp", region_name=settings.aws_region) as cognito:
            try:
                await cognito.initiate_auth(
                    AuthFlow="CUSTOM_AUTH",
                    ClientId=settings.cognito_client_id,
                    AuthParameters={"USERNAME": body.phone},
                )
            except Exception:
                # Log but don't expose internal errors to user
                # OTP delivery is handled by Cognito Lambda triggers
                pass

    return OTPRequestResponse(message="OTP sent", expires_in=300)


@router.post("/otp/verify", response_model=OTPVerifyResponse)
async def verify_otp(
    body: OTPVerifyBody,
    redis: RedisCache = Depends(get_redis),
    db: AsyncSession = Depends(get_db),
):
    """Verify an OTP and issue a JWT session token.

    Validates the OTP against Cognito, tracks failed attempts,
    and locks the phone number after 3 consecutive failures.
    """
    # Validate phone format
    if not validate_indian_phone(body.phone):
        raise HTTPException(
            status_code=status.HTTP_422_UNPROCESSABLE_ENTITY,
            detail={
                "error": {
                    "code": "invalid_phone",
                    "message": "Invalid phone number. Must be 10 digits starting with 6-9.",
                }
            },
        )

    # Check if phone is locked due to failed attempts
    attempts_key = f"otp_attempts:{body.phone}"
    current_attempts = await redis.client.get(attempts_key)
    if current_attempts and int(current_attempts) >= 3:
        ttl = await redis.client.ttl(attempts_key)
        unlock_at = datetime.now(timezone.utc) + timedelta(seconds=max(ttl, 0))
        raise HTTPException(
            status_code=status.HTTP_423_LOCKED,
            detail={
                "error": {
                    "code": "locked",
                    "message": "Account locked due to too many failed attempts.",
                    "unlock_at": unlock_at.isoformat(),
                }
            },
        )

    # Verify OTP with Cognito
    is_new_user = False
    cognito_sub = ""

    # Dev mode: accept fixed OTP 123456
    if settings.environment == "development":
        if body.otp != "123456":
            attempt_count = await redis.increment_otp_attempts(body.phone)
            attempts_remaining = max(0, 3 - attempt_count)
            raise HTTPException(
                status_code=status.HTTP_401_UNAUTHORIZED,
                detail={
                    "error": {
                        "code": "invalid_otp",
                        "message": "Invalid OTP. Use 123456 in dev mode.",
                        "attempts_remaining": attempts_remaining,
                    }
                },
            )
        # Generate a deterministic sub from phone for dev
        cognito_sub = str(uuid.uuid5(uuid.NAMESPACE_DNS, f"dev-{body.phone}"))
        # Check if CP already exists in DB
        result = await db.execute(select(CP).where(CP.phone == body.phone))
        existing_cp = result.scalar_one_or_none()
        is_new_user = existing_cp is None
    else:
        session = _get_cognito_session()
        async with session.client("cognito-idp", region_name=settings.aws_region) as cognito:
            try:
                # First initiate auth to get the session
                init_response = await cognito.initiate_auth(
                    AuthFlow="CUSTOM_AUTH",
                    ClientId=settings.cognito_client_id,
                    AuthParameters={"USERNAME": body.phone},
                )

                # Respond to auth challenge with OTP
                challenge_response = await cognito.respond_to_auth_challenge(
                    ClientId=settings.cognito_client_id,
                    ChallengeName="CUSTOM_CHALLENGE",
                    Session=init_response.get("Session", ""),
                    ChallengeResponses={
                        "USERNAME": body.phone,
                        "ANSWER": body.otp,
                    },
                )

                # Extract user info from successful auth
                auth_result = challenge_response.get("AuthenticationResult", {})
                if not auth_result:
                    raise ValueError("Authentication failed")

                # Get user info to check if new
                user_response = await cognito.get_user(
                    AccessToken=auth_result.get("AccessToken", "")
                )
                cognito_sub = user_response.get("Username", "")
                user_attrs = {
                    attr["Name"]: attr["Value"]
                    for attr in user_response.get("UserAttributes", [])
                }
                is_new_user = "custom:rera_id" not in user_attrs

            except Exception:
                # OTP verification failed - increment attempts
                attempt_count = await redis.increment_otp_attempts(body.phone)
                attempts_remaining = max(0, 3 - attempt_count)

                if attempt_count >= 3:
                    ttl = await redis.client.ttl(attempts_key)
                    unlock_at = datetime.now(timezone.utc) + timedelta(seconds=max(ttl, 0))
                    raise HTTPException(
                        status_code=status.HTTP_423_LOCKED,
                        detail={
                            "error": {
                                "code": "locked",
                                "message": "Account locked due to too many failed attempts.",
                                "unlock_at": unlock_at.isoformat(),
                            }
                        },
                    )

                raise HTTPException(
                    status_code=status.HTTP_401_UNAUTHORIZED,
                    detail={
                        "error": {
                            "code": "invalid_otp",
                            "message": "Invalid OTP.",
                            "attempts_remaining": attempts_remaining,
                        }
                    },
                )

    # Success - reset attempt counter
    await redis.reset_otp_attempts(body.phone)

    # Generate JWT token
    token = create_access_token(
        data={"sub": cognito_sub, "phone": body.phone, "role": "cp"},
        expires_delta=timedelta(hours=24),
    )

    return OTPVerifyResponse(token=token, expires_in=86400, is_new_user=is_new_user)


@router.post("/register", response_model=RegisterResponse, status_code=status.HTTP_201_CREATED)
async def register_cp(
    body: RegisterBody,
    current_user: dict = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
):
    """Register a CP with name and RERA ID.

    Requires authentication. Validates RERA ID format,
    creates CP record in RDS, and updates Cognito user attributes.
    """
    # Validate RERA ID format
    if not validate_rera_id(body.rera_id):
        raise HTTPException(
            status_code=status.HTTP_422_UNPROCESSABLE_ENTITY,
            detail={
                "error": {
                    "code": "invalid_rera_format",
                    "message": "Invalid RERA ID format.",
                    "expected": "RERA/{state}/{year}/{number}",
                }
            },
        )

    cp_id = str(uuid.uuid4())
    cognito_sub = current_user["sub"]
    phone = current_user["phone"]

    # Create CP record in RDS
    cp = CP(
        id=uuid.UUID(cp_id),
        phone=phone,
        name=body.name,
        rera_id=body.rera_id,
        cognito_sub=cognito_sub,
    )
    db.add(cp)
    await db.commit()

    # Update Cognito user attributes
    session = _get_cognito_session()
    async with session.client("cognito-idp", region_name=settings.aws_region) as cognito:
        try:
            await cognito.admin_update_user_attributes(
                UserPoolId=settings.cognito_user_pool_id,
                Username=phone,
                UserAttributes=[
                    {"Name": "custom:rera_id", "Value": body.rera_id},
                    {"Name": "name", "Value": body.name},
                ],
            )
        except Exception:
            # Non-critical - CP record is already created
            pass

    return RegisterResponse(cp_id=cp_id, name=body.name, rera_id=body.rera_id)


@router.post("/session/anonymous", response_model=AnonymousSessionResponse)
async def create_anonymous_session(
    body: AnonymousSessionBody,
    response: Response,
    db: AsyncSession = Depends(get_db),
    session_id: str | None = Cookie(default=None),
):
    """Create an anonymous buyer session for tour viewing.

    Looks up the share link to get CP and project attribution,
    generates a unique session, and returns a short-lived JWT
    for WebSocket authentication.

    Handles return-visit detection via session_id cookie.
    """
    # Look up share link to get cp_id and project_id
    result = await db.execute(
        select(ShareLink).where(ShareLink.id == uuid.UUID(body.link_id))
    )
    share_link = result.scalar_one_or_none()

    if not share_link:
        raise NotFoundException(message="Share link not found.")

    cp_id = str(share_link.cp_id)
    project_id = str(share_link.project_id)

    # Handle return-visit detection
    session_repo = SessionRepository()

    if session_id:
        # Check if existing session is still valid (within 24h)
        existing_session = await session_repo.get_session(session_id)
        if existing_session:
            created_at = existing_session.get("created_at", "")
            try:
                created_dt = datetime.fromisoformat(created_at)
                if datetime.now(timezone.utc) - created_dt < timedelta(hours=24):
                    # Reuse existing session
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
                    return AnonymousSessionResponse(
                        session_id=session_id, session_token=session_token
                    )
            except (ValueError, TypeError):
                pass

    # Create new session
    new_session_id = str(uuid.uuid4())

    await session_repo.create_session(
        session_id=new_session_id,
        cp_id=cp_id,
        project_id=project_id,
        link_id=body.link_id,
    )

    # Generate short-lived JWT for WebSocket auth
    session_token = create_access_token(
        data={
            "sub": new_session_id,
            "phone": "",
            "role": "buyer",
            "session_id": new_session_id,
            "cp_id": cp_id,
            "project_id": project_id,
        },
        expires_delta=timedelta(hours=1),
    )

    # Set session_id cookie for return-visit detection
    response.set_cookie(
        key="session_id",
        value=new_session_id,
        max_age=86400,  # 24 hours
        httponly=True,
        samesite="lax",
    )

    return AnonymousSessionResponse(
        session_id=new_session_id, session_token=session_token
    )
