import datetime as dt

from sqlmodel import Session

from app.models import (
    Account,
    BankConnection,
    Category,
    Posting,
    PostingAllocation,
    all_models,
)
from app.services.notification_service import (
    detect_duplicate_payments,
    detect_expiring_consents,
    detect_rule_suggestions,
    get_household_notifications,
)
from app.services.reconciliation_service import (
    dismiss_all_same_account_duplicates,
    dismiss_duplicate_pair,
    get_duplicate_groups_preview,
)
from app.services.transaction_service import get_transaction, list_transactions
from tests.conftest import TEST_HOUSEHOLD_ID


def test_detect_duplicate_payments():
    with Session(all_models.engine) as session:
        acc = Account(uid="acc1", household_id=TEST_HOUSEHOLD_ID, name="Checking", currency="DKK")
        session.add(acc)

        p1 = Posting(
            id="p1",
            household_id=TEST_HOUSEHOLD_ID,
            account_uid="acc1",
            booking_date="2026-01-22",
            amount_minor=-3200,
            original_description="MobilePay Annelise Petersen Løvholt",
        )
        p2 = Posting(
            id="p2",
            household_id=TEST_HOUSEHOLD_ID,
            account_uid="acc1",
            booking_date="2026-01-22",
            amount_minor=-3200,
            original_description="MobilePay Annelise Petersen Løvholt",
        )
        # Different date - not a duplicate
        p3 = Posting(
            id="p3",
            household_id=TEST_HOUSEHOLD_ID,
            account_uid="acc1",
            booking_date="2026-01-23",
            amount_minor=-3200,
            original_description="MobilePay Annelise Petersen Løvholt",
        )
        session.add_all([p1, p2, p3])
        session.commit()

        notifs = detect_duplicate_payments(session, TEST_HOUSEHOLD_ID)
        assert len(notifs) == 1
        assert notifs[0]["type"] == "duplicate_payment"
        assert notifs[0]["metadata"]["count"] == 2
        assert set(notifs[0]["metadata"]["transaction_ids"]) == {"p1", "p2"}


def test_transaction_list_and_detail_duplicate_metadata():
    with Session(all_models.engine) as session:
        acc = Account(uid="acc1", household_id=TEST_HOUSEHOLD_ID, name="Checking", currency="DKK")
        session.add(acc)

        p1 = Posting(
            id="p1",
            household_id=TEST_HOUSEHOLD_ID,
            account_uid="acc1",
            booking_date="2026-01-30",
            amount_minor=-3000,
            original_description="MobilePay HTy 45 jubilee ??",
        )
        p2 = Posting(
            id="p2",
            household_id=TEST_HOUSEHOLD_ID,
            account_uid="acc1",
            booking_date="2026-01-30",
            amount_minor=-3000,
            original_description="MobilePay HTy 45 jubilee ??",
        )
        p3 = Posting(
            id="p3",
            household_id=TEST_HOUSEHOLD_ID,
            account_uid="acc1",
            booking_date="2026-01-30",
            amount_minor=-5000,
            original_description="Supermarket",
        )
        session.add_all([p1, p2, p3])
        session.commit()

    # Test list_transactions returns duplicate metadata
    res = list_transactions()
    tx_map = {t["id"]: t for t in res["transactions"]}
    assert tx_map["p1"]["has_duplicate_warning"] is True
    assert tx_map["p1"]["duplicate_count"] == 2
    assert tx_map["p1"]["duplicate_sibling_ids"] == ["p2"]

    assert tx_map["p2"]["has_duplicate_warning"] is True
    assert tx_map["p2"]["duplicate_sibling_ids"] == ["p1"]

    assert tx_map["p3"]["has_duplicate_warning"] is False

    # Test filter by dubletter
    filtered = list_transactions(filter_type="dubletter")
    assert len(filtered["transactions"]) == 2
    assert {t["id"] for t in filtered["transactions"]} == {"p1", "p2"}

    # Test get_transaction detail
    detail1 = get_transaction("p1")
    assert detail1 is not None
    assert detail1["has_duplicate_warning"] is True
    assert detail1["duplicate_sibling_ids"] == ["p2"]


def test_detect_expiring_consents():
    with Session(all_models.engine) as session:
        # Expiring in 4 days
        exp_date = (dt.datetime.now(dt.UTC) + dt.timedelta(days=4)).isoformat()
        conn = BankConnection(
            id="conn1",
            household_id=TEST_HOUSEHOLD_ID,
            bank_name="Spar Nord",
            consent_expires_at=exp_date,
            status="active",
        )
        session.add(conn)
        session.commit()

        notifs = detect_expiring_consents(session, TEST_HOUSEHOLD_ID)
        assert len(notifs) == 1
        assert notifs[0]["type"] == "consent_expiring"
        assert notifs[0]["metadata"]["bank_name"] == "Spar Nord"


def test_detect_rule_suggestions():
    with Session(all_models.engine) as session:
        acc = Account(uid="acc1", household_id=TEST_HOUSEHOLD_ID, name="Checking", currency="DKK")
        session.add(acc)
        cat = Category(id="fornøjelser|musik-lyd", main_name="Fornøjelser", sub_name="Musik & Lyd")
        session.add(cat)

        for i in range(3):
            p = Posting(
                id=f"tx_{i}",
                household_id=TEST_HOUSEHOLD_ID,
                account_uid="acc1",
                booking_date=f"2026-01-0{i+1}",
                amount_minor=-9900,
                original_description="Spotify AB",
            )
            alloc = PostingAllocation(
                id=f"alloc_{i}",
                posting_id=p.id,
                category_id="fornøjelser|musik-lyd",
                amount_minor=-9900,
            )
            session.add_all([p, alloc])
        session.commit()

        notifs = detect_rule_suggestions(session, TEST_HOUSEHOLD_ID)
        assert len(notifs) == 1
        assert notifs[0]["type"] == "rule_suggestion"
        assert notifs[0]["metadata"]["match_pattern"] == "spotify ab"
        assert notifs[0]["metadata"]["category_id"] == "fornøjelser|musik-lyd"


