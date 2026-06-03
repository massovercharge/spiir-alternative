"""Sync service — Enable Banking retrieval, normalization, and persistence."""
from __future__ import annotations

import datetime as dt
import json
import os
import threading
import uuid
from pathlib import Path
from typing import Any, Callable

import jwt
import requests

from sqlmodel import Session

from .config import get_data_dir
from .database import Account, Transaction, SyncJob, engine

# ---------------------------------------------------------------------------
# Enable Banking Configuration
# ---------------------------------------------------------------------------

APP_ID = os.getenv("ENABLEBANKING_APP_ID", "").strip()
API_BASE = "https://api.enablebanking.com"
INCREMENTAL_LOOKBACK_DAYS = 7

_RETRIEVE_STATE: dict[str, Any] = {"thread": None}
_RETRIEVE_LOCK = threading.Lock()


def _utcnow_iso() -> str:
    return dt.datetime.now(dt.UTC).isoformat().replace("+00:00", "Z")


# ---------------------------------------------------------------------------
# Enable Banking Auth
# ---------------------------------------------------------------------------

def _enablebanking_dir() -> Path:
    return get_data_dir() / "transactions" / "enablebanking"


def _raw_dir() -> Path:
    return get_data_dir() / "transactions" / "raw" / "enablebanking"


def _key_path() -> Path:
    app_id = _get_app_id()
    configured_path = os.getenv("ENABLEBANKING_PRIVATE_KEY_PATH")
    if configured_path:
        return Path(configured_path).expanduser().resolve()
    return get_data_dir() / "local_secrets" / "enablebanking" / f"{app_id}.pem"


def _get_app_id() -> str:
    if not APP_ID:
        raise RuntimeError("Set ENABLEBANKING_APP_ID before calling Enable Banking")
    return APP_ID


def _auth_headers() -> dict[str, str]:
    key_path = _key_path()
    if not key_path.exists():
        raise FileNotFoundError(f"Missing Enable Banking private key: {key_path}")
    issued_at = int(dt.datetime.now(dt.UTC).timestamp())
    token = jwt.encode(
        {
            "iss": "enablebanking.com",
            "aud": "api.enablebanking.com",
            "iat": issued_at,
            "exp": issued_at + 3600,
        },
        key_path.read_bytes(),
        algorithm="RS256",
        headers={"kid": _get_app_id()},
    )
    return {"Authorization": f"Bearer {token}", "Accept": "application/json"}


def _request_json(method: str, path: str, **kwargs: Any) -> Any:
    response = requests.request(
        method, f"{API_BASE}{path}", headers=_auth_headers(), timeout=60, **kwargs
    )
    try:
        payload = response.json()
    except ValueError:
        payload = {"text": response.text}
    if response.status_code >= 400:
        raise RuntimeError(f"{method} {path} failed: {response.status_code} {payload}")
    return payload


# ---------------------------------------------------------------------------
# Transaction Normalization
# ---------------------------------------------------------------------------

def _signed_amount(transaction: dict[str, Any]) -> float:
    amount = float(transaction.get("transaction_amount", {}).get("amount") or 0)
    if transaction.get("credit_debit_indicator") == "DBIT":
        return -amount
    return amount


def _join_lines(value: Any) -> str:
    if isinstance(value, list):
        return "\n".join(str(item) for item in value if item is not None).strip()
    return str(value or "").strip()


def _party_name(value: Any) -> str | None:
    if not isinstance(value, dict):
        return None
    name = str(value.get("name") or "").strip()
    return name or None


def _description(transaction: dict[str, Any]) -> str:
    remittance = _join_lines(transaction.get("remittance_information"))
    if remittance:
        return remittance.splitlines()[0].strip()
    return (
        _party_name(transaction.get("creditor"))
        or _party_name(transaction.get("debtor"))
        or transaction.get("bank_transaction_code", {}).get("description")
        or transaction.get("entry_reference")
        or ""
    )


