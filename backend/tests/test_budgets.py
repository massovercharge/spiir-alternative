"""Tests for budget services, suggestions and persistence."""
from sqlmodel import Session, select

from app.models import (
    Account,
    Budget,
    Category,
    Posting,
    PostingAllocation,
    engine,
)
from app.services.budget_service import (
    apply_budget_suggestions,
    generate_budget_suggestion,
)


def test_generate_budget_suggestion_has_no_side_effects():
    with Session(engine) as db:
        acc = Account(uid="acc_b1", name="Checking", source="bank")
        db.add(acc)
        cat = Category(
            id="dagligvarer|supermarked",
            main_name="Dagligvarer",
            sub_name="Supermarked",
            category_type="Expense",
            expense_type="Variable",
        )
        db.add(cat)
        # Create postings in recent months
        for i, month in enumerate(["2026-05", "2026-06", "2026-07"]):
            p = Posting(
                id=f"p_bg_{i}",
                account_uid="acc_b1",
                booking_date=f"{month}-15",
                amount_minor=-200000,
            )
            db.add(p)
            a = PostingAllocation(
                id=f"a_bg_{i}",
                posting_id=p.id,
                amount_minor=-200000,
                category_id=cat.id,
            )
            db.add(a)
        db.commit()

    # Call generate_budget_suggestion
    suggestions = generate_budget_suggestion(months=12, target_year=2026)
    assert len(suggestions) >= 1

    # Verify NO Budget records were added to DB
    with Session(engine) as db:
        budgets = db.exec(select(Budget)).all()
        assert len(budgets) == 0

    # Explicitly apply suggestions
    result = apply_budget_suggestions(suggestions=suggestions, target_year=2026)
    assert result["applied_count"] > 0

    # Verify Budget records now exist
    with Session(engine) as db:
        budgets = db.exec(select(Budget).where(Budget.year == 2026)).all()
        assert len(budgets) == result["applied_count"]
