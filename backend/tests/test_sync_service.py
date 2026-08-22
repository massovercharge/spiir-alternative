"""Tests for sync_service — Pydantic models, normalization, and error handling."""
from __future__ import annotations

import pytest

from app.services.sync_service import (
    EnableBankingAccountID,
    EnableBankingAmount,
    EnableBankingTransaction,
    RateLimitError,
    _signed_amount_minor,
)

# ---------------------------------------------------------------------------
# Fixtures: representative bank transaction payloads
# ---------------------------------------------------------------------------

def _make_tx(**overrides) -> EnableBankingTransaction:
    """Build an EnableBankingTransaction with sensible defaults."""
    defaults = {
        "transaction_amount": {"amount": "100.50", "currency": "DKK"},
        "credit_debit_indicator": "CRDT",
        "booking_date": "2026-07-01",
        "value_date": "2026-07-01",
        "entry_reference": "2026-07-01-12.00.00.000000",
        "remittance_information": ["Løn fra arbejdsgiver"],
        "creditor": {"name": "Daniel Wollenberg"},
        "debtor": {"name": "Firma ApS"},
        "creditor_account": {"iban": "DK1234567890"},
        "debtor_account": {"iban": "DK0987654321"},
        "bank_transaction_code": {"code": "PMNT", "description": "Betaling"},
    }
    defaults.update(overrides)
    return EnableBankingTransaction(**defaults)


# ---------------------------------------------------------------------------
# Pydantic Model Parsing
# ---------------------------------------------------------------------------

class TestEnableBankingTransaction:
    """Verify that the Pydantic model handles all flavours of bank JSON."""

    def test_full_payload(self):
        tx = _make_tx()
        assert tx.transaction_amount is not None
        assert tx.transaction_amount.amount == "100.50"
        assert tx.credit_debit_indicator == "CRDT"
        assert tx.creditor.name == "Daniel Wollenberg"

    def test_minimal_payload(self):
        """Bank sends almost nothing — model should still parse."""
        tx = EnableBankingTransaction()
        assert tx.transaction_amount is None
        assert tx.credit_debit_indicator is None
        assert tx.booking_date is None
        assert tx.remittance_information is None
        assert tx.creditor is None

    def test_null_fields_accepted(self):
        """Explicit null from bank JSON should map to None, not crash."""
        tx = EnableBankingTransaction(
            transaction_amount=None,
            creditor=None,
            debtor=None,
            creditor_account=None,
            debtor_account=None,
            bank_transaction_code=None,
            balance_after_transaction=None,
        )
        assert tx.transaction_amount is None
        assert tx.creditor is None

    def test_extra_fields_ignored(self):
        """Bank may add new fields — Pydantic should not crash."""
        tx = EnableBankingTransaction(
            transaction_amount={"amount": "10.00", "currency": "DKK"},
            some_future_field="unexpected",  # not in schema
        )
        assert tx.transaction_amount.amount == "10.00"

    def test_nested_null_amount(self):
        """transaction_amount is present but amount inside is null."""
        tx = EnableBankingTransaction(
            transaction_amount={"amount": None, "currency": "DKK"},
            credit_debit_indicator="CRDT",
        )
        # amount defaults or is None — should not crash
        assert tx.transaction_amount is not None

    def test_empty_remittance_list(self):
        tx = EnableBankingTransaction(remittance_information=[])
        assert tx.remittance_information == []

    def test_remittance_with_none_elements(self):
        """Some banks include null items in the remittance list."""
        tx = EnableBankingTransaction(
            remittance_information=["Betaling", None, "Reference 123"],
        )
        assert len(tx.remittance_information) == 3


# ---------------------------------------------------------------------------
# _signed_amount_minor
# ---------------------------------------------------------------------------

