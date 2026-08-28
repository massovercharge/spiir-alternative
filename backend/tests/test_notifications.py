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
