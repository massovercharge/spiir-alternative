from unittest.mock import patch

from conftest import TEST_HOUSEHOLD_ID, test_engine
from sqlmodel import Session

from app.models import Account, Posting, PostingAllocation
from app.services.transaction_service import (
    fix_receipt_difference_categories,
    link_receipt_to_transaction,
)


def test_link_receipt_assigns_category_to_difference():
    # Setup test account and posting
    with Session(test_engine) as db:
        acc = Account(
            uid="acc-test-1",
            household_id=TEST_HOUSEHOLD_ID,
            name="Checking",
            currency="DKK",
            created_at="2026-01-01T00:00:00Z",
            updated_at="2026-01-01T00:00:00Z",
        )
        db.add(acc)

        posting = Posting(
            id="post-diff-1",
            household_id=TEST_HOUSEHOLD_ID,
            account_uid="acc-test-1",
            amount_minor=-46545,  # 465.45 kr
            booking_date="2026-08-20",
            original_description="Dankort-køb Netto",
            created_at="2026-08-20T10:00:00Z",
            updated_at="2026-08-20T10:00:00Z",
        )
        db.add(posting)

        # Existing allocation was Dagligvarer
        alloc = PostingAllocation(
            id="alloc-diff-1",
            posting_id="post-diff-1",
            household_id=TEST_HOUSEHOLD_ID,
            category_id="husholdning|dagligvarer",
            amount_minor=-46545,
            created_at="2026-08-20T10:00:00Z",
            updated_at="2026-08-20T10:00:00Z",
        )
        db.add(alloc)
        db.commit()

    mock_receipt = {
        "receipt": {
            "receipt_id": "rec-123",
            "merchant_key": "netto",
            "merchant_name": "Netto",
            "receipt_total_minor": 46545,
            "unassigned_discount_total_minor": 0,
        },
        "occurrences": [
            {
                "display_name": "Øko Tofu Naturel",
                "net_total_minor": 8623,
                "cluster_id": "tofu",
            },
            {
                "display_name": "Peanuts 250 g",
                "net_total_minor": 938,
                "cluster_id": "peanuts",
            },
            {
                "display_name": "Øvrige varer",
                "net_total_minor": 37284,
                "cluster_id": "other",
            },
        ],  # Sum of items = 8623 + 938 + 37284 = 46845, difference = -300 (-3.00 kr)
    }

    with patch("app.services.kvitteringer_service.get_receipt", return_value=mock_receipt):
        result = link_receipt_to_transaction("post-diff-1", "rec-123", is_auto=True)

    allocations = result["allocations"]
    assert len(allocations) == 4

    diff_alloc = next(a for a in allocations if a["item_name"] == "Difference / Gebyr")
    assert diff_alloc["amount_minor"] == 300 or diff_alloc["amount_minor"] == -300
    assert diff_alloc["category_id"] == "husholdning|dagligvarer"


def test_link_receipt_infers_merchant_category_when_no_prior_category():
    with Session(test_engine) as db:
        acc = Account(
            uid="acc-test-2",
            household_id=TEST_HOUSEHOLD_ID,
            name="Checking",
            currency="DKK",
            created_at="2026-01-01T00:00:00Z",
            updated_at="2026-01-01T00:00:00Z",
        )
        db.add(acc)

        posting = Posting(
            id="post-diff-2",
            household_id=TEST_HOUSEHOLD_ID,
            account_uid="acc-test-2",
            amount_minor=-10000,
            booking_date="2026-08-20",
            original_description="Ubekendt post 123",
            created_at="2026-08-20T10:00:00Z",
            updated_at="2026-08-20T10:00:00Z",
        )
        db.add(posting)

        alloc = PostingAllocation(
            id="alloc-diff-2",
            posting_id="post-diff-2",
            household_id=TEST_HOUSEHOLD_ID,
            category_id="diverse|ikke-kategoriseret",
            amount_minor=-10000,
            created_at="2026-08-20T10:00:00Z",
            updated_at="2026-08-20T10:00:00Z",
        )
        db.add(alloc)
        db.commit()

    mock_receipt = {
        "receipt": {
            "receipt_id": "rec-456",
            "merchant_key": "rema1000",
            "merchant_name": "Rema 1000",
            "receipt_total_minor": 10000,
            "unassigned_discount_total_minor": 0,
        },
        "occurrences": [
            {
                "display_name": "Mælk 1L",
                "net_total_minor": 1295,
                "cluster_id": "milk",
            },
        ],
    }

    with patch("app.services.kvitteringer_service.get_receipt", return_value=mock_receipt):
        result = link_receipt_to_transaction("post-diff-2", "rec-456", is_auto=True)

    allocations = result["allocations"]
    diff_alloc = next(a for a in allocations if a["item_name"] == "Difference / Gebyr")
    assert diff_alloc["category_id"] == "husholdning|dagligvarer"


def test_fix_receipt_difference_categories_migration():
    with Session(test_engine) as db:
        acc = Account(
            uid="acc-test-3",
            household_id=TEST_HOUSEHOLD_ID,
            name="Checking",
            currency="DKK",
            created_at="2026-01-01T00:00:00Z",
            updated_at="2026-01-01T00:00:00Z",
        )
        db.add(acc)

        posting = Posting(
            id="post-diff-3",
            household_id=TEST_HOUSEHOLD_ID,
            account_uid="acc-test-3",
            amount_minor=-5000,
            booking_date="2026-08-20",
            original_description="MobilePay køb MobilePay Coop App",
            created_at="2026-08-20T10:00:00Z",
            updated_at="2026-08-20T10:00:00Z",
        )
        db.add(posting)

        # Sibling item allocation
        item_alloc = PostingAllocation(
            id="alloc-item-3",
            posting_id="post-diff-3",
            household_id=TEST_HOUSEHOLD_ID,
            category_id="husholdning|dagligvarer",
            item_name="Rugbrød",
            amount_minor=-4000,
            created_at="2026-08-20T10:00:00Z",
            updated_at="2026-08-20T10:00:00Z",
        )
        db.add(item_alloc)

        # Difference allocation without category and without item_name
        diff_alloc = PostingAllocation(
            id="alloc-diff-3",
            posting_id="post-diff-3",
            household_id=TEST_HOUSEHOLD_ID,
            category_id=None,
            item_name=None,
            amount_minor=-1000,
            created_at="2026-08-20T10:00:00Z",
            updated_at="2026-08-20T10:00:00Z",
        )
        db.add(diff_alloc)
        db.commit()

    fixed_count = fix_receipt_difference_categories()
    assert fixed_count == 1

    with Session(test_engine) as db:
        updated_alloc = db.get(PostingAllocation, "alloc-diff-3")
        assert updated_alloc.category_id == "husholdning|dagligvarer"
        assert updated_alloc.item_name == "Difference / Gebyr"
