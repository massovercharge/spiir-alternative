"""Inbound email service for Storebox/Nexi receipt exports.

Extracts download links from forwarded emails, downloads ZIP archives,
unpacks and parses receipts idempotently, and logs inbound email history.
"""
from __future__ import annotations

import email
import email.policy
import html
import re
import uuid
from datetime import UTC, datetime
from typing import Any

from sqlmodel import Session, select

from app.core.config import (
    get_household_inbound_email,
    get_imap_config,
    get_inbound_email_domain,
    get_inbound_email_prefix,
)
from app.models import (
    Household,
    HouseholdMember,
    InboundEmail,
    current_household_id,
    engine,
)
from app.services.storebox_service import process_storebox_file, process_storebox_link
from app.services.transaction_service import auto_link_receipts


def _utcnow_iso() -> str:
    return datetime.now(UTC).isoformat().replace("+00:00", "Z")


# Regex to match URLs in plain text or HTML
URL_PATTERN = re.compile(r"https?://[^\s<>\"']+", re.IGNORECASE)

# Regex to match HTML <a> tags with href
A_TAG_PATTERN = re.compile(
    r"<a\s+(?:[^>]*?\s+)?href=([\"'])(.*?)\1[^>]*>(.*?)</a>",
    re.IGNORECASE | re.DOTALL,
)

# Token extraction pattern (e.g. receipts+abc123def456@... or abc123def456@...)
TOKEN_PATTERN = re.compile(r"(?:[a-zA-Z0-9._%+-]+\+)?([a-f0-9]{8,32})@", re.IGNORECASE)


def extract_storebox_link(text_body: str = "", html_body: str = "") -> str | None:
    """Extract the download link for receipt data from email HTML or plain text."""
    candidates: list[tuple[int, str]] = []

    # 1. Inspect HTML anchor tags
    if html_body:
        for match in A_TAG_PATTERN.finditer(html_body):
            raw_href = match.group(2).strip()
            anchor_text = re.sub(r"<[^>]+>", "", match.group(3)).strip().lower()
            clean_url = html.unescape(raw_href).strip()

            if not clean_url.startswith("http"):
                continue

            score = 0
            low_url = clean_url.lower()

            if any(k in anchor_text for k in ("download", "hent", "data", "kvittering", "eksport", "export")):
                score += 50
            if "storebox" in low_url or "nexi" in low_url:
                score += 40
            if "s3.amazonaws.com" in low_url or "s3." in low_url or "s3-" in low_url:
                score += 35
            if any(k in low_url for k in ("export", "receipts", "download", "archive")):
                score += 25

            candidates.append((score, clean_url))

    # 2. Inspect plain text URLs
    combined_text = f"{text_body}\n{re.sub(r'<[^>]+>', ' ', html_body)}"
    for match in URL_PATTERN.finditer(combined_text):
        raw_url = match.group(0).strip()
        # Clean trailing punctuation
        raw_url = re.sub(r"[.,;:!?)\]'\"]+$", "", raw_url)
        clean_url = html.unescape(raw_url).strip()

        if not clean_url.startswith("http"):
            continue

        score = 0
        low_url = clean_url.lower()

        if "storebox" in low_url or "nexi" in low_url:
            score += 40
        if "s3.amazonaws.com" in low_url or "s3." in low_url or "s3-" in low_url:
            score += 35
        if any(k in low_url for k in ("export", "receipts", "download", "archive")):
            score += 20

        candidates.append((score, clean_url))

    if not candidates:
        return None

    # Deduplicate candidates while preserving best score
    best_by_url: dict[str, int] = {}
    for score, url in candidates:
        if url not in best_by_url or score > best_by_url[url]:
            best_by_url[url] = score

    sorted_candidates = sorted(best_by_url.items(), key=lambda x: x[1], reverse=True)
    return sorted_candidates[0][0]