def test_get_household_notifications_aggregation():
    with Session(all_models.engine) as session:
        acc = Account(uid="acc1", household_id=TEST_HOUSEHOLD_ID, name="Checking", currency="DKK")
        session.add(acc)

        p1 = Posting(id="a1", household_id=TEST_HOUSEHOLD_ID, account_uid="acc1", booking_date="2026-01-01", amount_minor=-1000, original_description="Baker")
        p2 = Posting(id="a2", household_id=TEST_HOUSEHOLD_ID, account_uid="acc1", booking_date="2026-01-01", amount_minor=-1000, original_description="Baker")
        session.add_all([p1, p2])
        session.commit()

    all_notifs = get_household_notifications(TEST_HOUSEHOLD_ID)
    assert len(all_notifs) >= 1
    assert any(n["type"] == "duplicate_payment" for n in all_notifs)


def test_statutory_benefits_and_income_not_flagged_as_duplicates():
    with Session(all_models.engine) as session:
        acc1 = Account(uid="acc_parent1", household_id=TEST_HOUSEHOLD_ID, name="Parent 1 NemKonto", currency="DKK")
        acc2 = Account(uid="acc_parent2", household_id=TEST_HOUSEHOLD_ID, name="Parent 2 NemKonto", currency="DKK")
        session.add_all([acc1, acc2])

        # Positive income: Børne- og Ungeydelse received by both parents on Jan 20th
        p1 = Posting(
            id="by1",
            household_id=TEST_HOUSEHOLD_ID,
            account_uid="acc_parent1",
            booking_date="2026-01-20",
            amount_minor=237400,
            original_description="Udbetaling Danmark Børne- og ungeydelse",
        )
        p2 = Posting(
            id="by2",
            household_id=TEST_HOUSEHOLD_ID,
            account_uid="acc_parent2",
            booking_date="2026-01-20",
            amount_minor=237400,
            original_description="Udbetaling Danmark Børne- og ungeydelse",
        )
        session.add_all([p1, p2])
        session.commit()

        notifs = detect_duplicate_payments(session, TEST_HOUSEHOLD_ID)
        assert len(notifs) == 0

        # Also verify list_transactions does not set has_duplicate_warning
        tx_list = list_transactions(limit=10)
        for tx in tx_list["transactions"]:
            assert tx.get("has_duplicate_warning") is False


def test_dismiss_duplicate_pair_and_all_same_account():
    with Session(all_models.engine) as session:
        acc = Account(uid="acc_same", household_id=TEST_HOUSEHOLD_ID, name="Checking", currency="DKK")
        session.add(acc)

        p1 = Posting(
            id="dp1",
            household_id=TEST_HOUSEHOLD_ID,
            account_uid="acc_same",
            booking_date="2026-03-01",
            amount_minor=-4500,
            original_description="Kaffebaren",
        )
        p2 = Posting(
            id="dp2",
            household_id=TEST_HOUSEHOLD_ID,
            account_uid="acc_same",
            booking_date="2026-03-01",
            amount_minor=-4500,
            original_description="Kaffebaren",
        )
        session.add_all([p1, p2])
        session.commit()

        # Before dismissing, it appears in preview and notifications
        groups = get_duplicate_groups_preview(session, TEST_HOUSEHOLD_ID)
        assert len(groups) == 1
        assert groups[0]["can_auto_merge"] is False

        notifs = detect_duplicate_payments(session, TEST_HOUSEHOLD_ID)
        assert len(notifs) == 1

        tx_detail = get_transaction("dp1")
        assert tx_detail["has_duplicate_warning"] is True

        # Now dismiss the duplicate pair
        dismiss_count = dismiss_duplicate_pair(session, TEST_HOUSEHOLD_ID, ["dp1", "dp2"])
        assert dismiss_count == 1

        # Now verify it no longer appears in preview, notifications, or transaction warning
        groups_after = get_duplicate_groups_preview(session, TEST_HOUSEHOLD_ID)
        assert len(groups_after) == 0

        notifs_after = detect_duplicate_payments(session, TEST_HOUSEHOLD_ID)
        assert len(notifs_after) == 0

        tx_detail_after = get_transaction("dp1")
        assert tx_detail_after["has_duplicate_warning"] is False

        # Add another pair and test dismiss_all_same_account_duplicates
        p3 = Posting(id="dp3", household_id=TEST_HOUSEHOLD_ID, account_uid="acc_same", booking_date="2026-03-02", amount_minor=-2000, original_description="Netto")
        p4 = Posting(id="dp4", household_id=TEST_HOUSEHOLD_ID, account_uid="acc_same", booking_date="2026-03-02", amount_minor=-2000, original_description="Netto")
        session.add_all([p3, p4])
        session.commit()

        bulk_dismissed = dismiss_all_same_account_duplicates(session, TEST_HOUSEHOLD_ID)
        assert bulk_dismissed >= 1
        assert len(get_duplicate_groups_preview(session, TEST_HOUSEHOLD_ID)) == 0


