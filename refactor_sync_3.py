import re
from pathlib import Path

content = Path('backend/app/sync_service.py').read_text()

loop_orig = """
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

            existing = db.get(Posting, tx_id)
            if existing is not None:
                # Update amount/description if changed, but preserve user overrides
                existing.amount_minor = _signed_amount_minor(raw_tx)
                existing.original_description = _description(raw_tx)
                continue

            balance_amount = None
            if raw_tx.get("balance_after_transaction"):
                bal_minor = _signed_amount_minor(raw_tx, field="balance_after_transaction")
                # Sometimes it doesn't have credit_debit_indicator for balance, fallback to raw parsing
                if bal_minor == 0 and raw_tx["balance_after_transaction"].get("amount"):
                    try:
                        from .money import to_minor
                        bal_minor = to_minor(raw_tx["balance_after_transaction"]["amount"])
                        if raw_tx["balance_after_transaction"].get("credit_debit_indicator") == "DBIT":
                            bal_minor = -bal_minor
                    except Exception:
                        bal_minor = 0
                balance_amount = bal_minor

            posting = Posting(
                id=tx_id,
                account_uid=account_uid,
                booking_date=booking_date,
                booking_date_time=raw_tx.get("booking_date_time"),
                value_date=raw_tx.get("value_date"),
                amount_minor=_signed_amount_minor(raw_tx),
                currency=(raw_tx.get("transaction_amount") or {}).get("currency") or account_currency,
                credit_debit_indicator=raw_tx.get("credit_debit_indicator"),
                original_description=_description(raw_tx),
                remittance_information=_join_lines(raw_tx.get("remittance_information")),
                creditor_name=_party_name(raw_tx.get("creditor")),
                debtor_name=_party_name(raw_tx.get("debtor")),
                creditor_account=(raw_tx.get("creditor_account") or {}).get("iban") or (raw_tx.get("creditor_account") or {}).get("other"),
                debtor_account=(raw_tx.get("debtor_account") or {}).get("iban") or (raw_tx.get("debtor_account") or {}).get("other"),
                merchant_category_code=raw_tx.get("merchant_category_code"),
                entry_reference=entry_reference,
                transaction_type=(raw_tx.get("bank_transaction_code") or {}).get("description"),
                transaction_type_code=(raw_tx.get("bank_transaction_code") or {}).get("code"),
                balance_after_transaction_minor=balance_amount,
            )
"""

loop_new = """
        # Upsert transactions
        for raw_dict in raw_transactions:
            try:
                tx = EnableBankingTransaction(**raw_dict)
            except Exception as e:
                print(f"Skipping malformed transaction: {e}")
                continue
                
            entry_reference = str(tx.entry_reference or "")
            tx_id = f"eb:{account_uid}:{entry_reference}"
            booking_date = (
                tx.booking_date
                or tx.transaction_date
                or tx.value_date
                or ""
            )

            existing = db.get(Posting, tx_id)
            if existing is not None:
                # Update amount/description if changed, but preserve user overrides
                existing.amount_minor = _signed_amount_minor(tx)
                existing.original_description = _description(tx)
                continue

            balance_amount = None
            if tx.balance_after_transaction:
                balance_amount = _signed_amount_minor(tx, field="balance_after_transaction")

            posting = Posting(
                id=tx_id,
                account_uid=account_uid,
                booking_date=booking_date,
                booking_date_time=tx.booking_date_time,
                value_date=tx.value_date,
                amount_minor=_signed_amount_minor(tx),
                currency=(tx.transaction_amount.currency if tx.transaction_amount else None) or account_currency,
                credit_debit_indicator=tx.credit_debit_indicator,
                original_description=_description(tx),
                remittance_information="\\n".join(tx.remittance_information) if tx.remittance_information else "",
                creditor_name=tx.creditor.name if tx.creditor else None,
                debtor_name=tx.debtor.name if tx.debtor else None,
                creditor_account=(tx.creditor_account.iban or tx.creditor_account.other) if tx.creditor_account else None,
                debtor_account=(tx.debtor_account.iban or tx.debtor_account.other) if tx.debtor_account else None,
                merchant_category_code=tx.merchant_category_code,
                entry_reference=entry_reference,
                transaction_type=tx.bank_transaction_code.description if tx.bank_transaction_code else None,
                transaction_type_code=tx.bank_transaction_code.code if tx.bank_transaction_code else None,
                balance_after_transaction_minor=balance_amount,
            )
"""
content = content.replace(loop_orig.strip(), loop_new.strip())
Path('backend/app/sync_service.py').write_text(content)
print("Phase 3 done")