def resolve_household_by_token_or_recipient(
    recipients: list[str],
    subject: str = "",
    body_text: str = "",
) -> Household | None:
    """Resolve which household an inbound email belongs to."""
    with Session(engine) as db:
        # Check recipient addresses for tokens
        for recipient in recipients:
            match = TOKEN_PATTERN.search(recipient)
            if match:
                token = match.group(1).lower()
                hh = db.exec(
                    select(Household).where(Household.inbound_email_token == token)
                ).first()
                if hh:
                    return hh

        # Search subject and body for tokens if forwarded
        combined_text = f"{subject}\n{body_text}"
        for match in TOKEN_PATTERN.finditer(combined_text):
            token = match.group(1).lower()
            hh = db.exec(
                select(Household).where(Household.inbound_email_token == token)
            ).first()
            if hh:
                return hh

        # Fallback: if only 1 active household exists, match it
        all_households = db.exec(
            select(Household).where(Household.deleted_at == None)  # noqa: E711
        ).all()
        if len(all_households) == 1:
            return all_households[0]

    return None


def _parse_mime_email(raw_bytes: bytes) -> dict[str, Any]:
    """Parse raw RFC822 MIME email into a structured dictionary."""
    msg = email.message_from_bytes(raw_bytes, policy=email.policy.default)

    sender = str(msg.get("From", ""))
    recipients: list[str] = []
    for header_name in ("To", "Cc", "X-Forwarded-To", "Delivered-To", "Envelope-To"):
        val = msg.get(header_name)
        if val:
            recipients.append(str(val))

    subject = str(msg.get("Subject", ""))
    text_body = ""
    html_body = ""
    attachments: list[tuple[str, bytes]] = []

    if msg.is_multipart():
        for part in msg.walk():
            content_type = part.get_content_type()
            content_disposition = str(part.get("Content-Disposition", ""))
            filename = part.get_filename()

            if filename and ("attachment" in content_disposition or filename.endswith((".zip", ".json"))):
                payload = part.get_payload(decode=True)
                if isinstance(payload, bytes):
                    attachments.append((filename, payload))
            elif content_type == "text/plain" and not text_body:
                payload = part.get_payload(decode=True)
                if isinstance(payload, bytes):
                    text_body = payload.decode(part.get_content_charset() or "utf-8", errors="replace")
            elif content_type == "text/html" and not html_body:
                payload = part.get_payload(decode=True)
                if isinstance(payload, bytes):
                    html_body = payload.decode(part.get_content_charset() or "utf-8", errors="replace")
    else:
        payload = msg.get_payload(decode=True)
        if isinstance(payload, bytes):
            decoded = payload.decode(msg.get_content_charset() or "utf-8", errors="replace")
            if msg.get_content_type() == "text/html":
                html_body = decoded
            else:
                text_body = decoded

    return {
        "sender": sender,
        "recipients": recipients,
        "subject": subject,
        "text_body": text_body,
        "html_body": html_body,
        "attachments": attachments,
    }


