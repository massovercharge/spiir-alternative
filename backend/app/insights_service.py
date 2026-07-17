"""Insights service — analytics, trends, and charts for postings.

Provides endpoints for income/expense time series, category sunbursts,
and statistical anomaly/trend detection.
"""
from __future__ import annotations

import statistics
from datetime import UTC, datetime
from typing import Any

from sqlmodel import Session, col, select

from app.database import Category, Posting, PostingAllocation, engine
from app.money import format_amount


def _utcnow_iso() -> str:
    return datetime.now(UTC).isoformat().replace("+00:00", "Z")


# ---------------------------------------------------------------------------
# Charts
# ---------------------------------------------------------------------------

def income_expense_series(year: int | None = None) -> dict[str, Any]:
    """Build monthly income/expense aggregates for charts."""
    with Session(engine) as db:
        stmt = (
            select(Posting, PostingAllocation, Category)
            .join(PostingAllocation, PostingAllocation.posting_id == Posting.id)
            .outerjoin(Category, PostingAllocation.category_id == Category.id)
            .where(Posting.is_excluded == False)  # noqa: E712
        )
        if year:
            stmt = stmt.where(Posting.booking_date.startswith(str(year)))

        stmt = stmt.order_by(col(Posting.booking_date).asc())
        rows = db.exec(stmt).all()

    months: dict[str, dict[str, int]] = {}
    for posting, alloc, category in rows:
        main_cat = category.main_name if category else "Diverse"
        if main_cat == "Vis ikke":
            continue

        month_key = posting.booking_date[:7] if posting.booking_date else "unknown"
        bucket = months.setdefault(month_key, {"income": 0, "expense_fixed": 0, "expense_variable": 0, "savings": 0})

        amt = alloc.amount_minor
        if amt >= 0:
            bucket["income"] += amt
        else:
            if main_cat == "Pension & Opsparing":
                bucket["savings"] += abs(amt)
            else:
                exp_type = category.expense_type if category else "Variable"
                if exp_type == "Fixed":
                    bucket["expense_fixed"] += abs(amt)
                else:
                    bucket["expense_variable"] += abs(amt)

    series = []
    for month, data in sorted(months.items()):
        total_expense = data["expense_fixed"] + data["expense_variable"]
        net = data["income"] - total_expense
        series.append({
            "month": month,
            "income": format_amount(data["income"]),
            "expense_fixed": format_amount(data["expense_fixed"]),
            "expense_variable": format_amount(data["expense_variable"]),
            "savings": format_amount(data["savings"]),
            "expense": format_amount(total_expense),
            "net": format_amount(net),
        })

    return {
        "generated_at": _utcnow_iso(),
        "series": series,
    }