class TestSignedAmountMinor:
    """Test amount extraction and signing from Pydantic models."""

    def test_credit_positive(self):
        tx = _make_tx(
            transaction_amount={"amount": "500.00", "currency": "DKK"},
            credit_debit_indicator="CRDT",
        )
        assert _signed_amount_minor(tx) == 50000

    def test_debit_negative(self):
        tx = _make_tx(
            transaction_amount={"amount": "250.75", "currency": "DKK"},
            credit_debit_indicator="DBIT",
        )
        assert _signed_amount_minor(tx) == -25075

    def test_no_indicator_positive(self):
        """Without credit_debit_indicator the amount should be positive."""
        tx = _make_tx(
            transaction_amount={"amount": "42.00"},
            credit_debit_indicator=None,
        )
        assert _signed_amount_minor(tx) == 4200

    def test_zero_amount(self):
        tx = _make_tx(
            transaction_amount={"amount": "0.00"},
            credit_debit_indicator="CRDT",
        )
        assert _signed_amount_minor(tx) == 0

    def test_missing_transaction_amount(self):
        """If transaction_amount is None, should return 0."""
        tx = _make_tx(transaction_amount=None)
        assert _signed_amount_minor(tx) == 0

    def test_balance_after_transaction_field(self):
        """Test extracting balance_after_transaction via field parameter."""
        tx = _make_tx(
            balance_after_transaction={"amount": "9999.99", "currency": "DKK"},
            credit_debit_indicator="CRDT",
        )
        result = _signed_amount_minor(tx, amount_field=tx.balance_after_transaction)
        assert result == 999999

    def test_balance_uses_own_cdi(self):
        """balance_after_transaction may carry its own credit_debit_indicator."""
        tx = EnableBankingTransaction(
            transaction_amount={"amount": "100.00"},
            credit_debit_indicator=None,  # no top-level indicator
            balance_after_transaction={
                "amount": "500.00",
                "credit_debit_indicator": "DBIT",
            },
        )
        result = _signed_amount_minor(tx, amount_field=tx.balance_after_transaction)
        assert result == -50000

    def test_small_ore_amounts(self):
        tx = _make_tx(
            transaction_amount={"amount": "0.01"},
            credit_debit_indicator="CRDT",
        )
        assert _signed_amount_minor(tx) == 1

    def test_large_amount(self):
        tx = _make_tx(
            transaction_amount={"amount": "1000000.00"},
            credit_debit_indicator="CRDT",
        )
        assert _signed_amount_minor(tx) == 100000000


# ---------------------------------------------------------------------------
# EnableBankingAmount edge cases
# ---------------------------------------------------------------------------

class TestEnableBankingAmount:
    """Verify the Amount sub-model handles edge cases."""

    def test_defaults(self):
        amt = EnableBankingAmount()
        assert amt.amount == "0"
        assert amt.currency is None

    def test_with_values(self):
        amt = EnableBankingAmount(amount="123.45", currency="EUR")
        assert amt.amount == "123.45"
        assert amt.currency == "EUR"

    def test_null_amount_field(self):
        """Bank sends amount: null explicitly."""
        amt = EnableBankingAmount(amount=None)
        # Pydantic may coerce or leave as None depending on version
        # The important thing is it doesn't crash
        assert amt is not None


# ---------------------------------------------------------------------------
# EnableBankingAccountID edge cases
# ---------------------------------------------------------------------------

class TestEnableBankingAccountID:
    def test_iban_only(self):
        acc = EnableBankingAccountID(iban="DK1234567890")
        assert acc.iban == "DK1234567890"
        assert acc.other is None

    def test_other_only(self):
        acc = EnableBankingAccountID(other="SORT-12345678")
        assert acc.iban is None
        assert acc.other == "SORT-12345678"

    def test_both_none(self):
        acc = EnableBankingAccountID()
        assert acc.iban is None
        assert acc.other is None


# ---------------------------------------------------------------------------
# RateLimitError
# ---------------------------------------------------------------------------