def process_inbound_email(
    raw_content: str | bytes | dict[str, Any],
    household_id: str | None = None,
    source_type: str = "webhook",
) -> dict[str, Any]:
    """Process an incoming email, extract link/file, parse Storebox receipts, and log history."""
    sender = ""
    recipients: list[str] = []
    subject = ""
    text_body = ""
    html_body = ""
    attachments: list[tuple[str, bytes]] = []
    provided_url: str | None = None

    if isinstance(raw_content, bytes):
        parsed = _parse_mime_email(raw_content)
        sender = parsed["sender"]
        recipients = parsed["recipients"]
        subject = parsed["subject"]
        text_body = parsed["text_body"]
        html_body = parsed["html_body"]
        attachments = parsed["attachments"]
    elif isinstance(raw_content, str):
        # Could be raw MIME string or raw text body/link
        if raw_content.strip().startswith(("From:", "Received:", "Return-Path:", "MIME-Version:")):
            parsed = _parse_mime_email(raw_content.encode("utf-8"))
            sender = parsed["sender"]
            recipients = parsed["recipients"]
            subject = parsed["subject"]
            text_body = parsed["text_body"]
            html_body = parsed["html_body"]
            attachments = parsed["attachments"]
        else:
            text_body = raw_content
            if raw_content.strip().startswith("http"):
                provided_url = raw_content.strip()
    elif isinstance(raw_content, dict):
        sender = str(raw_content.get("sender") or raw_content.get("from") or "")
        recipient_val = raw_content.get("recipient") or raw_content.get("to")
        if isinstance(recipient_val, list):
            recipients = [str(r) for r in recipient_val]
        elif recipient_val:
            recipients = [str(recipient_val)]
        subject = str(raw_content.get("subject") or "")
        text_body = str(raw_content.get("text_body") or raw_content.get("text") or "")
        html_body = str(raw_content.get("html_body") or raw_content.get("html") or "")
        provided_url = raw_content.get("url") or raw_content.get("download_url")

    # Resolve target household
    target_household: Household | None = None
    with Session(engine) as db:
        if household_id:
            target_household = db.get(Household, household_id)
        if not target_household:
            target_household = resolve_household_by_token_or_recipient(recipients, subject, text_body)

        if not target_household:
            raise ValueError(
                "Could not identify the target household. Please make sure the email is forwarded to the correct household address."
            )
        target_household_id = target_household.id

    # Process receipt data and update log
    current_token = current_household_id.set(target_household_id)
    try:
        with Session(engine) as db:
            # Create log record
            email_log = InboundEmail(
                household_id=target_household_id,
                received_at=_utcnow_iso(),
                sender=sender or "Ukendt afsender",
                recipient=", ".join(recipients) if recipients else None,
                subject=subject or "(Intet emne)",
                status="pending",
                source_type=source_type,
            )
            db.add(email_log)
            db.commit()
            db.refresh(email_log)
            log_id = email_log.id

        result: dict[str, Any] = {}
        download_url: str | None = None

        if attachments:
            # Direct attachment (.zip or .json)
            filename, content = attachments[0]
            result = process_storebox_file(content, filename)
        else:
            # Extract download link
            download_url = provided_url or extract_storebox_link(text_body, html_body)
            if not download_url:
                with Session(engine) as db:
                    log_item = db.get(InboundEmail, log_id)
                    if log_item:
                        log_item.status = "no_link"
                        log_item.error_message = "Ingen Storebox download-link eller kvitteringsfil fundet i e-mailen"
                        db.add(log_item)
                        db.commit()
                return {
                    "success": False,
                    "status": "no_link",
                    "error": "Ingen Storebox download-link eller kvitteringsfil fundet i e-mailen",
                    "log_id": log_id,
                }

            result = process_storebox_link(download_url)

        # Auto-link receipts to bank transactions
        auto_linked = auto_link_receipts()
        result["auto_linked"] = auto_linked

        # Update log to success
        with Session(engine) as db:
            log_item = db.get(InboundEmail, log_id)
            if log_item:
                log_item.status = "success"
                log_item.download_url = download_url
                log_item.raw_receipt_count = int(result.get("raw_receipt_count") or 0)
                log_item.deduplicated_receipt_count = int(result.get("deduplicated_receipt_count") or 0)
                log_item.auto_linked_count = auto_linked
                log_item.error_message = None
                db.add(log_item)
                db.commit()

        return {
            "success": True,
            "status": "success",
            "log_id": log_id,
            "download_url": download_url,
            "raw_receipt_count": result.get("raw_receipt_count", 0),
            "deduplicated_receipt_count": result.get("deduplicated_receipt_count", 0),
            "auto_linked": auto_linked,
            "merchant_count": result.get("merchant_count", 0),
        }

    except Exception as exc:
        err_msg = str(exc)
        with Session(engine) as db:
            log_item = db.get(InboundEmail, log_id)
            if log_item:
                log_item.status = "failed"
                log_item.download_url = download_url
                log_item.error_message = err_msg
                db.add(log_item)
                db.commit()

        return {
            "success": False,
            "status": "failed",
            "log_id": log_id,
            "download_url": download_url,
            "error": err_msg,
        }
    finally:
        current_household_id.reset(current_token)