def sunburst_data(year: int | None = None, month: int | None = None, filter_type: str | None = None, start_date: str | None = None, end_date: str | None = None) -> dict[str, Any]:
    """Build hierarchical sunburst chart data grouped by category, optionally filtered by month/year, date range, and expense_type."""
    from app.category_service import list_categories

    with Session(engine) as db:
        query = (
            select(Posting)
            .where(Posting.is_excluded == False)  # noqa: E712
        )
        if filter_type == "Income":
            query = query.where(Posting.amount_minor >= 0)
        else:
            query = query.where(Posting.amount_minor < 0)

        if start_date:
            query = query.where(Posting.booking_date >= start_date)
        if end_date:
            query = query.where(Posting.booking_date <= end_date)

        if year and not start_date and not end_date:
            query = query.where(Posting.booking_date.startswith(str(year)))
            if month:
                month_str = f"{month:02d}"
                query = query.where(Posting.booking_date.startswith(f"{year}-{month_str}"))

        postings = db.exec(query).all()

        posting_ids = [p.id for p in postings]
        allocs: list[PostingAllocation] = []
        if posting_ids:
            allocs = list(db.exec(
                select(PostingAllocation).where(
                    PostingAllocation.posting_id.in_(posting_ids)  # type: ignore[union-attr]
                )
            ).all())

    # Map posting_id to list of allocations
    allocs_by_posting: dict[str, list[PostingAllocation]] = {}
    for alloc in allocs:
        if alloc.posting_id not in allocs_by_posting:
            allocs_by_posting[alloc.posting_id] = []
        allocs_by_posting[alloc.posting_id].append(alloc)

    categories = {cat["id"]: cat for cat in list_categories()}

    # totals grouped by (cat_id, item_name)
    totals: dict[tuple[str, str | None], int] = {}
    
    for p in postings:
        p_allocs = allocs_by_posting.get(p.id, [])
        if not p_allocs:
            cat_id = "diverse|ikke-kategoriseret"
            cat = categories.get(cat_id) or {"mainCategoryName": "Diverse", "categoryName": "Ukendt", "expenseType": "Variable", "categoryType": "Expense"}
            if cat["mainCategoryName"] == "Vis ikke":
                continue
            if filter_type:
                if (filter_type == "Income" and cat.get("categoryType") != "Income") or (filter_type in ["Fixed", "Variable"] and cat.get("expenseType", "Variable") != filter_type):
                    continue
            key = (cat_id, None)
            totals[key] = totals.get(key, 0) + abs(p.amount_minor)
        else:
            for alloc in p_allocs:
                cat_id = alloc.category_id or "diverse|ikke-kategoriseret"
                cat = categories.get(cat_id) or {"mainCategoryName": "Diverse", "categoryName": "Ukendt", "expenseType": "Variable", "categoryType": "Expense"}
                if cat["mainCategoryName"] == "Vis ikke":
                    continue
                if filter_type:
                    if (filter_type == "Income" and cat.get("categoryType") != "Income") or (filter_type in ["Fixed", "Variable"] and cat.get("expenseType", "Variable") != filter_type):
                        continue
                item_name = alloc.item_name
                # If item_name has a category, we might want to capitalize it nicely or just use it
                key = (cat_id, item_name)
                totals[key] = totals.get(key, 0) + abs(alloc.amount_minor)

    # Build flat arrays for Plotly or custom frontend lists
    labels = ["Total"]
    parents = [""]
    values = [0.0]
    seen_mains: set[str] = set()
    seen_subs: set[str] = set()

    # Pre-calculate category totals and main totals since we split by item now
    main_totals: dict[str, float] = {}
    sub_totals: dict[str, float] = {}
    
    for (cat_id, item_name), total in totals.items():
        if total == 0: continue
        cat = categories.get(cat_id) or {"mainCategoryName": "Diverse", "categoryName": "Ukendt"}
        main = cat["mainCategoryName"]
        sub = cat.get("categoryName", cat_id)
        
        main_totals[main] = main_totals.get(main, 0.0) + total
        sub_totals[sub] = sub_totals.get(sub, 0.0) + total

    # First add all mains
    for main, m_total in sorted(main_totals.items(), key=lambda x: -x[1]):
        labels.append(main)
        parents.append("Total")
        values.append(m_total)
        values[0] += m_total

    # Then add all subs
    for sub, s_total in sorted(sub_totals.items(), key=lambda x: -x[1]):
        # Find its main
        main = next((categories.get(cid, {}).get("mainCategoryName", "Diverse") 
                    for (cid, itm), t in totals.items() 
                    if categories.get(cid, {}).get("categoryName", cid) == sub), "Diverse")
        labels.append(sub)
        parents.append(main)
        values.append(s_total)

    # Then add all items
    for (cat_id, item_name), total in sorted(totals.items(), key=lambda x: -x[1]):
        if not item_name or total == 0: continue
        cat = categories.get(cat_id) or {"mainCategoryName": "Diverse", "categoryName": "Ukendt"}
        sub = cat.get("categoryName", cat_id)
        
        # We need a unique label if multiple subs have same item_name, but echarts doesn't strictly need it. 
        # Plotly might require unique labels. We'll append space if needed, or just keep it simple.
        labels.append(item_name)
        parents.append(sub)
        values.append(total)

    # Build ECharts hierarchical format (use floats: minor units / 100)
    echarts_tree: list[dict[str, Any]] = []
    main_nodes: dict[str, dict[str, Any]] = {}
    sub_nodes: dict[tuple[str, str], dict[str, Any]] = {}

    for (cat_id, item_name), total in sorted(totals.items(), key=lambda x: -x[1]):
        if total == 0:
            continue
        cat = categories.get(cat_id) or {"mainCategoryName": "Diverse", "categoryName": "Ukendt"}
        main = cat["mainCategoryName"]
        sub = cat.get("categoryName", cat_id)
        amount = round(total / 100, 2)

        if main not in main_nodes:
            main_nodes[main] = {"name": main, "value": 0.0, "children": []}
            echarts_tree.append(main_nodes[main])

        main_nodes[main]["value"] = round(main_nodes[main]["value"] + amount, 2)
        
        sub_key = (main, sub)
        if sub_key not in sub_nodes:
            sub_node = {"name": sub, "value": 0.0}
            # Only add children array if we actually have item-level data, to avoid breaking chart layout for categories without items
            sub_nodes[sub_key] = sub_node
            main_nodes[main]["children"].append(sub_node)
            
        sub_nodes[sub_key]["value"] = round(sub_nodes[sub_key]["value"] + amount, 2)
        
        if item_name:
            if "children" not in sub_nodes[sub_key]:
                # Convert this sub_node to have children instead of just a value. 
                # Echarts allows nodes to have both 'value' and 'children' where the value is the sum.
                sub_nodes[sub_key]["children"] = []
                
            # Check if this item_name already exists under this sub_category (e.g. "Mælk" across multiple transactions)
            existing_item = next((child for child in sub_nodes[sub_key]["children"] if child["name"] == item_name), None)
            if existing_item:
                existing_item["value"] = round(existing_item["value"] + amount, 2)
            else:
                sub_nodes[sub_key]["children"].append({"name": item_name, "value": amount})

    return {
        "labels": labels,
        "parents": parents,
        "values": [format_amount(v) for v in values],
        "echarts_data": echarts_tree,
    }

