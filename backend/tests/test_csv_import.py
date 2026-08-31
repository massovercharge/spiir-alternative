"""Tests for Spiir CSV export importer."""

from sqlmodel import Session, select

from app.models import (
    Account,
    Category,
    Posting,
    PostingAllocation,
    Tag,
    engine,
)
from app.services.csv_service import _parse_amount, _parse_date, import_spiir_csv


def test_parse_amount():
    assert _parse_amount("-5.231,28") == -523128
    assert _parse_amount("1.250,00") == 125000
    assert _parse_amount("0,50") == 50
    assert _parse_amount("-100") == -10000
    assert _parse_amount("") == 0
    assert _parse_amount("invalid") == 0


def test_parse_date():
    assert _parse_date("04-10-2019") == "2019-10-04"
    assert _parse_date("2026-08-25") == "2026-08-25"


def test_import_spiir_csv_new_and_allocations():
    # Setup Category in DB
    with Session(engine) as db:
        cat = Category(
            id="dagligvarer|supermarked",
            main_name="Dagligvarer",
            sub_name="Supermarked",
            category_type="Expense",
            expense_type="Variable",
        )
        db.add(cat)
        db.commit()

    csv_data = (
        "Date;Amount;Description;OriginalDescription;MainCategoryName;CategoryName;AccountId;AccountName;Comment;Extraordinary;Tags;Id;Currency\n"
        "15-05-2023;-150,50;Netto Nørrebro;DANKORT-KVITT;Dagligvarer;Supermarked;acc_1;Lønkonto;Ugentlig indkøb;No;mad,fest;tx_123;DKK\n"
    )

    stats = import_spiir_csv(csv_data)
    assert stats["total_rows"] == 1
    assert stats["imported_new"] == 1
    assert stats["accounts_created"] == 1

    with Session(engine) as db:
        acc = db.exec(select(Account).where(Account.uid == "csv:acc_1")).first()
        assert acc is not None
        assert "Lønkonto" in acc.name

        posting = db.exec(select(Posting).where(Posting.id == "csv:acc_1:tx_123")).first()
        assert posting is not None
        assert posting.amount_minor == -15050
        assert posting.booking_date == "2023-05-15"

        alloc = db.exec(
            select(PostingAllocation).where(PostingAllocation.posting_id == posting.id)
        ).first()
        assert alloc is not None
        assert alloc.amount_minor == -15050
        assert alloc.category_id == "dagligvarer|supermarked"
        assert alloc.note == "Ugentlig indkøb"
        assert not alloc.is_extraordinary

        tags = db.exec(select(Tag)).all()
        tag_names = {t.name for t in tags}
        assert "mad" in tag_names
        assert "fest" in tag_names


def test_import_spiir_csv_merge_existing():
    with Session(engine) as db:
        acc = Account(uid="acc_main", name="Main Bank", source="bank")
        db.add(acc)
        posting = Posting(
            id="p_existing",
            account_uid="acc_main",
            booking_date="2023-06-01",
            amount_minor=-25000,
            original_description="SuperBrugsen",
        )
        db.add(posting)
        alloc = PostingAllocation(
            id="a_existing",
            posting_id="p_existing",
            amount_minor=-25000,
            category_id="diverse|ikke-kategoriseret",
        )
        db.add(alloc)
        cat = Category(
            id="dagligvarer|supermarked",
            main_name="Dagligvarer",
            sub_name="Supermarked",
            category_type="Expense",
            expense_type="Variable",
        )
        db.add(cat)
        db.commit()

    csv_data = (
        "Date;Amount;Description;OriginalDescription;MainCategoryName;CategoryName;AccountId;AccountName;Comment;Extraordinary;Tags;Id;Currency\n"
        "01-06-2023;-250,00;Brugsen;SuperBrugsen;Dagligvarer;Supermarked;acc_spiir;Spiir Account;Mad til gæster;Yes;grill;tx_999;DKK\n"
    )

    stats = import_spiir_csv(csv_data)
    assert stats["total_rows"] == 1
    assert stats["merged_existing"] == 1

    with Session(engine) as db:
        alloc = db.exec(
            select(PostingAllocation).where(PostingAllocation.id == "a_existing")
        ).first()
        assert alloc is not None
        assert alloc.category_id == "dagligvarer|supermarked"
        assert alloc.note == "Mad til gæster"
        assert alloc.is_extraordinary is True
