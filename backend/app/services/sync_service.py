"""Sync service — Enable Banking retrieval, normalization, and persistence."""

from __future__ import annotations

import datetime as dt
import json
import logging
import os
import threading
import uuid
from collections.abc import Callable
from pathlib import Path
from typing import Any, Optional

import jwt
import requests
from pydantic import BaseModel, field_validator
from sqlmodel import Session, select

from app.core.config import get_data_dir
from app.core.money import to_minor
from app.models import Account, BankConnection, Posting, PostingAllocation, SyncJob, engine

logger = logging.getLogger("peng.sync_service")

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


class RateLimitError(Exception):
    pass


class EnableBankingAmount(BaseModel):
    amount: Optional[str] = "0"
    currency: Optional[str] = None
    credit_debit_indicator: Optional[str] = None

    @field_validator("amount", mode="before")
    @classmethod
    def _coerce_null_amount(cls, v: object) -> str:
        """Banks may send amount: null — treat as '0'."""
        if v is None:
            return "0"
        return str(v)


class EnableBankingAccountID(BaseModel):
    iban: Optional[str] = None
    other: Optional[Any] = None


class EnableBankingParty(BaseModel):
    name: Optional[str] = None


class EnableBankingCode(BaseModel):
    code: Optional[str] = None
    description: Optional[str] = None


class EnableBankingTransaction(BaseModel):
    transaction_amount: Optional[EnableBankingAmount] = None
    balance_after_transaction: Optional[EnableBankingAmount] = None
    credit_debit_indicator: Optional[str] = None
    booking_date: Optional[str] = None
    transaction_date: Optional[str] = None
    value_date: Optional[str] = None
    booking_date_time: Optional[str] = None
    remittance_information: Optional[list[Optional[str]]] = None
    creditor: Optional[EnableBankingParty] = None
    debtor: Optional[EnableBankingParty] = None
    creditor_account: Optional[EnableBankingAccountID] = None
    debtor_account: Optional[EnableBankingAccountID] = None
    bank_transaction_code: Optional[EnableBankingCode] = None
    merchant_category_code: Optional[str] = None
    entry_reference: Optional[str] = None


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
    if response.status_code == 429:
        raise RateLimitError(f"{method} {path} blev afvist af banken (Rate Limit 429).")
    if response.status_code >= 400:
        raise RuntimeError(f"{method} {path} failed: {response.status_code} {payload}")
    return payload


# ---------------------------------------------------------------------------
# Transaction Normalization
# ---------------------------------------------------------------------------


def _signed_amount_minor(
    tx: EnableBankingTransaction, amount_field: Optional[EnableBankingAmount] = None
) -> int:
    field_data = amount_field if amount_field is not None else tx.transaction_amount
    if not field_data:
        return 0
    raw = str(field_data.amount or "0")
    minor = to_minor(raw)

    # Sometimes credit_debit_indicator is on the amount itself for balances
    cdi = tx.credit_debit_indicator
    if not cdi and hasattr(field_data, "credit_debit_indicator"):
        cdi = field_data.credit_debit_indicator

    if cdi == "DBIT":
        return -abs(minor)
    return abs(minor)


def _join_lines(value: Any) -> str:
    if isinstance(value, list):
        return "\n".join(str(item) for item in value if item is not None).strip()
    return str(value or "").strip()


def _description(transaction: EnableBankingTransaction) -> str:
    remittance = _join_lines(transaction.remittance_information)
    if remittance:
        return remittance.splitlines()[0].strip()
    return (
        (transaction.creditor.name if transaction.creditor else None)
        or (transaction.debtor.name if transaction.debtor else None)
        or transaction.entry_reference
        or ""
    )


