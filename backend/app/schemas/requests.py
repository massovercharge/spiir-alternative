from typing import Any, Literal, Optional

from pydantic import BaseModel, Field, field_validator


# Households
class HouseholdCreateRequest(BaseModel):
    name: str = Field(..., min_length=1)

class HouseholdUpdateRequest(BaseModel):
    name: str = Field(..., min_length=1)

class HouseholdInviteRequest(BaseModel):
    email: str = Field(..., min_length=3)
    role: Optional[Literal["owner", "member"]] = Field(default="member")

    @field_validator("email", mode="before")
    @classmethod
    def normalize_email(cls, v: Any) -> str:
        if isinstance(v, str):
            return v.strip().lower()
        return v

class HouseholdMemberRoleUpdateRequest(BaseModel):
    role: Literal["owner", "member"]

# Accounts
class AccountUpdateRequest(BaseModel):
    name: str = Field(..., min_length=1)
    account_type: Optional[str] = None
    savings_category_id: Optional[str] = None

# Transactions
class TransactionPatch(BaseModel):
    category_id: Optional[str] = None
    custom_note: Optional[str] = None
    is_extraordinary: Optional[bool] = None
    is_excluded: Optional[bool] = None
    custom_date: Optional[str] = None
    tags: Optional[list[str]] = None

class TransactionsUpdateRequest(BaseModel):
    transaction_ids: list[str]
    patch: TransactionPatch

class TransactionCategoryUpdateRequest(BaseModel):
    category_id: str

class TransactionSplitItem(BaseModel):
    amount_minor: int
    category_id: Optional[str] = None
    note: Optional[str] = None
    item_name: Optional[str] = None
    item_cluster_id: Optional[str] = None
    is_extraordinary: Optional[bool] = False

class TransactionSplitRequest(BaseModel):
    splits: list[TransactionSplitItem] = Field(..., min_length=1)

class TransactionLinkReceiptRequest(BaseModel):
    receipt_id: str

# Rules
class RuleCreateRequest(BaseModel):
    match_pattern: str = Field(..., min_length=1)
    category_id: str
    is_regex: Optional[bool] = False
    partial_match: Optional[bool] = False
    priority: Optional[int] = 500

class RuleUpdateRequest(BaseModel):
    match_pattern: Optional[str] = None
    category_id: Optional[str] = None
    is_regex: Optional[bool] = None
    partial_match: Optional[bool] = None
    priority: Optional[int] = None
    is_active: Optional[bool] = None

# Budgets
class BudgetUpsertRequest(BaseModel):
    category_id: str
    year: int
    month: int
    amount_minor: int
    budget_type: Optional[str] = "limit"
    rollover: Optional[bool] = False

class BudgetBillItem(BaseModel):
    name: str
    amount_minor: int
    months: list[int]

class BudgetBillsUpsertRequest(BaseModel):
    category_id: str
    year: int
    bills: list[BudgetBillItem] = []

# Sync & Bank
class BankConnectRequest(BaseModel):
    redirect_url: str
    bank_name: str

class BankCallbackRequest(BaseModel):
    code: str

class StoreboxImportLinkRequest(BaseModel):
    url: str

# Recurring
class RecurringCreateRequest(BaseModel):
    name: str
    amount_minor: int
    interval: Optional[str] = "monthly"
    category_id: Optional[str] = None
    account_uid: Optional[str] = None
    match_pattern: str

# Inbound Email
class InboundEmailTestRequest(BaseModel):
    raw_content: Optional[str] = None
    url: Optional[str] = None
    subject: Optional[str] = None
    sender: Optional[str] = None

