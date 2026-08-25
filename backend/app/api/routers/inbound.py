"""Inbound email router — Webhooks and household inbound receipt email endpoints."""
from typing import Any

from fastapi import APIRouter, Depends, HTTPException, Request

from app.core.auth import get_auth_dependency
from app.schemas.requests import InboundEmailTestRequest
from app.services.inbound_email_service import (
    clear_inbound_emails,
    delete_inbound_email,
    get_inbound_config_for_household,
    list_inbound_emails,
    process_inbound_email,
    regenerate_inbound_token,
    retry_inbound_email,
)

router = APIRouter(tags=["inbound"])


# ---------------------------------------------------------------------------
# Public Inbound Webhooks (Unauthenticated / Token-routed)
# ---------------------------------------------------------------------------

@router.post("/api/inbound/email")
async def inbound_email_webhook(request: Request) -> dict[str, Any]:
    """Public webhook endpoint for receiving incoming forwarded emails (raw MIME or JSON)."""
    content_type = request.headers.get("content-type", "").lower()

    if "application/json" in content_type:
        try:
            payload = await request.json()
        except Exception as exc:
            raise HTTPException(status_code=400, detail="Invalid JSON body") from exc
        return process_inbound_email(payload, source_type="webhook")

    # Handle raw RFC822 / raw bytes / text
    body_bytes = await request.body()
    if not body_bytes:
        raise HTTPException(status_code=400, detail="Empty request body")

    return process_inbound_email(body_bytes, source_type="webhook")


@router.post("/api/inbound/email/{token}")
async def inbound_email_webhook_with_token(token: str, request: Request) -> dict[str, Any]:
    """Public webhook endpoint with household token explicitly in the URL path."""
    from sqlmodel import Session, select

    import app.models as models
    from app.models import Household

    with Session(models.engine) as db:
        hh = db.exec(select(Household).where(Household.inbound_email_token == token.lower())).first()
        if not hh:
            raise HTTPException(status_code=404, detail="Invalid household token")
        household_id = hh.id

    content_type = request.headers.get("content-type", "").lower()
    if "application/json" in content_type:
        try:
            payload = await request.json()
        except Exception as exc:
            raise HTTPException(status_code=400, detail="Invalid JSON body") from exc
        return process_inbound_email(payload, household_id=household_id, source_type="webhook")

    body_bytes = await request.body()
    if not body_bytes:
        raise HTTPException(status_code=400, detail="Empty request body")

    return process_inbound_email(body_bytes, household_id=household_id, source_type="webhook")


# ---------------------------------------------------------------------------
# Authenticated Household Inbound Email Endpoints
# ---------------------------------------------------------------------------

@router.get("/api/households/{household_id}/inbound-config")
def household_inbound_config(
    household_id: str,
    auth: dict[str, Any] = Depends(get_auth_dependency()),
) -> dict[str, Any]:
    """Get the household's inbound email address and configuration."""
    try:
        return get_inbound_config_for_household(household_id)
    except ValueError as exc:
        raise HTTPException(status_code=404, detail=str(exc)) from exc


@router.post("/api/households/{household_id}/inbound-config/regenerate-token")
def household_inbound_regenerate_token(
    household_id: str,
    auth: dict[str, Any] = Depends(get_auth_dependency()),
) -> dict[str, Any]:
    """Regenerate the household's inbound email token (requires owner role)."""
    try:
        return regenerate_inbound_token(household_id, auth["user_id"])
    except ValueError as exc:
        raise HTTPException(status_code=400, detail=str(exc)) from exc


@router.get("/api/households/{household_id}/inbound-emails")
def household_inbound_emails_list(
    household_id: str,
    auth: dict[str, Any] = Depends(get_auth_dependency()),
) -> list[dict[str, Any]]:
    """List historical received Storebox emails for this household."""
    return list_inbound_emails(household_id)


@router.post("/api/households/{household_id}/inbound-emails/test")
def household_inbound_email_simulate(
    household_id: str,
    payload: InboundEmailTestRequest,
    auth: dict[str, Any] = Depends(get_auth_dependency()),
) -> dict[str, Any]:
    """Simulate receiving an email or test extracting and importing from email text / link."""
    content: dict[str, Any] = {
        "sender": payload.sender or auth.get("email", "test@example.com"),
        "subject": payload.subject or "Test: Kvitteringsdata fra Storebox",
        "text_body": payload.raw_content or "",
        "download_url": payload.url,
    }
    return process_inbound_email(content, household_id=household_id, source_type="simulation")


@router.post("/api/households/{household_id}/inbound-emails/{email_id}/retry")
def household_inbound_email_retry(
    household_id: str,
    email_id: str,
    auth: dict[str, Any] = Depends(get_auth_dependency()),
) -> dict[str, Any]:
    """Retry downloading and parsing a previously failed email log entry."""
    try:
        return retry_inbound_email(email_id, household_id)
    except ValueError as exc:
        raise HTTPException(status_code=400, detail=str(exc)) from exc


@router.delete("/api/households/{household_id}/inbound-emails/{email_id}")
def household_inbound_email_delete(
    household_id: str,
    email_id: str,
    auth: dict[str, Any] = Depends(get_auth_dependency()),
) -> dict[str, Any]:
    """Delete an inbound email history record."""
    try:
        return delete_inbound_email(email_id, household_id)
    except ValueError as exc:
        raise HTTPException(status_code=404, detail=str(exc)) from exc


@router.delete("/api/households/{household_id}/inbound-emails")
def household_inbound_emails_clear(
    household_id: str,
    auth: dict[str, Any] = Depends(get_auth_dependency()),
) -> dict[str, Any]:
    """Clear all inbound email history for a household."""
    try:
        return clear_inbound_emails(household_id)
    except ValueError as exc:
        raise HTTPException(status_code=400, detail=str(exc)) from exc

