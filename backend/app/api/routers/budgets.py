from typing import Any, Optional

from fastapi import APIRouter

from app.schemas.requests import BudgetBillsUpsertRequest, BudgetUpsertRequest
from app.services.budget_service import (
    apply_budget_suggestions,
    generate_budget_suggestion,
    get_annual_summary,
    get_budget_bills,
    list_budgets,
    upsert_budget,
    upsert_budget_bills,
)

router = APIRouter(prefix="/api/budgets", tags=["budgets"])


@router.get("")
def budgets_list(
    year: int, month: Optional[int] = None, category_id: Optional[str] = None
) -> list[dict[str, Any]]:
    """List budgets for a given year and optional month/category."""
    return list_budgets(year, month, category_id)


@router.post("")
def budgets_upsert(payload: BudgetUpsertRequest) -> dict[str, Any]:
    """Create or update a budget."""
    return upsert_budget(
        category_id=payload.category_id,
        year=payload.year,
        month=payload.month,
        amount_minor=payload.amount_minor,
        budget_type=payload.budget_type,
        rollover=payload.rollover,
    )


@router.post("/generate")
def budgets_generate(months: int = 12, year: Optional[int] = None) -> list[dict[str, Any]]:
    """Auto-generate budget suggestions based on historical spending without persisting."""
    return generate_budget_suggestion(months, year)


@router.post("/apply-suggestions")
def budgets_apply_suggestions(months: int = 12, year: Optional[int] = None) -> dict[str, Any]:
    """Auto-generate and persist budget suggestions based on historical spending."""
    return apply_budget_suggestions(months=months, target_year=year)


@router.get("/bills/{category_id}/{year}")
def budgets_get_bills(category_id: str, year: int) -> list[dict[str, Any]]:
    """Get all specific bills for a budget category."""
    return get_budget_bills(category_id, year)


@router.post("/bills")
def budgets_upsert_bills(payload: BudgetBillsUpsertRequest) -> list[dict[str, Any]]:
    """Replace all specific bills for a category and recalculate its monthly budget."""
    bills_data = [b.model_dump() for b in payload.bills]
    return upsert_budget_bills(
        category_id=payload.category_id,
        year=payload.year,
        bills_data=bills_data,
    )


@router.get("/summary/{year}")
def budgets_summary(year: int) -> dict[str, Any]:
    """Get the annual summary of budgeted vs actual spending."""
    return get_annual_summary(year)