def _normalize_and_persist(
    account_data: dict[str, Any],
    raw_transactions: list[dict[str, Any]],
    session_name: str,
) -> int:
    """Normalize raw Enable Banking transactions and upsert into SQLite.
    Returns the number of new transactions inserted.
    """
    account_uid = str(
        account_data.get("uid")
        or account_data.get("identification_hash")
        or account_data.get("account_id", {}).get("iban")
        or "unknown"
    )
    account_iban = account_data.get("account_id", {}).get("iban")
    account_name = account_data.get("name")
    account_currency = account_data.get("currency") or "DKK"

    new_count = 0
    with Session(engine) as db:
        # Upsert account
        db_account = db.get(Account, account_uid)
        if db_account is None:
            db_account = Account(
                uid=account_uid,
                session_name=session_name,
                iban=account_iban,
                name=account_name,
                currency=account_currency,
            )
            db.add(db_account)
        else:
            db_account.iban = account_iban
            db_account.name = account_name

        # Upsert transactions
        for raw_tx in raw_transactions:
            entry_reference = str(raw_tx.get("entry_reference") or "")
            tx_id = f"eb:{account_uid}:{entry_reference}"
            booking_date = (
                raw_tx.get("booking_date")
                or raw_tx.get("transaction_date")
                or raw_tx.get("value_date")
                or ""
            )

            existing = db.get(Transaction, tx_id)
            if existing is not None:
                # Update amount/description if changed, but preserve user overrides
                existing.amount = _signed_amount(raw_tx)
                existing.original_description = _description(raw_tx)
                continue

            db.add(Transaction(
                id=tx_id,
                account_uid=account_uid,
                booking_date=booking_date,
                value_date=raw_tx.get("value_date"),
                amount=_signed_amount(raw_tx),
                currency=raw_tx.get("transaction_amount", {}).get("currency") or account_currency,
                credit_debit_indicator=raw_tx.get("credit_debit_indicator"),
                original_description=_description(raw_tx),
                remittance_information=_join_lines(raw_tx.get("remittance_information")),
                creditor_name=_party_name(raw_tx.get("creditor")),
                debtor_name=_party_name(raw_tx.get("debtor")),
                merchant_category_code=raw_tx.get("merchant_category_code"),
                entry_reference=entry_reference,
            ))
            new_count += 1

        db.commit()

    return new_count


# ---------------------------------------------------------------------------
# Retrieval Orchestration
# ---------------------------------------------------------------------------

def _latest_booking_date() -> dt.date | None:
    """Find the most recent booking date across all transactions."""
    from sqlmodel import select, col
    with Session(engine) as db:
        result = db.exec(
            select(Transaction.booking_date)
            .order_by(col(Transaction.booking_date).desc())
            .limit(1)
        ).first()
    if result:
        try:
            return dt.date.fromisoformat(str(result)[:10])
        except ValueError:
            pass
    return None


def _fetch_params(incremental: bool) -> tuple[dict[str, Any], dict[str, Any]]:
    """Build Enable Banking query params."""
    if not incremental:
        return (
            {"strategy": "longest", "transaction_status": "BOOK"},
            {"mode": "full"},
        )
    latest = _latest_booking_date()
    if latest is None:
        return (
            {"strategy": "longest", "transaction_status": "BOOK"},
            {"mode": "full"},
        )
    date_from = latest - dt.timedelta(days=INCREMENTAL_LOOKBACK_DAYS)
    date_to = dt.datetime.now(dt.UTC).date()
    return (
        {
            "transaction_status": "BOOK",
            "date_from": date_from.isoformat(),
            "date_to": date_to.isoformat(),
        },
        {
            "mode": "incremental",
            "lookback_days": INCREMENTAL_LOOKBACK_DAYS,
            "date_from": date_from.isoformat(),
            "date_to": date_to.isoformat(),
        },
    )


