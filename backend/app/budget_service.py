"""Budget service — manages monthly limits and bills per category.

Also provides auto-generation of budgets based on historical spending,
and annual summaries combining budgeted vs actual realized spending.
"""
from __future__ import annotations

import statistics
from datetime import UTC, datetime
from typing import Any

from sqlmodel import Session, select

from app.database import (
    Budget,
    BudgetBill,
    Category,
    Posting,
    PostingAllocation,
    engine,
)
from app.money import format_amount


def _utcnow_iso() -> str:
    return datetime.now(UTC).isoformat().replace("+00:00", "Z")


# ---------------------------------------------------------------------------
# CRUD
# ---------------------------------------------------------------------------

def upsert_budget(
    category_id: str,
    year: int,
    month: int,
    amount_minor: int,
    budget_type: str = "limit",
    rollover: bool = False,
) -> dict[str, Any]:
    """Create or update a budget for a specific category and month."""
    now = _utcnow_iso()
    with Session(engine) as db:
        budget = db.exec(
            select(Budget)
            .where(Budget.category_id == category_id)
            .where(Budget.year == year)
            .where(Budget.month == month)
        ).first()

        if budget:
            budget.amount_minor = amount_minor
            budget.budget_type = budget_type
            budget.rollover = rollover
            budget.updated_at = now
        else:
            budget = Budget(
                category_id=category_id,
                year=year,
                month=month,
                amount_minor=amount_minor,
                budget_type=budget_type,
                rollover=rollover,
                created_at=now,
                updated_at=now,
            )
            db.add(budget)

        db.commit()
        db.refresh(budget)

    return {
        "id": budget.id,
        "category_id": budget.category_id,
        "year": budget.year,
        "month": budget.month,
        "amount": format_amount(budget.amount_minor),
        "amount_minor": budget.amount_minor,
        "budget_type": budget.budget_type,
        "rollover": budget.rollover,
    }


def list_budgets(year: int, month: int | None = None, category_id: str | None = None) -> list[dict[str, Any]]:
    """List budgets for a given year (and optionally month and category)."""
    with Session(engine) as db:
        query = select(Budget).where(Budget.year == year)
        if month is not None:
            query = query.where(Budget.month == month)
        if category_id is not None:
            query = query.where(Budget.category_id == category_id)

        budgets = db.exec(query).all()

    return [
        {
            "id": b.id,
            "category_id": b.category_id,
            "year": b.year,
            "month": b.month,
            "amount": format_amount(b.amount_minor),
            "amount_minor": b.amount_minor,
            "budget_type": b.budget_type,
            "rollover": b.rollover,
        }
        for b in budgets
    ]


# ---------------------------------------------------------------------------
# Budget Bills
# ---------------------------------------------------------------------------

def get_budget_bills(category_id: str, year: int) -> list[dict[str, Any]]:
    """Get all specific bills for a category and year."""
    with Session(engine) as db:
        bills = db.exec(
            select(BudgetBill)
            .where(BudgetBill.category_id == category_id)
            .where(BudgetBill.year == year)
        ).all()

    return [
        {
            "id": b.id,
            "category_id": b.category_id,
            "year": b.year,
            "name": b.name,
            "amount_minor": b.amount_minor,
            "months": [int(m.strip()) for m in b.months.split(",") if m.strip()],
        }
        for b in bills
    ]


