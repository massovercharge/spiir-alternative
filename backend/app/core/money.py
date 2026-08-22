"""Money utilities — safe integer-based monetary arithmetic.

All monetary values in Peng are stored as integers representing
the smallest unit of the currency (e.g. øre for DKK, cents for EUR/USD).
This module provides conversion helpers to move between the integer
representation and human-readable ``Decimal`` or ``str`` values.

This approach eliminates floating-point rounding errors that are
unacceptable in a financial application (e.g. ``0.1 + 0.2 != 0.3``).

Examples::

    >>> to_minor(Decimal("100.50"))
    10050
    >>> from_minor(10050)
    Decimal('100.50')
    >>> format_amount(10050, "DKK")
    '100.50'
"""
from __future__ import annotations

from decimal import ROUND_HALF_UP, Decimal, InvalidOperation


def to_minor(amount: Decimal | str) -> int:
    """Convert a Decimal (or string) amount to minor units (øre/cents).

    Args:
        amount: The amount as a Decimal or parseable string (e.g. "100.50").

    Returns:
        Integer minor units. ``Decimal("100.50")`` → ``10050``.

    Raises:
        ValueError: If the input cannot be parsed as a valid amount.
    """
    if isinstance(amount, str):
        amount = amount.strip()
        if not amount:
            raise ValueError("Empty string is not a valid amount")
        try:
            amount = Decimal(amount)
        except InvalidOperation as exc:
            raise ValueError(f"Cannot parse {amount!r} as a monetary amount") from exc

    if not isinstance(amount, Decimal):
        raise TypeError(f"Expected Decimal or str, got {type(amount).__name__}")

    return int((amount * 100).to_integral_value(rounding=ROUND_HALF_UP))


def from_minor(amount_minor: int) -> Decimal:
    """Convert minor units back to a Decimal with 2 decimal places.

    Args:
        amount_minor: Integer minor units (e.g. ``10050``).

    Returns:
        A Decimal with exactly 2 decimal places: ``Decimal('100.50')``.
    """
    return (Decimal(amount_minor) / 100).quantize(Decimal("0.01"), rounding=ROUND_HALF_UP)


def format_amount(amount_minor: int, currency: str = "DKK") -> str:
    """Format minor units as a human-readable string for API responses.

    The amount is always returned with exactly 2 decimal places,
    using a period as the decimal separator (locale-independent).

    Args:
        amount_minor: Integer minor units.
        currency: ISO 4217 currency code (for future multi-currency support).

    Returns:
        String representation, e.g. ``"100.50"`` or ``"-42.00"``.
    """
    return str(from_minor(amount_minor))


def float_to_minor(amount: float) -> int:
    """Convert a legacy float amount to minor units.

    This is a **migration helper** for converting existing V2 data
    where amounts are stored as floats. It should NOT be used for
    new code paths — use :func:`to_minor` with Decimal/str instead.

    Args:
        amount: A float amount (e.g. ``100.50``).

    Returns:
        Integer minor units.
    """
    return to_minor(Decimal(str(amount)))
