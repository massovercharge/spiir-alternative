"""Bank service — handles PSD2 consent flow via Enable Banking."""
from __future__ import annotations

import uuid
from datetime import UTC
from typing import Any

from sqlmodel import Session, select

from app.database import Account, BankConnection, engine
from app.sync_service import _request_json, _utcnow_iso


def start_auth_session(redirect_url: str) -> dict[str, Any]:
    """Start the PSD2 authorization flow.

    Calls Enable Banking to generate an authorization URL where the user
    can select their bank and give consent.
    """
    from datetime import datetime, timedelta

    # Enable Banking nu kræver at vi angiver specifik bank, land, state og max 180 dages valid_until
    valid_until = (datetime.now(UTC) + timedelta(days=179)).isoformat()[:19] + "Z"

    payload = {
        "access": {
            "valid_until": valid_until
        },
        "aspsp": {
            "name": "Sparekassen Danmark",
            "country": "DK"
        },
        "state": uuid.uuid4().hex,
        "redirect_url": redirect_url,
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

    if "session_id" not in session_response:
        raise RuntimeError(f"Failed to create session: {session_response}")

    session_id = session_response["session_id"]
    bank_name = session_response.get("aspsp", {}).get("name", "Unknown Bank")
    accounts_data = session_response.get("accounts", [])

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

    # Automatisk start synkronisering af transaktioner
    try:
        from app.sync_service import start_sync_job
        start_sync_job()
    except Exception as e:
        print(f"Failed to auto-start sync job: {e}")

    return {
        "status": "success",
        "connection_id": conn.id,
        "bank_name": conn.bank_name,
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
