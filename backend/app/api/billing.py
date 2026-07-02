"""Billing API endpoints for credit pack purchases and Razorpay webhook.

Handles credit pack listing, purchase order creation, and webhook processing
for payment confirmation.
"""

import json
import uuid

import razorpay
from fastapi import APIRouter, Depends, Header, HTTPException, Request, status
from pydantic import BaseModel, Field
from sqlalchemy import text
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.config import settings
from app.core.database import get_db
from app.core.security import get_current_user
from app.models.credit_transaction import CreditTransaction

router = APIRouter()

# --- Credit Pack Definitions ---

CREDIT_PACKS = {
    "starter": {"amount_paise": 99900, "credits": 2, "name": "Starter Pack"},
    "growth": {"amount_paise": 399900, "credits": 10, "name": "Growth Pack"},
    "agency": {"amount_paise": 1499900, "credits": 50, "name": "Agency Pack"},
}


def _get_razorpay_client() -> razorpay.Client:
    """Create and return a Razorpay client instance."""
    return razorpay.Client(auth=(settings.razorpay_key_id, settings.razorpay_key_secret))


# --- Request/Response Models ---


class PackInfo(BaseModel):
    """Credit pack information."""

    pack_type: str
    name: str
    amount_paise: int
    credits: int


class PurchaseRequest(BaseModel):
    """Request body for credit pack purchase."""

    pack_type: str = Field(..., pattern="^(starter|growth|agency)$")


class PurchaseResponse(BaseModel):
    """Response for successful order creation."""

    order_id: str
    amount_paise: int
    credits: int
    razorpay_key_id: str


# --- Auth Dependency ---


async def require_cp(current_user: dict = Depends(get_current_user)) -> dict:
    """Require the current user to have CP role.

    Raises:
        HTTPException: 403 if user is not a CP.
    """
    if current_user.get("role") != "cp":
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="CP access required",
        )
    return current_user


# --- Endpoints ---


@router.get("/packs", response_model=list[PackInfo])
async def list_packs():
    """Return list of available credit packs. No auth required."""
    return [
        PackInfo(
            pack_type=key,
            name=pack["name"],
            amount_paise=pack["amount_paise"],
            credits=pack["credits"],
        )
        for key, pack in CREDIT_PACKS.items()
    ]


@router.post("/purchase", response_model=PurchaseResponse, status_code=status.HTTP_201_CREATED)
async def purchase_credits(
    body: PurchaseRequest,
    current_user: dict = Depends(require_cp),
    db: AsyncSession = Depends(get_db),
):
    """Create a Razorpay order for credit pack purchase.

    CP auth required. Encodes cp_id:pack_type in the receipt field
    so the webhook can link the payment back to the CP.
    """
    pack = CREDIT_PACKS.get(body.pack_type)
    if not pack:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail={"error": "invalid_pack_type", "valid_types": list(CREDIT_PACKS.keys())},
        )

    cp_sub = current_user["sub"]

    # Encode cp_sub and pack_type in receipt for webhook lookup
    receipt = f"{cp_sub}:{body.pack_type}"

    client = _get_razorpay_client()
    order_data = {
        "amount": pack["amount_paise"],
        "currency": "INR",
        "receipt": receipt,
    }
    order = client.order.create(data=order_data)

    return PurchaseResponse(
        order_id=order["id"],
        amount_paise=pack["amount_paise"],
        credits=pack["credits"],
        razorpay_key_id=settings.razorpay_key_id,
    )


@router.post("/webhook", status_code=status.HTTP_200_OK)
async def razorpay_webhook(
    request: Request,
    db: AsyncSession = Depends(get_db),
):
    """Handle Razorpay payment webhooks.

    NO AUTH required — excluded from JWT middleware.
    Verifies signature using Razorpay webhook secret.
    On payment.captured: credits the CP's balance and records the transaction.
    """
    # Read raw body for signature verification
    body_bytes = await request.body()
    body_str = body_bytes.decode("utf-8")

    # Get signature header
    signature = request.headers.get("X-Razorpay-Signature", "")
    if not signature:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail={"error": "invalid_signature"},
        )

    # Verify webhook signature
    client = _get_razorpay_client()
    try:
        client.utility.verify_webhook_signature(body_str, signature, settings.razorpay_webhook_secret)
    except razorpay.errors.SignatureVerificationError:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail={"error": "invalid_signature"},
        )

    # Parse payload
    payload = json.loads(body_str)
    event = payload.get("event", "")

    if event == "payment.captured":
        payment_entity = payload.get("payload", {}).get("payment", {}).get("entity", {})
        order_id = payment_entity.get("order_id", "")

        # Fetch order to get receipt (contains cp_sub:pack_type)
        order = client.order.fetch(order_id)
        receipt = order.get("receipt", "")

        if ":" not in receipt:
            # Cannot link this payment — ignore gracefully
            return {"status": "ok", "message": "unlinked_order"}

        cp_sub, pack_type = receipt.split(":", 1)

        pack = CREDIT_PACKS.get(pack_type)
        if not pack:
            return {"status": "ok", "message": "unknown_pack_type"}

        credits_to_add = pack["credits"]

        # Look up CP by cognito_sub
        result = await db.execute(
            text("SELECT id FROM cps WHERE cognito_sub = :sub"),
            {"sub": cp_sub},
        )
        row = result.first()
        if not row:
            return {"status": "ok", "message": "cp_not_found"}

        cp_id = row[0]

        # Atomically add credits
        await db.execute(
            text("UPDATE cps SET credit_balance = credit_balance + :credits WHERE id = :cp_id"),
            {"credits": credits_to_add, "cp_id": str(cp_id)},
        )

        # Record transaction
        transaction = CreditTransaction(
            cp_id=cp_id,
            type="purchase",
            amount=credits_to_add,
            pack_type=pack_type,
            razorpay_order_id=order_id,
        )
        db.add(transaction)

    return {"status": "ok"}