def upsert_budget_bills(category_id: str, year: int, bills_data: list[dict[str, Any]]) -> list[dict[str, Any]]:
    """Replace all bills for a category/year and recalculate monthly budget sums."""
    with Session(engine) as db:
        # 1. Delete existing bills for this category/year
        existing_bills = db.exec(
            select(BudgetBill)
            .where(BudgetBill.category_id == category_id)
            .where(BudgetBill.year == year)
        ).all()
        for b in existing_bills:
            db.delete(b)

        # 2. Insert new bills
        new_bills = []
        for bd in bills_data:
            months_str = ",".join(str(m) for m in bd.get("months", []))
            bill = BudgetBill(
                category_id=category_id,
                year=year,
                name=bd["name"],
                amount_minor=int(bd["amount_minor"]),
                months=months_str,
            )
            db.add(bill)
            new_bills.append(bill)

        db.commit()

        # 3. Recalculate monthly budget limits based on new bills
        # First, zero out existing budgets for this category/year
        existing_budgets = db.exec(
            select(Budget)
            .where(Budget.category_id == category_id)
            .where(Budget.year == year)
        ).all()

        budget_map = {b.month: b for b in existing_budgets}

        # Calculate sum per month
        month_sums = {m: 0 for m in range(1, 13)}
        for b in new_bills:
            months_list = [int(m.strip()) for m in b.months.split(",") if m.strip()]
            for m in months_list:
                if 1 <= m <= 12:
                    month_sums[m] += b.amount_minor

        now = _utcnow_iso()
        for m in range(1, 13):
            sum_minor = month_sums[m]
            if m in budget_map:
                # Update existing
                budget_map[m].amount_minor = sum_minor
                budget_map[m].budget_type = "bill"
                budget_map[m].updated_at = now
            else:
                # Create if > 0, or maybe create anyway so we have a record
                if sum_minor > 0 or new_bills:
                    db.add(Budget(
                        category_id=category_id,
                        year=year,
                        month=m,
                        amount_minor=sum_minor,
                        budget_type="bill",
                    ))

        db.commit()

    return get_budget_bills(category_id, year)


# ---------------------------------------------------------------------------
# Auto-Generation
# ---------------------------------------------------------------------------

def generate_budget_suggestion(months: int = 12, target_year: int | None = None) -> list[dict[str, Any]]:
    """Analyze historical spending and suggest budget limits.

    Looks at the last `months` of data (excluding current month).
    Classifies stable spending as 'bill' and variable as 'limit'.
    """
    with Session(engine) as db:
        # Only look at the last 12 months of data so we don't bring back ancient categories
        now = datetime.now(UTC)
        now.year - (1 if now.month >= 1 else 2) # simplified 1 year back
        cutoff_key = f"{now.year - 1}-{now.month:02d}-01"

        rows = db.exec(
            select(PostingAllocation, Posting)
            .join(Posting, PostingAllocation.posting_id == Posting.id)
            .where(Posting.is_excluded == False)  # noqa: E712
            .where(Posting.booking_date >= cutoff_key)
        ).all()

    # Group by category and month
    monthly_totals: dict[str, dict[str, int]] = {}
    for alloc, posting in rows:
        cat_id = alloc.category_id or "diverse|ikke-kategoriseret"
        month_key = posting.booking_date[:7] if posting.booking_date else "unknown"
        if month_key == "unknown":
            continue

        if cat_id not in monthly_totals:
            monthly_totals[cat_id] = {}

        # We only look at negative (expense) postings for budget limits,
        # but if we want to suggest income budgets, we handle both.
        # For simplicity, we just take the raw amount.
        monthly_totals[cat_id][month_key] = monthly_totals[cat_id].get(month_key, 0) + alloc.amount_minor

    current_month_key = _utcnow_iso()[:7]
    suggestions = []

    with Session(engine) as db:
        categories_dict = {c.id: c for c in db.exec(select(Category)).all()}

        if target_year is None:
            target_year = datetime.now(UTC).year

        for cat_id, month_data in monthly_totals.items():
            sorted_months = sorted(month_data.keys())
            historical_months = [m for m in sorted_months if m < current_month_key][-months:]

            if not historical_months:
                continue

            historical_values = [month_data[m] for m in historical_months]

            avg = statistics.mean(historical_values)
            stddev = statistics.stdev(historical_values) if len(historical_values) > 1 else 0
            cv = abs(stddev / avg) if avg != 0 else 0

            cat = categories_dict.get(cat_id)
            if not cat and "|" in cat_id:
                cat = categories_dict.get(cat_id.split("|")[0])

            is_fixed = cat.expense_type == "Fixed" if cat else (cv < 0.15)
            is_income = cat.category_type == "Income" if cat else (avg > 0)

            budget_type = "bill" if (is_fixed or is_income) else "limit"
            suggested_amount = int(round(avg / 5000) * 5000)

            suggestions.append({
                "category_id": cat_id,
                "suggested_amount_minor": suggested_amount,
                "suggested_amount": format_amount(suggested_amount),
                "budget_type": budget_type,
                "confidence": max(0.0, 1.0 - cv),
                "historical_average_minor": int(avg),
                "historical_stddev_minor": int(stddev),
                "is_fixed": is_fixed,
                "is_income": is_income,
            })

            target_months = list(range(1, 13))
            if is_fixed or is_income:
                historical_month_ints = {int(m[-2:]) for m in historical_months}
                if historical_month_ints:
                    target_months = list(historical_month_ints)

            for m in target_months:
                existing = db.exec(
                    select(Budget)
                    .where(Budget.category_id == cat_id)
                    .where(Budget.year == target_year)
                    .where(Budget.month == m)
                ).first()
                if not existing:
                    db.add(
                        Budget(
                            category_id=cat_id,
                            year=target_year,
                            month=m,
                            amount_minor=suggested_amount,
                            budget_type=budget_type,
                        )
                    )
        db.commit()

    return suggestions


