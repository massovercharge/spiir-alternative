# ADR-0001: Store monetary values as integer minor units

## Status
Accepted

## Context
The original V2 codebase stored monetary amounts as `float` (e.g. `amount: float = -150.0`). Floating-point arithmetic introduces rounding errors that are unacceptable in a financial application (`0.1 + 0.2 != 0.3`).

We needed a reliable, simple approach to monetary storage that:
- Eliminates floating-point rounding errors completely
- Works across SQLite and PostgreSQL without precision loss
- Is easy to reason about in Python, SQL, and JavaScript
- Supports multi-currency amounts

## Decision
All monetary values are stored as **integers representing the smallest unit of the currency** (øre for DKK, cents for EUR/USD). We call this "minor units."

| Layer | Type | Example |
|-------|------|---------|
| **Database** | `INTEGER` | `10050` = 100,50 kr |
| **Python (model)** | `int` | `amount_minor: int = 10050` |
| **Python (calculation)** | `Decimal` | `Decimal("100.50")` |
| **API (JSON)** | `string` | `"100.50"` |
| **Frontend (display)** | `Intl.NumberFormat` | `100,50 kr.` |

Conversion helpers are provided in `app/money.py`:
- `to_minor(Decimal) → int`
- `from_minor(int) → Decimal`
- `format_amount(int) → str`
- `float_to_minor(float) → int` (migration only)

## Consequences
- **Positive:** Zero rounding errors, safe aggregation in SQL (`SUM(amount_minor)`), no need for `DECIMAL` column types
- **Positive:** Simple integer arithmetic for comparisons and budgeting
- **Negative:** Frontend must convert minor units to display format (handled by `Intl.NumberFormat`)
- **Negative:** Migration required from V2 `float` data (handled by `float_to_minor()`)
- **Note:** Currency must always be stored alongside the amount — never assume DKK
