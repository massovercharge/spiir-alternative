"""Account service — manages bank accounts and balances.

This service provides an overview of all connected bank accounts,
including their real-time calculated balances based on postings.
"""
import datetime as dt
from typing import Any

from sqlmodel import Session, select

from app.models import Account, BankConnection, Posting, engine
from app.core.money import format_amount


def list_accounts_with_balances() -> list[dict[str, Any]]:
    """List all accounts with their calculated balance from postings."""
    with Session(engine) as db:
        # Fetch all accounts and their bank connections
        accounts = db.exec(
            select(Account, BankConnection)
            .join(BankConnection, isouter=True)
        ).all()

    result = []
    for account, bank_conn in accounts:
        balance_minor = account.balance_minor

        result.append({
            "uid": account.uid,
            "name": account.name,
            "iban": account.iban,
            "currency": account.currency,
            "source": account.source,
            "account_type": account.account_type,
            "savings_category_id": account.savings_category_id,
            "balance": format_amount(balance_minor),
            "balance_minor": balance_minor,
            "bank_connection": {
                "id": bank_conn.id,
                "provider": bank_conn.provider,
                "bank_name": bank_conn.bank_name,
                "status": bank_conn.status,
            } if bank_conn else None
        })

    return result

def update_account(uid: str, name: str, account_type: str | None = None, savings_category_id: str | None = None) -> dict[str, Any] | None:
    """Update an account's name and/or type."""
    with Session(engine) as db:
        account = db.get(Account, uid)
        if not account:
            return None
        account.name = name
        if account_type is not None:
            account.account_type = account_type
        if savings_category_id is not None:
            account.savings_category_id = savings_category_id
        db.commit()

        # Changing account type or savings category can change how transfers are categorized,
        # so we re-run the detection logic retroactively.
        from app.services.transfer_service import detect_internal_transfers
        detect_internal_transfers()

        return {"uid": account.uid, "name": account.name, "account_type": account.account_type, "savings_category_id": account.savings_category_id}


def get_account_balance_history(uid: str, days: int = 365) -> list[dict[str, Any]]:
    """Calculate daily end-of-day balance history for an account."""
    from sqlmodel import col
    with Session(engine) as db:
        account = db.get(Account, uid)
        if not account:
            return []

        current_balance = account.balance_minor

        # Get all postings for this account
        postings = db.exec(
            select(Posting.booking_date, Posting.amount_minor)
            .where(Posting.account_uid == uid)
            .order_by(col(Posting.booking_date).desc())
        ).all()

    # Group by date
    daily_sums = {}
    for booking_date_str, amount in postings:
        if booking_date_str:
            date_str = booking_date_str[:10]
            daily_sums[date_str] = daily_sums.get(date_str, 0) + amount

    today = dt.date.today()
    history = []

    running_balance = current_balance

    for i in range(days):
        current_date = today - dt.timedelta(days=i)
        date_str = current_date.isoformat()

        history.append({
            "date": date_str,
            "balance_minor": running_balance,
            "balance": format_amount(running_balance)
        })

        # Subtract today's net change to find yesterday's end-of-day balance
        if date_str in daily_sums:
            running_balance -= daily_sums[date_str]

    # Chronological order
    history.reverse()
    return history