def get_averages(year: int) -> dict[str, Any]:
    """Calculate average monthly income, fixed expenses, variable expenses and net result for the given year."""
    data = income_expense_series(year)
    series = data.get("series", [])

    if not series:
        return {
            "income_avg": "0.00",
            "expense_fixed_avg": "0.00",
            "expense_variable_avg": "0.00",
            "savings_avg": "0.00",
            "net_avg": "0.00",
            "income_total": "0.00",
            "expense_fixed_total": "0.00",
            "expense_variable_total": "0.00",
            "savings_total": "0.00",
            "net_total": "0.00",
            "months_counted": 0
        }

    months_counted = len(series)

    total_income = sum(float(item["income"]) for item in series)
    total_fixed = sum(float(item["expense_fixed"]) for item in series)
    total_variable = sum(float(item["expense_variable"]) for item in series)
    total_savings = sum(float(item.get("savings", 0)) for item in series)
    total_net = sum(float(item["net"]) for item in series)

    return {
        "income_avg": format_amount(int((total_income / months_counted) * 100)),
        "expense_fixed_avg": format_amount(int((total_fixed / months_counted) * 100)),
        "expense_variable_avg": format_amount(int((total_variable / months_counted) * 100)),
        "savings_avg": format_amount(int((total_savings / months_counted) * 100)),
        "net_avg": format_amount(int((total_net / months_counted) * 100)),
        "income_total": format_amount(int(total_income * 100)),
        "expense_fixed_total": format_amount(int(total_fixed * 100)),
        "expense_variable_total": format_amount(int(total_variable * 100)),
        "savings_total": format_amount(int(total_savings * 100)),
        "net_total": format_amount(int(total_net * 100)),
        "months_counted": months_counted
    }


# ---------------------------------------------------------------------------
# Trends & Anomalies
# ---------------------------------------------------------------------------