def retrieve_transactions(
    *,
    incremental: bool = True,
    progress: Callable[[str, int, dict[str, Any] | None], None] | None = None,
) -> dict[str, Any]:
    """Fetch transactions from Enable Banking and persist to SQLite."""
    started = dt.datetime.now(dt.UTC)

    def notify(label: str, pct: int, extra: dict[str, Any] | None = None) -> None:
        if progress:
            progress(label, pct, extra)

    notify("Læser Enable Banking-sessioner", 5, None)
    session_files = list(_enablebanking_dir().glob("session_*.json"))
    if not session_files:
        raise FileNotFoundError(
            "Missing Enable Banking session. Re-authorize account access first."
        )

    total_new = 0
    total_fetched = 0

    for session_file in session_files:
        session_data = json.loads(session_file.read_text(encoding="utf-8"))
        session_name = session_file.stem
        accounts = session_data.get("accounts") or []
        if not accounts:
            continue

        params, fetch_window = _fetch_params(incremental)
        notify(
            f"Kontrollerer tilknyttede konti ({session_name})",
            10,
            {"account_count": len(accounts), "fetch_window": fetch_window},
        )

        for idx, account in enumerate(accounts, start=1):
            account_uid = account["uid"]
            raw_transactions: list[dict[str, Any]] = []
            continuation_key = None
            page = 0

            while True:
                page += 1
                notify(
                    f"Henter konto {idx}/{len(accounts)} · side {page}",
                    min(75, 15 + idx * 10 + page * 3),
                    {"account_index": idx, "page_number": page, "fetch_window": fetch_window},
                )
                page_params = dict(params)
                if continuation_key:
                    page_params["continuation_key"] = continuation_key
                payload = _request_json(
                    "GET", f"/accounts/{account_uid}/transactions", params=page_params
                )
                raw_transactions.extend(payload.get("transactions", []))
                continuation_key = payload.get("continuation_key")
                if not continuation_key:
                    break

            total_fetched += len(raw_transactions)
            notify(
                f"Gemmer og normaliserer ({session_name})",
                85,
                {"transaction_count": len(raw_transactions)},
            )

            # Save raw JSON for audit trail
            _raw_dir().mkdir(parents=True, exist_ok=True)
            raw_path = _raw_dir() / f"tx_{session_name}_{account_uid}_{dt.datetime.now(dt.UTC).strftime('%Y%m%dT%H%M%SZ')}.json"
            raw_path.write_text(json.dumps({
                "fetched_at": _utcnow_iso(),
                "account": account,
                "transactions": raw_transactions,
            }, indent=2, ensure_ascii=False), encoding="utf-8")

            new = _normalize_and_persist(account, raw_transactions, session_name)
            total_new += new

    elapsed = round((dt.datetime.now(dt.UTC) - started).total_seconds(), 3)
    notify("Bank-hentning færdig", 95, {"fetched": total_fetched, "new": total_new})

    return {
        "fetched_count": total_fetched,
        "new_count": total_new,
        "elapsed_seconds": elapsed,
        "fetch_window": fetch_window if session_files else {},
    }


# ---------------------------------------------------------------------------
# Background Job Management (via SyncJob table)
# ---------------------------------------------------------------------------

def get_sync_status() -> dict[str, Any]:
    """Return the latest sync job status."""
    with Session(engine) as db:
        from sqlmodel import select, col
        job = db.exec(
            select(SyncJob).order_by(col(SyncJob.started_at).desc()).limit(1)
        ).first()

    if job is None:
        return {
            "job_id": None,
            "status": "idle",
            "progress": 0,
            "current_phase": None,
            "error": None,
        }

    # Detect zombie jobs (thread died but status still says running)
    thread = _RETRIEVE_STATE.get("thread")
    if job.status in {"queued", "running"} and not isinstance(thread, threading.Thread):
        with Session(engine) as db:
            stale = db.get(SyncJob, job.id)
            if stale:
                stale.status = "failed"
                stale.completed_at = _utcnow_iso()
                stale.error_message = "Hentning blev afbrudt. Start igen."
                db.commit()
        job.status = "failed"
        job.error_message = "Hentning blev afbrudt. Start igen."

    return {
        "job_id": job.id,
        "status": job.status,
        "started_at": job.started_at,
        "completed_at": job.completed_at,
        "progress": job.progress,
        "current_phase": job.current_phase,
        "error": job.error_message,
        "result": json.loads(job.result_json) if job.result_json else None,
    }


def _run_sync_job(job_id: str) -> None:
    """Background thread target for retrieval."""
    def _update_job(status: str, progress: int, phase: str | None = None, **kwargs: Any) -> None:
        with Session(engine) as db:
            job = db.get(SyncJob, job_id)
            if job:
                job.status = status
                job.progress = progress
                job.current_phase = phase
                for key, value in kwargs.items():
                    if hasattr(job, key):
                        setattr(job, key, value)
                db.commit()

    def progress(label: str, pct: int, extra: dict[str, Any] | None) -> None:
        _update_job("running", pct, label)

    try:
        _update_job("running", 1, "Starter hentning")
        result = retrieve_transactions(incremental=True, progress=progress)
        _update_job(
            "succeeded", 100, "Færdig",
            completed_at=_utcnow_iso(),
            result_json=json.dumps(result, default=str),
        )
    except Exception as exc:
        _update_job(
            "failed", 0, "Fejlede",
            completed_at=_utcnow_iso(),
            error_message=str(exc),
        )


def start_sync_job() -> dict[str, Any]:
    """Start a background retrieval job. Returns current status."""
    with _RETRIEVE_LOCK:
        thread = _RETRIEVE_STATE.get("thread")
        if isinstance(thread, threading.Thread) and thread.is_alive():
            return get_sync_status()

        job_id = uuid.uuid4().hex
        with Session(engine) as db:
            db.add(SyncJob(id=job_id))
            db.commit()

        t = threading.Thread(target=_run_sync_job, args=(job_id,), daemon=True)
        _RETRIEVE_STATE["thread"] = t
        t.start()

    return get_sync_status()