# ---------------------------------------------------------------------------
# Annual Summary
# ---------------------------------------------------------------------------

def get_annual_summary(year: int) -> dict[str, Any]:
    """Combine budgets with realized spending for a full-year matrix."""
    with Session(engine) as db:
        # Fetch all budgets for the year
        budgets = db.exec(select(Budget).where(Budget.year == year)).all()

        # Fetch all allocations for the year
        start_date = f"{year}-01-01"
        end_date = f"{year}-12-31T23:59:59"

        rows = db.exec(
            select(PostingAllocation, Posting)
            .join(Posting, PostingAllocation.posting_id == Posting.id)
            .where(Posting.is_excluded == False)  # noqa: E712
            .where(Posting.booking_date >= start_date)
            .where(Posting.booking_date <= end_date)
        ).all()

    # Map budgets
    budget_map: dict[str, dict[int, int]] = {}
    for b in budgets:
        if b.category_id not in budget_map:
            budget_map[b.category_id] = {}
        budget_map[b.category_id][b.month] = b.amount_minor

    # Map actuals
    actual_map: dict[str, dict[int, int]] = {}
    for alloc, posting in rows:
        cat_id = alloc.category_id or "diverse|ikke-kategoriseret"
        if not posting.booking_date:
            continue
        try:
            month = int(posting.booking_date[5:7])
        except ValueError:
            continue

        if cat_id not in actual_map:
            actual_map[cat_id] = {}
        actual_map[cat_id][month] = actual_map[cat_id].get(month, 0) + alloc.amount_minor

    # Build matrix
    categories = set(budget_map.keys()) | set(actual_map.keys())
    matrix = []

    # Fetch category metadata
    with Session(engine) as db:
        category_objects = db.exec(select(Category)).all()
        cat_meta = {c.id: c for c in category_objects}
        main_meta = {}
        for c in category_objects:
            main_id = c.id.split("|")[0]
            if main_id not in main_meta:
                main_meta[main_id] = c

    for cat_id in sorted(categories):
        months_data = []
        for m in range(1, 13):
            budgeted = budget_map.get(cat_id, {}).get(m, 0)
            actual = actual_map.get(cat_id, {}).get(m, 0)
            months_data.append({
                "month": m,
                "budgeted_minor": budgeted,
                "actual_minor": actual,
                "budgeted": format_amount(budgeted),
                "actual": format_amount(actual),
            })

        meta = cat_meta.get(cat_id)
        if not meta and "|" not in cat_id:
            meta = main_meta.get(cat_id)

        matrix.append({
            "category_id": cat_id,
            "category_type": meta.category_type if meta else "Expense",
            "expense_type": meta.expense_type if meta else "Variable",
            "months": months_data,
            "total_budgeted_minor": sum(d["budgeted_minor"] for d in months_data),
            "total_actual_minor": sum(d["actual_minor"] for d in months_data),
        })

    return {
        "year": year,
        "categories": matrix,
    }