def get_category_trends() -> list[dict[str, Any]]:
    """Calculate moving averages, stddev, and detect anomalies per category.

    Categories with less than 2 months of history are skipped for anomaly detection.
    Amounts are returned as integers in minor units.
    """
    with Session(engine) as db:
        # Fetch all allocations and join with their postings
        rows = db.exec(
            select(PostingAllocation, Posting)
            .join(Posting, PostingAllocation.posting_id == Posting.id)
            .where(Posting.is_excluded == False)  # noqa: E712
            .where(PostingAllocation.amount_minor < 0)  # Only expenses
        ).all()

    # Group spending by category and month
    monthly_cat_totals: dict[str, dict[str, int]] = {}
    for alloc, posting in rows:
        cat_id = alloc.category_id or "diverse|ikke-kategoriseret"
        month_key = posting.booking_date[:7] if posting.booking_date else "unknown"
        if month_key == "unknown":
            continue

        if cat_id not in monthly_cat_totals:
            monthly_cat_totals[cat_id] = {}

        # Add amount (store as absolute positive value for expense analysis)
        monthly_cat_totals[cat_id][month_key] = monthly_cat_totals[cat_id].get(month_key, 0) + abs(alloc.amount_minor)

    current_month_key = _utcnow_iso()[:7]
    trends = []

    for cat_id, month_data in monthly_cat_totals.items():
        # Sort months chronologically
        sorted_months = sorted(month_data.keys())
        if not sorted_months:
            continue

        # We need historical data to calculate stddev and moving average.
        # Exclude the current month from historical calculations if it exists.
        historical_months = [m for m in sorted_months if m < current_month_key]
        historical_values = [month_data[m] for m in historical_months]

        current_month_val = month_data.get(current_month_key, 0)

        # Sparkline data (last 12 months)
        sparkline = [{"month": m, "amount_minor": month_data[m]} for m in sorted_months[-12:]]

        # If we have very little history, we can't do meaningful stddev
        if len(historical_values) < 2:
            trends.append({
                "category_id": cat_id,
                "current_month_amount_minor": current_month_val,
                "moving_average_minor": historical_values[-1] if historical_values else 0,
                "historical_stddev_minor": 0,
                "trend_direction": "stable",
                "trend_slope_per_month_minor": 0,
                "is_anomaly": False,
                "anomaly_severity": None,
                "monthly_history": sparkline,
            })
            continue

        avg = statistics.mean(historical_values)
        stddev = statistics.stdev(historical_values)

        # 3-month moving average
        recent_3 = historical_values[-3:]
        moving_avg = int(statistics.mean(recent_3))

        # Linear regression slope over last 6 historical months
        recent_6 = historical_values[-6:]
        if len(recent_6) > 1:
            x_vals = list(range(len(recent_6)))
            x_mean = statistics.mean(x_vals)
            y_mean = statistics.mean(recent_6)
            numerator = sum((x - x_mean) * (y - y_mean) for x, y in zip(x_vals, recent_6, strict=False))
            denominator = sum((x - x_mean)**2 for x in x_vals)
            slope = numerator / denominator if denominator != 0 else 0
        else:
            slope = 0

        if slope > abs(avg) * 0.05:
            direction = "rising"
        elif slope < -abs(avg) * 0.05:
            direction = "falling"
        else:
            direction = "stable"

        # Anomaly detection: > 1.5 sigma
        is_anomaly = False
        severity = None
        if current_month_val > 0 and stddev > 0:
            sigma_diff = (current_month_val - avg) / stddev
            if sigma_diff > 1.5:
                is_anomaly = True
                severity = round(sigma_diff, 2)

        trends.append({
            "category_id": cat_id,
            "current_month_amount_minor": current_month_val,
            "moving_average_minor": moving_avg,
            "historical_stddev_minor": int(stddev),
            "trend_direction": direction,
            "trend_slope_per_month_minor": int(slope),
            "is_anomaly": is_anomaly,
            "anomaly_severity": severity,
            "monthly_history": sparkline,
        })

    # Sort so anomalies and high spenders are at the top
    trends.sort(key=lambda t: (not t["is_anomaly"], -t["current_month_amount_minor"]))
    return trends

def category_drilldown(category_name: str, year: int) -> dict[str, Any]:
    """Get monthly trends and top transactions for a specific category name (main or sub)."""
    from app.category_service import list_categories

    # 1. Find all matching category IDs
    categories = list_categories()
    matching_ids = []

    for cat in categories:
        if cat["mainCategoryName"] == category_name or cat.get("categoryName") == category_name:
            matching_ids.append(cat["id"])

    if not matching_ids:
        # If it doesn't match anything, maybe it's the raw ID?
        matching_ids.append(category_name)

    with Session(engine) as db:
        query = (
            select(PostingAllocation, Posting)
            .join(Posting, PostingAllocation.posting_id == Posting.id)
            .where(Posting.is_excluded == False)  # noqa: E712
            .where(Posting.booking_date.startswith(str(year)))
            .where(PostingAllocation.category_id.in_(matching_ids))
        )

        rows = db.exec(query).all()

    # Group by month
    months_data = {}

    for i in range(1, 13):
        month_str = f"{year}-{i:02d}"
        months_data[month_str] = {
            "month": month_str,
            "total_amount_minor": 0,
            "transactions": []
        }

    for alloc, posting in rows:
        month_str = posting.booking_date[:7] if posting.booking_date else f"{year}-01"
        if month_str not in months_data:
            continue

        amount = alloc.amount_minor
        months_data[month_str]["total_amount_minor"] += amount
        months_data[month_str]["transactions"].append({
            "date": posting.booking_date,
            "payee": posting.original_description,
            "amount_minor": amount,
        })

    monthly_results = []
    for month_str, data in sorted(months_data.items()):
        # Sort transactions by absolute amount descending, take top 3
        top_tx = sorted(data["transactions"], key=lambda x: -abs(x["amount_minor"]))[:3]
        monthly_results.append({
            "month": month_str,
            "total_amount_minor": data["total_amount_minor"],
            "top_transactions": top_tx
        })

    return {
        "category_name": category_name,
        "year": year,
        "monthly_data": monthly_results
    }
