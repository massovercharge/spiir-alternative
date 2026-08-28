import pytest
from sqlmodel import Session, SQLModel, create_engine
from app.models import Account, Household, Posting, PostingAllocation, current_household_id
from app.services.reconciliation_service import (
    consolidate_posting_pair,
    find_duplicate_candidate_in_db,
    merge_accounts,
    reconcile_incoming_postings,
)

@pytest.fixture(name="session")
def session_fixture():
    token = current_household_id.set("hh_1")
    engine = create_engine("sqlite:///:memory:")
    SQLModel.metadata.create_all(engine)
    with Session(engine) as session:
        yield session
    current_household_id.reset(token)

def test_consolidate_posting_pair_categories_and_notes(session: Session):
    hh = Household(id="hh_1", name="Test Household")
    session.add(hh)
    
    acc_bank = Account(uid="acc_bank", name="SparD Plus", source="enablebanking", household_id="hh_1")
    acc_csv = Account(uid="acc_csv", name="SparD Plus (Spiir)", source="csv", household_id="hh_1")
    session.add_all([acc_bank, acc_csv])
    session.commit()

    p_bank = Posting(
        id="eb:acc_bank:123",
        household_id="hh_1",
        account_uid="acc_bank",
        booking_date="2026-05-10",
        amount_minor=-15000,
        original_description="MobilePay Natalia Andrea",
    )
    p_csv = Posting(
        id="csv:acc_csv:456",
        household_id="hh_1",
        account_uid="acc_csv",
        booking_date="2026-05-10",
        amount_minor=-15000,
        original_description="MobilePay Natalia Andrea",
    )
    session.add_all([p_bank, p_csv])
    session.commit()

    alloc_bank = PostingAllocation(
        id="alloc_b",
        household_id="hh_1",
        posting_id=p_bank.id,
        category_id="diverse|ikke-kategoriseret",
        amount_minor=-15000,
        note="",
    )
    alloc_csv = PostingAllocation(
        id="alloc_c",
        household_id="hh_1",
        posting_id=p_csv.id,
        category_id="privatforbrug|gaver-velgørenhed",
        amount_minor=-15000,
        note="Fødselsdagsgave",
    )
    session.add_all([alloc_bank, alloc_csv])
    session.commit()

    # Consolidate
    stats = consolidate_posting_pair(session, kept_posting_id=p_bank.id, removed_posting_id=p_csv.id)
    session.commit()

    assert stats["categories_migrated"] is True
    assert stats["notes_migrated"] is True

    # Check remaining
    assert session.get(Posting, p_csv.id) is None
    kept = session.get(Posting, p_bank.id)
    assert kept is not None

    kept_alloc = session.get(PostingAllocation, alloc_bank.id)
    assert kept_alloc.category_id == "privatforbrug|gaver-velgørenhed"
    assert kept_alloc.note == "Fødselsdagsgave"

def test_consolidate_posting_pair_with_splits(session: Session):
    hh = Household(id="hh_1", name="Test Household")
    session.add(hh)
    
    acc_bank = Account(uid="acc_bank", name="SparD Plus", source="enablebanking", household_id="hh_1")
    acc_csv = Account(uid="acc_csv", name="SparD Plus (Spiir)", source="csv", household_id="hh_1")
    session.add_all([acc_bank, acc_csv])
    session.commit()

    p_bank = Posting(
        id="eb:acc_bank:789",
        household_id="hh_1",
        account_uid="acc_bank",
        booking_date="2026-04-01",
        amount_minor=-20000,
        original_description="Netto Supermarked",
    )
    p_csv = Posting(
        id="csv:acc_csv:789",
        household_id="hh_1",
        account_uid="acc_csv",
        booking_date="2026-04-01",
        amount_minor=-20000,
        original_description="Netto Supermarked",
    )
    session.add_all([p_bank, p_csv])
    session.commit()

    alloc_bank = PostingAllocation(
        id="alloc_b_default",
        household_id="hh_1",
        posting_id=p_bank.id,
        category_id="diverse|ikke-kategoriseret",
        amount_minor=-20000,
    )
    alloc_csv_1 = PostingAllocation(
        id="alloc_c_split1",
        household_id="hh_1",
        posting_id=p_csv.id,
        category_id="husholdning|dagligvarer",
        amount_minor=-15000,
    )
    alloc_csv_2 = PostingAllocation(
        id="alloc_c_split2",
        household_id="hh_1",
        posting_id=p_csv.id,
        category_id="fritid|personlig-pleje",
        amount_minor=-5000,
    )
    session.add_all([alloc_bank, alloc_csv_1, alloc_csv_2])
    session.commit()

    # Consolidate
    stats = consolidate_posting_pair(session, kept_posting_id=p_bank.id, removed_posting_id=p_csv.id)
    session.commit()

    assert stats["splits_migrated"] is True
    from sqlmodel import select
    bank_allocs = session.exec(select(PostingAllocation).where(PostingAllocation.posting_id == p_bank.id)).all()
    assert len(bank_allocs) == 2
    assert {a.category_id for a in bank_allocs} == {"husholdning|dagligvarer", "fritid|personlig-pleje"}
    assert sum(a.amount_minor for a in bank_allocs) == -20000

