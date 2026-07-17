import re
from pathlib import Path

content = Path('backend/app/sync_service.py').read_text()

# 1. Add Pydantic imports
imports = """
import jwt
import requests
from sqlmodel import Session, select
from pydantic import BaseModel, Field
from typing import Optional, List
"""
content = re.sub(r'import jwt\nimport requests\nfrom sqlmodel import Session, select', imports.strip(), content)

# 2. Add RateLimitError and models
models = """
class RateLimitError(Exception):
    pass

class EnableBankingAmount(BaseModel):
    amount: str = "0"
    currency: Optional[str] = None
    credit_debit_indicator: Optional[str] = None

class EnableBankingAccountID(BaseModel):
    iban: Optional[str] = None
    other: Optional[str] = None

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
    remittance_information: Optional[List[str]] = None
    creditor: Optional[EnableBankingParty] = None
    debtor: Optional[EnableBankingParty] = None
    creditor_account: Optional[EnableBankingAccountID] = None
    debtor_account: Optional[EnableBankingAccountID] = None
    bank_transaction_code: Optional[EnableBankingCode] = None
    merchant_category_code: Optional[str] = None
    entry_reference: Optional[str] = None

# ---------------------------------------------------------------------------
# Enable Banking Auth
"""
content = content.replace("# ---------------------------------------------------------------------------\n# Enable Banking Auth", models.strip())

# 3. Update _request_json
request_json_orig = """
    if response.status_code >= 400:
        raise RuntimeError(f"{method} {path} failed: {response.status_code} {payload}")
"""
request_json_new = """
    if response.status_code == 429:
        raise RateLimitError(f"{method} {path} blev afvist af banken (Rate Limit 429).")
    if response.status_code >= 400:
        raise RuntimeError(f"{method} {path} failed: {response.status_code} {payload}")
"""
content = content.replace(request_json_orig.strip(), request_json_new.strip())

Path('backend/app/sync_service.py').write_text(content)
print("Phase 1 done")