def list_inbound_emails(household_id: str, limit: int = 50) -> list[dict[str, Any]]:
    """List historical inbound Storebox emails for a household."""
    token = current_household_id.set(household_id)
    try:
        with Session(engine) as db:
            logs = db.exec(
                select(InboundEmail)
                .where(InboundEmail.household_id == household_id)
                .order_by(InboundEmail.received_at.desc())  # type: ignore
                .limit(limit)
            ).all()

            return [
                {
                    "id": log.id,
                    "household_id": log.household_id,
                    "received_at": log.received_at,
                    "sender": log.sender,
                    "recipient": log.recipient,
                    "subject": log.subject,
                    "status": log.status,
                    "download_url": log.download_url,
                    "error_message": log.error_message,
                    "raw_receipt_count": log.raw_receipt_count,
                    "deduplicated_receipt_count": log.deduplicated_receipt_count,
                    "auto_linked_count": log.auto_linked_count,
                    "source_type": log.source_type,
                }
                for log in logs
            ]
    finally:
        current_household_id.reset(token)


def retry_inbound_email(email_id: str, household_id: str) -> dict[str, Any]:
    """Retry downloading and parsing receipts for a previously logged email."""
    with Session(engine) as db:
        log_item = db.get(InboundEmail, email_id)
        if not log_item or log_item.household_id != household_id:
            raise ValueError("Inbound email log record not found")

        if not log_item.download_url:
            raise ValueError("No download URL recorded for this email to retry")

        url = log_item.download_url

    current_token = current_household_id.set(household_id)
    try:
        result = process_storebox_link(url)
        auto_linked = auto_link_receipts()

        with Session(engine) as db:
            log_item = db.get(InboundEmail, email_id)
            if log_item:
                log_item.status = "success"
                log_item.raw_receipt_count = int(result.get("raw_receipt_count") or 0)
                log_item.deduplicated_receipt_count = int(result.get("deduplicated_receipt_count") or 0)
                log_item.auto_linked_count = auto_linked
                log_item.error_message = None
                db.add(log_item)
                db.commit()

        return {
            "success": True,
            "status": "success",
            "raw_receipt_count": result.get("raw_receipt_count", 0),
            "deduplicated_receipt_count": result.get("deduplicated_receipt_count", 0),
            "auto_linked": auto_linked,
        }
    except Exception as exc:
        err_msg = str(exc)
        with Session(engine) as db:
            log_item = db.get(InboundEmail, email_id)
            if log_item:
                log_item.status = "failed"
                log_item.error_message = err_msg
                db.add(log_item)
                db.commit()

        return {
            "success": False,
            "status": "failed",
            "error": err_msg,
        }
    finally:
        current_household_id.reset(current_token)


def get_inbound_config_for_household(household_id: str) -> dict[str, Any]:
    """Return inbound email configuration, unique address, and IMAP status for a household."""
    with Session(engine) as db:
        hh = db.get(Household, household_id)
        if not hh:
            raise ValueError("Household not found")

        token = hh.inbound_email_token or "default"
        imap_conf = get_imap_config()

        return {
            "household_id": hh.id,
            "household_name": hh.name,
            "inbound_token": token,
            "email_address": get_household_inbound_email(token),
            "domain": get_inbound_email_domain(),
            "prefix": get_inbound_email_prefix(),
            "imap_enabled": imap_conf["enabled"],
        }


def regenerate_inbound_token(household_id: str, requesting_user_id: str) -> dict[str, Any]:
    """Regenerate a new inbound email token for the household (requires owner role)."""
    with Session(engine) as db:
        membership = db.exec(
            select(HouseholdMember).where(
                HouseholdMember.household_id == household_id,
                HouseholdMember.user_id == requesting_user_id,
            )
        ).first()

        if not membership or membership.role != "owner":
            raise ValueError("Only household owners can regenerate the inbound email token")

        hh = db.get(Household, household_id)
        if not hh:
            raise ValueError("Household not found")

        new_token = uuid.uuid4().hex[:12]
        hh.inbound_email_token = new_token
        db.add(hh)
        db.commit()
        db.refresh(hh)

        return get_inbound_config_for_household(household_id)