def test_reconcile_incoming_postings(session: Session):
    hh = Household(id="hh_1", name="Test Household")
    session.add(hh)
    
    acc_bank = Account(uid="acc_bank", name="SparD Plus", source="enablebanking", household_id="hh_1")
    acc_csv = Account(uid="acc_csv", name="SparD Plus (Spiir)", source="csv", household_id="hh_1")
    session.add_all([acc_bank, acc_csv])
    session.commit()

    # Pre-existing CSV posting
    p_csv = Posting(
        id="csv:acc_csv:001",
        household_id="hh_1",
        account_uid="acc_csv",
        booking_date="2026-03-15",
        amount_minor=-5000,
        original_description="Gladsaxe Fysioterapi",
    )
    alloc_csv = PostingAllocation(
        id="alloc_c001",
        household_id="hh_1",
        posting_id=p_csv.id,
        category_id="sundhed|behandlinger",
        amount_minor=-5000,
    )
    session.add_all([p_csv, alloc_csv])
    session.commit()

    # Incoming bank posting
    p_bank = Posting(
        id="eb:acc_bank:001",
        household_id="hh_1",
        account_uid="acc_bank",
        booking_date="2026-03-15",
        amount_minor=-5000,
        original_description="Gladsaxe Fysioterapi",
    )
    alloc_bank = PostingAllocation(
        id="alloc_b001",
        household_id="hh_1",
        posting_id=p_bank.id,
        category_id="diverse|ikke-kategoriseret",
        amount_minor=-5000,
    )
    session.add_all([p_bank, alloc_bank])
    session.commit()

    summary = reconcile_incoming_postings(session, "hh_1", incoming_posting_ids=[p_bank.id])
    session.commit()

    assert summary["reconciled_count"] == 1
    assert session.get(Posting, p_csv.id) is None
    assert session.get(Posting, p_bank.id) is not None
    assert session.get(PostingAllocation, alloc_bank.id).category_id == "sundhed|behandlinger"

def test_merge_accounts(session: Session):
    hh = Household(id="hh_1", name="Test Household")
    session.add(hh)
    
    acc_src = Account(uid="acc_src", name="Old CSV Account", source="csv", household_id="hh_1")
    acc_tgt = Account(uid="acc_tgt", name="New Bank Account", source="enablebanking", household_id="hh_1")
    session.add_all([acc_src, acc_tgt])
    session.commit()

    # Add historical non-duplicate transaction to src
    p_old = Posting(
        id="csv:acc_src:old",
        household_id="hh_1",
        account_uid="acc_src",
        booking_date="2025-01-01",
        amount_minor=-10000,
        original_description="Old Transaction",
    )
    alloc_old = PostingAllocation(
        id="alloc_old",
        household_id="hh_1",
        posting_id=p_old.id,
        category_id="bolig|husleje",
        amount_minor=-10000,
    )
    session.add_all([p_old, alloc_old])
    session.commit()

    res = merge_accounts(session, "hh_1", source_account_uid="acc_src", target_account_uid="acc_tgt")

    assert res["success"] is True
    assert res["postings_migrated"] == 1
    assert session.get(Account, "acc_src") is None
    assert session.get(Posting, "csv:acc_src:old").account_uid == "acc_tgt"
