import re
from pathlib import Path

content = Path('backend/app/sync_service.py').read_text()

# Update _signed_amount_minor
# We will just redefine it to take EnableBankingTransaction
signed_amount_orig = """
def _signed_amount_minor(transaction: dict[str, Any], field: str = "transaction_amount") -> int:
    \"\"\"Extract and sign the transaction amount as integer minor units (øre/cents).\"\"\"
    field_data = transaction.get(field) or {}
    raw = str(field_data.get("amount") or "0")
    minor = to_minor(raw)
    if transaction.get("credit_debit_indicator") == "DBIT":
        return -abs(minor)
    return abs(minor)
"""
signed_amount_new = """
def _signed_amount_minor(tx: "EnableBankingTransaction", field: str = "transaction_amount") -> int:
    \"\"\"Extract and sign the transaction amount as integer minor units (øre/cents).\"\"\"
    field_data = getattr(tx, field, None)
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
"""
content = content.replace(signed_amount_orig.strip(), signed_amount_new.strip())

# Update _description
desc_orig = """
def _description(transaction: dict[str, Any]) -> str:
    remittance = _join_lines(transaction.get("remittance_information"))
    if remittance:
        return remittance
    party = _party_name(transaction.get("creditor")) or _party_name(transaction.get("debtor"))
    if party:
        return party
    return "Ukendt transaktion"
"""
desc_new = """
def _description(tx: "EnableBankingTransaction") -> str:
    remittance = "\\n".join(tx.remittance_information) if tx.remittance_information else ""
    if remittance:
        return remittance
    party = (tx.creditor.name if tx.creditor else None) or (tx.debtor.name if tx.debtor else None)
    if party:
        return party
    return "Ukendt transaktion"
"""
content = content.replace(desc_orig.strip(), desc_new.strip())

# Update _party_name and _join_lines (we can just remove them or leave them unused)

Path('backend/app/sync_service.py').write_text(content)
print("Phase 2.1 done")
