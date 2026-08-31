from typing import Any, Optional

from fastapi import APIRouter

from app.services.insights_service import (
    category_drilldown,
    get_averages,
    get_category_trends,
    income_expense_series,
    sunburst_data,
)

router = APIRouter(prefix="/api/insights", tags=["insights"])


@router.get("/income-expense-series")
def insights_income_expense(year: Optional[int] = None) -> dict[str, Any]:
    """Monthly income/expense aggregates for bar charts."""
    return income_expense_series(year)


@router.get("/sunburst")
def insights_sunburst(
    year: Optional[int] = None,
    month: Optional[int] = None,
    filter_type: Optional[str] = None,
    start_date: Optional[str] = None,
    end_date: Optional[str] = None,
) -> dict[str, Any]:
    """Hierarchical category data for sunburst/drilldown charts."""
    return sunburst_data(
        year=year, month=month, filter_type=filter_type, start_date=start_date, end_date=end_date
    )


@router.get("/averages")
def insights_averages(year: int) -> dict[str, Any]:
    """Get monthly averages for a year."""
    return get_averages(year)


@router.get("/category-drilldown")
def insights_category_drilldown(category_name: str, year: int) -> dict[str, Any]:
    """Get monthly drill-down data for a category."""
    return category_drilldown(category_name, year)


@router.get("/trends")
def insights_trends() -> list[dict[str, Any]]:
    """Trend data for income/expenses over time."""
    return get_category_trends()
