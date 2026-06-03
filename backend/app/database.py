"""V2 Database Schema — Pure SQLite, bank-agnostic models."""
from __future__ import annotations

import uuid
from datetime import datetime, timezone
from typing import Optional

from sqlmodel import SQLModel, Field, Session, create_engine

from .config import get_data_dir

# ---------------------------------------------------------------------------
# Engine
# ---------------------------------------------------------------------------

sqlite_file_name = get_data_dir() / "database.sqlite"
sqlite_url = f"sqlite:///{sqlite_file_name}"
engine = create_engine(sqlite_url, echo=False)


def _utcnow() -> datetime:
    return datetime.now(timezone.utc)


def create_db_and_tables() -> None:
    SQLModel.metadata.create_all(engine)


def get_session():
    with Session(engine) as session:
        yield session


# ---------------------------------------------------------------------------
# Models
# ---------------------------------------------------------------------------

class Account(SQLModel, table=True):
    """A bank account linked via Enable Banking."""
    uid: str = Field(primary_key=True)
    session_name: str = Field(index=True)
    iban: Optional[str] = None
    name: Optional[str] = None
    currency: str = Field(default="DKK")
    source: str = Field(default="enablebanking")


class Category(SQLModel, table=True):
    """A category from the taxonomy (e.g. 'Bolig|Boliglån/husleje')."""
    id: str = Field(primary_key=True)
    main_name: str = Field(index=True)
    sub_name: str = Field(index=True)
    category_type: str = Field(default="Expense")  # "Expense" or "Income"


class Transaction(SQLModel, table=True):
    """A bank transaction, possibly categorized."""
    id: str = Field(primary_key=True)
    account_uid: str = Field(index=True)

    booking_date: str = Field(index=True)  # ISO date string for flexibility
    value_date: Optional[str] = None

    amount: float
    currency: str = Field(default="DKK")
    credit_debit_indicator: Optional[str] = None  # CRDT / DBIT

    original_description: str = Field(default="", index=True)
    remittance_information: Optional[str] = None
    creditor_name: Optional[str] = None
    debtor_name: Optional[str] = None
    merchant_category_code: Optional[str] = None
    entry_reference: Optional[str] = None

    # Categorization (mutable — no separate overrides table)
    category_id: Optional[str] = Field(default=None, index=True)
    custom_note: Optional[str] = None
    is_extraordinary: bool = Field(default=False)
    is_excluded: bool = Field(default=False)

    created_at: str = Field(default_factory=lambda: _utcnow().isoformat())
    updated_at: str = Field(default_factory=lambda: _utcnow().isoformat())


class SyncJob(SQLModel, table=True):
    """Tracks the status of an Enable Banking retrieval job."""
    id: str = Field(default_factory=lambda: uuid.uuid4().hex, primary_key=True)
    status: str = Field(default="queued")  # queued, running, succeeded, failed
    started_at: str = Field(default_factory=lambda: _utcnow().isoformat())
    completed_at: Optional[str] = None
    progress: int = Field(default=0)
    current_phase: Optional[str] = None
    error_message: Optional[str] = None
    result_json: Optional[str] = None  # JSON blob for the final result payload