def _normalize_and_persist(
    db: Session,
    account_data: dict[str, Any],
    session_name: str,
    transactions_data: dict[str, Any],
    household_id: str,
) -> int:
    """Normalize raw bank data and insert into the database.

    Implements rule #5: all minor units, deduplication via consistent IDs.
    Returns the number of new transactions created.
    """
    from app.models import current_household_id

    account_uid = (
        account_data.get("uid")
        or account_data.get("identification_hash")
        or (account_data.get("account_id") or {}).get("iban")
    )
    if not account_uid:
        return 0

    account_iban = (account_data.get("account_id") or {}).get("iban")
    account_data.get("name")
    account_currency = account_data.get("currency") or "DKK"

    # Upsert account
    try:
        if current_household_id.get() != household_id:
            current_household_id.set(household_id)
    except LookupError:
        current_household_id.set(household_id)

    db_account = db.get(Account, account_uid)
    if not db_account:
        db_account = Account(
            uid=account_uid,
            household_id=household_id,
            iban=account_iban,
            session_name=session_name,
            name=account_data.get("product") or f"{session_name} Konto",
            currency=account_currency,
            source="enablebanking",
        )
        db.add(db_account)
        # Flush so FKs are ready
        db.flush()

    new_count = 0
    raw_txs = transactions_data.get("transactions", [])

    # Pre-fetch active categorization rules as objects to avoid N+1 queries in evaluate_posting
    from sqlmodel import col, select

    from app.models import CategorizationRule, RecurringTransaction

    active_rules = db.exec(
        select(CategorizationRule)
        .where(CategorizationRule.is_active == True)  # noqa: E712
        .order_by(
            col(CategorizationRule.source).desc(),
            col(CategorizationRule.priority).asc(),
        )
    ).all()

    active_recurring = db.exec(
        select(RecurringTransaction).where(RecurringTransaction.status == "active")
    ).all()

    created_posting_ids: list[str] = []

    for i, raw_dict in enumerate(raw_txs):
        try:
            tx = EnableBankingTransaction.model_validate(raw_dict)
        except Exception as e:
            if "entry_reference" in raw_dict:
                logger.warning(
                    "Skipping malformed transaction %s: %s", raw_dict.get("entry_reference"), e
                )
            continue

        try:
            entry_reference = str(tx.entry_reference or "")
            tx_id = f"eb:{account_uid}:{entry_reference}"
            booking_date = tx.booking_date or tx.transaction_date or tx.value_date or ""

            existing = db.get(Posting, tx_id)
            if existing is not None:
                # Update amount/description if changed, but preserve user overrides
                existing.amount_minor = _signed_amount_minor(tx)
                existing.original_description = _description(tx)
                continue

            balance_amount = None
            if tx.balance_after_transaction:
                balance_amount = _signed_amount_minor(tx, amount_field=tx.balance_after_transaction)

            def _extract_acc_id(acc) -> str | None:
                if not acc:
                    return None
                if acc.iban:
                    return acc.iban
                if isinstance(acc.other, dict) and "identification" in acc.other:
                    return str(acc.other["identification"])
                return str(acc.other) if acc.other else None

            posting = Posting(
                id=tx_id,
                household_id=household_id,
                account_uid=account_uid,
                booking_date=booking_date,
                booking_date_time=tx.booking_date_time,
                value_date=tx.value_date,
                amount_minor=_signed_amount_minor(tx),
                currency=(tx.transaction_amount.currency if tx.transaction_amount else None)
                or account_currency,
                credit_debit_indicator=tx.credit_debit_indicator,
                original_description=_description(tx),
                remittance_information="\n".join(s for s in tx.remittance_information if s)
                if tx.remittance_information
                else "",
                creditor_name=tx.creditor.name if tx.creditor else None,
                debtor_name=tx.debtor.name if tx.debtor else None,
                creditor_account=_extract_acc_id(tx.creditor_account),
                debtor_account=_extract_acc_id(tx.debtor_account),
                merchant_category_code=tx.merchant_category_code,
                entry_reference=entry_reference,
                transaction_type=tx.bank_transaction_code.description
                if tx.bank_transaction_code
                else None,
                transaction_type_code=tx.bank_transaction_code.code
                if tx.bank_transaction_code
                else None,
                balance_after_transaction_minor=balance_amount,
            )
            db.add(posting)

            # Auto-categorize via rules engine
            from .rules_service import evaluate_posting

            matched_category = evaluate_posting(posting, rules=active_rules)
            fallback_category = "diverse|ikke-kategoriseret"

            alloc = PostingAllocation(
                posting_id=tx_id,
                category_id=matched_category or fallback_category,
                amount_minor=posting.amount_minor,
            )
            db.add(alloc)

            # Link to recurring transaction
            from .recurring_service import match_posting_to_recurring

            match_posting_to_recurring(posting, alloc, recurring_txs=active_recurring)

            new_count += 1
            created_posting_ids.append(tx_id)
            db.flush()
            if (i + 1) % 100 == 0:
                db.commit()
        except Exception as e:
            logger.error("Error persisting transaction %s: %s", tx_id, e)
            db.rollback()
            continue

    if created_posting_ids:
        try:
            from .reconciliation_service import reconcile_incoming_postings

            reconcile_incoming_postings(db, household_id, created_posting_ids)
        except Exception as e:
            logger.warning("Reconciliation step encountered error: %s", e)

    db.commit()
    return new_count


