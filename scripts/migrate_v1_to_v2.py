"""Migrate existing V1 data (old BankTransaction/BankAccount/BankOverride tables)
into the new V2 schema (Account/Transaction/Category).

Run once:
    PYTHONPATH=backend python -m scripts.migrate_v1_to_v2
"""
from __future__ import annotations

import json
import sys
from pathlib import Path

# Ensure backend is importable
sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "backend"))

from sqlmodel import Session, SQLModel, create_engine, select

from app.config import get_data_dir
from app.database import Account, Transaction, engine as v2_engine, create_db_and_tables
from app.category_service import seed_categories, make_category_id

# ---------------------------------------------------------------------------
# V1 models (read-only, pointing at old database)
# ---------------------------------------------------------------------------

from sqlmodel import Field
from typing import Optional, Any


class V1BankAccount(SQLModel, table=True):
    __tablename__ = "bankaccount"
    uid: str = Field(primary_key=True)
    session_name: str = Field(index=True)
    iban: Optional[str] = None
    name: Optional[str] = None
    payload_json: str = ""


class V1BankTransaction(SQLModel, table=True):
    __tablename__ = "banktransaction"
    id: str = Field(primary_key=True)
    account_key: str = Field(index=True)
    session_name: str = Field(index=True)
    booking_date: str = Field(index=True)
    entry_reference: str = ""
    payload_json: str = ""


class V1BankOverride(SQLModel, table=True):
    __tablename__ = "bankoverride"
    id: str = Field(primary_key=True)
    updated_at: str = ""
    patch_json: str = ""


def main():
    old_db_path = get_data_dir() / "database.sqlite"
    if not old_db_path.exists():
        print(f"No V1 database found at {old_db_path}")
        return

    old_engine = create_engine(f"sqlite:///{old_db_path}", echo=False)

    # Initialize V2
    create_db_and_tables()
    seeded = seed_categories()
    print(f"Seeded {seeded} categories into V2 database")

    # Read V1 data
    with Session(old_engine) as old_db:
        v1_accounts = old_db.exec(select(V1BankAccount)).all()
        v1_transactions = old_db.exec(select(V1BankTransaction)).all()
        v1_overrides = old_db.exec(select(V1BankOverride)).all()

    print(f"Found {len(v1_accounts)} accounts, {len(v1_transactions)} transactions, {len(v1_overrides)} overrides in V1")

    # Build override lookup
    override_map: dict[str, dict[str, Any]] = {}
    for ov in v1_overrides:
        try:
            override_map[ov.id] = json.loads(ov.patch_json)
        except (json.JSONDecodeError, TypeError):
            pass

    # Migrate accounts
    migrated_accounts = 0
    with Session(v2_engine) as db:
        for v1_acc in v1_accounts:
            if db.get(Account, v1_acc.uid):
                continue
            try:
                payload = json.loads(v1_acc.payload_json)
            except (json.JSONDecodeError, TypeError):
                payload = {}
            db.add(Account(
                uid=v1_acc.uid,
                session_name=v1_acc.session_name,
                iban=v1_acc.iban or payload.get("account_id", {}).get("iban"),
                name=v1_acc.name or payload.get("name"),
                currency=payload.get("currency", "DKK"),
            ))
            migrated_accounts += 1
        db.commit()
    print(f"Migrated {migrated_accounts} accounts")

    # Migrate transactions
    migrated_tx = 0
    skipped_tx = 0
    with Session(v2_engine) as db:
        for v1_tx in v1_transactions:
            if db.get(Transaction, v1_tx.id):
                skipped_tx += 1
                continue

            try:
                payload = json.loads(v1_tx.payload_json)
            except (json.JSONDecodeError, TypeError):
                payload = {}

            # Apply override if exists
            override = override_map.get(v1_tx.id, {})
            category_data = override.get("category") if override else None

            category_id = None
            if isinstance(category_data, dict):
                main_name = category_data.get("mainCategoryName", "Diverse")
                sub_name = category_data.get("categoryName", "Ukendt")
                category_id = make_category_id(main_name, sub_name)
            elif payload.get("mainCategoryName") and payload.get("categoryName"):
                main_name = payload["mainCategoryName"]
                sub_name = payload["categoryName"]
                if main_name != "Diverse" or sub_name != "Ikke kategoriseret":
                    category_id = make_category_id(main_name, sub_name)

            # Remap old ID format to new
            new_id = v1_tx.id.replace("enablebanking:bank:", "eb:")

            db.add(Transaction(
                id=new_id,
                account_uid=v1_tx.account_key,
                booking_date=v1_tx.booking_date or payload.get("booking_date", ""),
                value_date=payload.get("value_date"),
                amount=float(payload.get("amount", 0)),
                currency=payload.get("currency", "DKK"),
                credit_debit_indicator=payload.get("credit_debit_indicator"),
                original_description=payload.get("description", ""),
                remittance_information=payload.get("remittance_information"),
                creditor_name=payload.get("creditor_name"),
                debtor_name=payload.get("debtor_name"),
                merchant_category_code=payload.get("merchant_category_code"),
                entry_reference=v1_tx.entry_reference,
                category_id=category_id,
                custom_note=override.get("note") or payload.get("note"),
                is_extraordinary=bool(override.get("is_extraordinary", payload.get("is_extraordinary", False))),
                is_excluded=bool(payload.get("is_excluded", False)),
            ))
            migrated_tx += 1

        db.commit()

    print(f"Migrated {migrated_tx} transactions ({skipped_tx} already existed)")
    print("Migration complete!")


if __name__ == "__main__":
    main()