class TestRateLimitError:
    def test_is_exception(self):
        assert issubclass(RateLimitError, Exception)

    def test_message(self):
        err = RateLimitError("429 Too Many Requests")
        assert "429" in str(err)

    def test_catchable_separately(self):
        """RateLimitError should be catchable independently of RuntimeError."""
        with pytest.raises(RateLimitError):
            raise RateLimitError("Rate limit hit")

        # Should NOT be caught by RuntimeError
        with pytest.raises(RateLimitError):
            try:
                raise RateLimitError("Rate limit hit")
            except RuntimeError:
                pytest.fail("RateLimitError should not be caught as RuntimeError")


# ---------------------------------------------------------------------------
# Real-world payloads from Danish banks (regression tests)
# ---------------------------------------------------------------------------

class TestRealWorldPayloads:
    """Regression tests using realistic Danish bank transaction shapes."""

    def test_sparekassen_full(self):
        """Sparekassen Danmark style payload with all fields."""
        raw = {
            "booking_date": "2026-07-01",
            "booking_date_time": "2026-07-01T04:30:07.429647",
            "value_date": "2026-07-01",
            "credit_debit_indicator": "CRDT",
            "transaction_amount": {"amount": "1500.00", "currency": "DKK"},
            "balance_after_transaction": {"amount": "12345.67", "currency": "DKK"},
            "remittance_information": ["Overført fra Daniel Wollenberg"],
            "creditor": {"name": "Birk Wollenberg"},
            "debtor": {"name": "Daniel Wollenberg"},
            "creditor_account": {"iban": "DK8490701644034182"},
            "debtor_account": None,
            "bank_transaction_code": None,
            "merchant_category_code": None,
            "entry_reference": "2026-07-01-04.30.07.429647",
        }
        tx = EnableBankingTransaction(**raw)
        assert tx.booking_date == "2026-07-01"
        assert _signed_amount_minor(tx) == 150000
        assert tx.debtor_account is None
        assert tx.creditor_account.iban == "DK8490701644034182"

    def test_null_heavy_payload(self):
        """Minimal bank that sends nulls for nearly everything."""
        raw = {
            "booking_date": "2026-06-15",
            "credit_debit_indicator": "DBIT",
            "transaction_amount": {"amount": "29.95", "currency": "DKK"},
            "balance_after_transaction": None,
            "remittance_information": None,
            "creditor": None,
            "debtor": None,
            "creditor_account": None,
            "debtor_account": None,
            "bank_transaction_code": None,
            "merchant_category_code": None,
            "entry_reference": "REF123456",
        }
        tx = EnableBankingTransaction(**raw)
        assert _signed_amount_minor(tx) == -2995
        assert tx.creditor is None
        assert tx.balance_after_transaction is None

    def test_missing_amount_entirely(self):
        """Edge case: transaction_amount key missing from JSON."""
        raw = {
            "booking_date": "2026-06-20",
            "credit_debit_indicator": "CRDT",
            "entry_reference": "NO-AMOUNT-TX",
        }
        tx = EnableBankingTransaction(**raw)
        assert _signed_amount_minor(tx) == 0

    def test_empty_string_entry_reference(self):
        raw = {
            "booking_date": "2026-06-20",
            "transaction_amount": {"amount": "10.00"},
            "entry_reference": "",
        }
        tx = EnableBankingTransaction(**raw)
        assert tx.entry_reference == ""

    def test_remittance_multiline(self):
        """Some banks send multiple remittance lines."""
        raw = {
            "booking_date": "2026-07-10",
            "transaction_amount": {"amount": "500.00", "currency": "DKK"},
            "credit_debit_indicator": "DBIT",
            "remittance_information": [
                "Dankort-køb",
                "NETTO 1234",
                "Den 10.07.2026",
            ],
            "entry_reference": "MULTI-REM-001",
        }
        tx = EnableBankingTransaction(**raw)
        assert len(tx.remittance_information) == 3
        assert _signed_amount_minor(tx) == -50000
