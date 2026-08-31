import logging
import uuid
from datetime import UTC
from typing import Any

from sqlmodel import Session, select

from app.models import Account, BankConnection, engine
from app.services.sync_service import _request_json, _utcnow_iso

logger = logging.getLogger("peng.bank_service")


def start_auth_session(redirect_url: str, bank_name: str) -> dict[str, Any]:
    """Start the PSD2 authorization flow.

    Calls Enable Banking to generate an authorization URL where the user
    can select their bank and give consent.
    """
    from datetime import datetime, timedelta

    # Enable Banking nu kræver at vi angiver specifik bank, land, state og max 180 dages valid_until
    valid_until = (datetime.now(UTC) + timedelta(days=179)).isoformat()[:19] + "Z"

    country = "DK"
    if bank_name == "Revolut (LT)":
        bank_name = "Revolut"
        country = "LT"
    elif bank_name == "Revolut (UK)":
        bank_name = "Revolut"
        country = "GB"

    access_scopes = {
        "valid_until": valid_until,
    }

    payload = {
        "access": access_scopes,
        "aspsp": {
            "name": bank_name,
            "country": country,
        },
        "state": uuid.uuid4().hex,
        "redirect_url": redirect_url,
        "psu_type": "personal",
        "maximum_consent_validity": 180,
    }

    response = _request_json("POST", "/auth", json=payload)

    if "url" not in response:
        raise RuntimeError(f"Failed to get auth URL from Enable Banking: {response}")

    return {"auth_url": response["url"]}


def complete_auth_session(code: str) -> dict[str, Any]:
    """Complete the PSD2 authorization flow.

    Exchanges the authorization code for a session, and saves the connection
    and authorized accounts to the database.
    """
    # 1. Exchange code for session
    payload = {"code": code}
    session_response = _request_json("POST", "/sessions", json=payload)
    logger.info("Received session response for code exchange")

    if "session_id" not in session_response:
        raise RuntimeError(f"Failed to create session: {session_response}")

    session_id = session_response["session_id"]
    bank_name = session_response.get("aspsp", {}).get("name", "Unknown Bank")
    accounts_data = session_response.get("accounts", [])
    if not accounts_data:
        try:
            acc_resp = _request_json("GET", f"/sessions/{session_id}/accounts")
            accounts_data = acc_resp.get("accounts", [])
        except Exception as e:
            logger.error("Failed to fetch accounts for session %s: %s", session_id, e)

    now = _utcnow_iso()

    with Session(engine) as db:
        # Save BankConnection
        conn = BankConnection(
            provider="enablebanking",
            bank_name=bank_name,
            consent_id=session_id,
            status="active",
            created_at=now,
        )
        db.add(conn)
        db.commit()
        db.refresh(conn)

        # Save Accounts
        for acc_data in accounts_data:
            account_uid = str(
                acc_data.get("uid")
                or acc_data.get("identification_hash")
                or acc_data.get("account_id", {}).get("iban")
                or f"unknown-{uuid.uuid4().hex[:8]}"
            )

            existing_acc = db.get(Account, account_uid)
            if existing_acc:
                existing_acc.bank_connection_id = conn.id
                existing_acc.iban = acc_data.get("account_id", {}).get("iban")
                existing_acc.owner_name = acc_data.get("name")
                # Do not blindly overwrite account name if user might have renamed it
                if not existing_acc.name:
                    existing_acc.name = acc_data.get("product") or f"{bank_name} Konto"
                existing_acc.currency = acc_data.get("currency", "DKK")
                existing_acc.source = "enablebanking"
            else:
                new_acc = Account(
                    uid=account_uid,
                    bank_connection_id=conn.id,
                    session_name=conn.id,  # Fallback for old code
                    iban=acc_data.get("account_id", {}).get("iban"),
                    owner_name=acc_data.get("name"),
                    name=acc_data.get("product") or f"{bank_name} Konto",
                    currency=acc_data.get("currency", "DKK"),
                    source="enablebanking",
                )
                db.add(new_acc)

        db.commit()

        # Capture ID before session closes to avoid DetachedInstanceError
        conn_id = conn.id

    # Automatisk start synkronisering af transaktioner
    try:
        from app.services.sync_service import start_sync_job

        start_sync_job()
    except Exception as e:
        logger.warning("Failed to auto-start sync job: %s", e)

    return {
        "status": "success",
        "connection_id": conn_id,
        "bank_name": bank_name,
        "accounts_added": len(accounts_data),
    }


def list_bank_connections() -> list[dict[str, Any]]:
    """List all bank connections."""
    with Session(engine) as db:
        connections = db.exec(select(BankConnection)).all()

    return [
        {
            "id": c.id,
            "provider": c.provider,
            "bank_name": c.bank_name,
            "status": c.status,
            "created_at": c.created_at,
        }
        for c in connections
    ]


def delete_bank_connection(connection_id: str) -> dict[str, Any]:
    """Delete a bank connection.

    Revokes the Enable Banking session (if active) and removes the
    connection from the database. Linked accounts are kept but unlinked
    (FK is SET NULL).
    """
    with Session(engine) as db:
        conn = db.get(BankConnection, connection_id)
        if not conn:
            raise ValueError(f"Bank connection {connection_id} not found")

        # Try to revoke the Enable Banking session
        if conn.consent_id and conn.provider == "enablebanking":
            try:
                _request_json("DELETE", f"/sessions/{conn.consent_id}")
            except Exception as e:
                # Log but don't block deletion — session may already be expired
                logger.warning("Failed to revoke Enable Banking session: %s", e)

        bank_name = conn.bank_name
        db.delete(conn)
        db.commit()

    return {"status": "deleted", "bank_name": bank_name}