# ---------------------------------------------------------------------------
# Retrieval Orchestration
# ---------------------------------------------------------------------------


def _latest_booking_date(account_uid: str) -> dt.date | None:
    """Find the most recent booking date for a specific account (excluding future dates)."""
    import datetime as dt_mod

    from sqlmodel import col, select

    with Session(engine) as db:
        today_iso = dt_mod.date.today().isoformat()
        result = db.exec(
            select(Posting.booking_date)
            .where(Posting.account_uid == account_uid)
            .where(Posting.booking_date <= today_iso)
            .order_by(col(Posting.booking_date).desc())
            .limit(1)
        ).first()
    if result:
        try:
            return dt.date.fromisoformat(str(result)[:10])
        except ValueError:
            pass
    return None


def _fetch_params(incremental: bool, account_uid: str) -> tuple[dict[str, Any], dict[str, Any]]:
    """Build Enable Banking query params for a specific account."""
    if not incremental:
        return (
            {"strategy": "longest", "transaction_status": "BOOK"},
            {"mode": "full"},
        )
    latest = _latest_booking_date(account_uid)
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

    notify("Læser aktive bankforbindelser", 5, None)

    with Session(engine) as db:
        connections = db.exec(select(BankConnection).where(BankConnection.status == "active")).all()

        if not connections:
            raise FileNotFoundError("Ingen aktive bankforbindelser fundet. Tilknyt en bank først.")

        total_new = 0
        total_fetched = 0
        fetch_window = {}
        account_errors = {}

        for conn in connections:
            session_name = conn.bank_name or conn.id
            db_accounts = db.exec(
                select(Account).where(Account.bank_connection_id == conn.id)
            ).all()

            if not db_accounts:
                continue

            # Map accounts to dicts for existing logic
            accounts = [{"uid": acc.uid, "household_id": acc.household_id} for acc in db_accounts]

            for idx, account in enumerate(accounts, start=1):
                account_uid = account["uid"]
                try:
                    params, fetch_window = _fetch_params(incremental, account_uid)
                    notify(
                        f"Kontrollerer tilknyttede konti ({session_name})",
                        10,
                        {"account_count": len(accounts), "fetch_window": fetch_window},
                    )
                    raw_transactions: list[dict[str, Any]] = []
                    continuation_key = None
                    page = 0

                    while True:
                        page += 1
                        notify(
                            f"Henter konto {idx}/{len(accounts)} · side {page}",
                            min(75, 15 + idx * 10 + page * 3),
                            {
                                "account_index": idx,
                                "page_number": page,
                                "fetch_window": fetch_window,
                            },
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
                except Exception as e:
                    import traceback

                    logger.error(
                        "Error fetching account %s: %s", account_uid, traceback.format_exc()
                    )
                    account_errors[account_uid] = str(e)
                    continue

                # Fetch balances
                try:
                    balance_payload = _request_json("GET", f"/accounts/{account_uid}/balances")
                    balances = balance_payload.get("balances", [])

                    preferred_balance = None
                    for b_type in ["CLBD", "ITAV", "XPCD"]:
                        match = next((b for b in balances if b.get("balance_type") == b_type), None)
                        if match:
                            preferred_balance = match
                            break
                    if not preferred_balance and balances:
                        preferred_balance = balances[0]

                    if preferred_balance:
                        from app.core.money import to_minor

                        amt_str = str(
                            (preferred_balance.get("balance_amount") or {}).get("amount", "0")
                        )

                        with Session(engine) as inner_db:
                            db_acc = inner_db.get(Account, account_uid)
                            if db_acc:
                                db_acc.balance_minor = to_minor(amt_str)
                                inner_db.commit()
                except Exception as e:
                    logger.warning("Failed to fetch balances for %s: %s", account_uid, e)

                total_fetched += len(raw_transactions)
                notify(
                    f"Gemmer og normaliserer ({session_name})",
                    85,
                    {"transaction_count": len(raw_transactions)},
                )

                # Save raw JSON for audit trail
                _raw_dir().mkdir(parents=True, exist_ok=True)
                raw_path = (
                    _raw_dir()
                    / f"tx_{session_name}_{account_uid}_{dt.datetime.now(dt.UTC).strftime('%Y%m%dT%H%M%SZ')}.json"
                )
                raw_path.write_text(
                    json.dumps(
                        {
                            "fetched_at": _utcnow_iso(),
                            "account": account,
                            "transactions": raw_transactions,
                        },
                        indent=2,
                        ensure_ascii=False,
                    ),
                    encoding="utf-8",
                )

                new = _normalize_and_persist(
                    db,
                    account,
                    session_name,
                    {"transactions": raw_transactions},
                    account["household_id"],
                )
                total_new += new

    elapsed = round((dt.datetime.now(dt.UTC) - started).total_seconds(), 3)
    notify("Bank-hentning færdig", 95, {"fetched": total_fetched, "new": total_new})

    return {
        "fetched_count": total_fetched,
        "new_count": total_new,
        "elapsed_seconds": elapsed,
        "fetch_window": fetch_window if connections else {},
        "account_errors": account_errors,
    }


# ---------------------------------------------------------------------------
# Background Job Management (via SyncJob table)
# ---------------------------------------------------------------------------


def get_sync_status() -> dict[str, Any]:
    """Return the latest sync job status."""
    with Session(engine) as db:
        from sqlmodel import col, select

        job = db.exec(select(SyncJob).order_by(col(SyncJob.started_at).desc()).limit(1)).first()

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


def _run_sync_job(job_id: str, hh_id: str | None = None) -> None:
    """Background thread target for retrieval."""
    if hh_id:
        from app.models import current_household_id

        current_household_id.set(hh_id)

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

        account_errors = result.get("account_errors", [])
        if account_errors:
            msg = "Færdig (med fejl på " + ", ".join(account_errors) + ")"
        else:
            msg = "Færdig"

        # After successful retrieval, try to auto-match receipts
        _update_job("running", 95, "Matcher kvitteringer...")
        try:
            from .transaction_service import auto_link_receipts

            linked = auto_link_receipts()
            if linked > 0:
                msg += f" (Forbandt {linked} kvitteringer)"
        except Exception as e:
            logger.warning("Failed to auto-link receipts after sync: %s", e)

        _update_job(
            "succeeded" if not account_errors else "completed_with_errors",
            100,
            msg,
            completed_at=_utcnow_iso(),
            result_json=json.dumps(result, default=str),
            error_message="Nogle konti fejlede: " + ", ".join(account_errors)
            if account_errors
            else None,
        )
    except Exception as exc:
        _update_job(
            "failed",
            0,
            "Fejlede",
            completed_at=_utcnow_iso(),
            error_message=str(exc),
        )


def start_sync_job() -> dict[str, Any]:
    """Start a background retrieval job. Returns current status."""
    with _RETRIEVE_LOCK:
        thread = _RETRIEVE_STATE.get("thread")
        if isinstance(thread, threading.Thread) and thread.is_alive():
            return get_sync_status()

        from app.models import current_household_id

        try:
            hh_id = current_household_id.get()
        except LookupError:
            hh_id = None

        job_id = uuid.uuid4().hex
        with Session(engine) as db:
            db.add(SyncJob(id=job_id, household_id=hh_id))
            db.commit()

        t = threading.Thread(target=_run_sync_job, args=(job_id, hh_id), daemon=True)
        _RETRIEVE_STATE["thread"] = t
        t.start()

    return get_sync_status()
