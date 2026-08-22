"""Tests for money utilities — integer-based monetary arithmetic."""
from decimal import Decimal

import pytest

from app.core.money import float_to_minor, format_amount, from_minor, to_minor


class TestToMinor:
    """Test Decimal/str → int minor unit conversion."""

    def test_basic_conversion(self):
        assert to_minor(Decimal("100.50")) == 10050

    def test_whole_number(self):
        assert to_minor(Decimal("42")) == 4200

    def test_negative(self):
        assert to_minor(Decimal("-150.75")) == -15075

    def test_zero(self):
        assert to_minor(Decimal("0")) == 0
        assert to_minor(Decimal("0.00")) == 0

    def test_one_ore(self):
        assert to_minor(Decimal("0.01")) == 1

    def test_rounds_half_up(self):
        # 3 decimal places should round: 100.505 → 10051 (half-up)
        assert to_minor(Decimal("100.505")) == 10051
        assert to_minor(Decimal("100.504")) == 10050
        assert to_minor(Decimal("100.506")) == 10051

    def test_string_input(self):
        assert to_minor("100.50") == 10050
        assert to_minor("-42.00") == -4200

    def test_empty_string_raises(self):
        with pytest.raises(ValueError, match="Empty string"):
            to_minor("")

    def test_invalid_string_raises(self):
        with pytest.raises(ValueError, match="Cannot parse"):
            to_minor("not_a_number")

    def test_large_amount(self):
        # 1 million kroner
        assert to_minor(Decimal("1000000.00")) == 100000000

    def test_type_error(self):
        with pytest.raises(TypeError):
            to_minor(100.50)  # type: ignore[arg-type]


class TestFromMinor:
    """Test int minor units → Decimal conversion."""

    def test_basic_conversion(self):
        assert from_minor(10050) == Decimal("100.50")

    def test_zero(self):
        assert from_minor(0) == Decimal("0.00")

    def test_negative(self):
        assert from_minor(-15075) == Decimal("-150.75")

    def test_one_ore(self):
        assert from_minor(1) == Decimal("0.01")

    def test_always_two_decimals(self):
        result = from_minor(4200)
        assert str(result) == "42.00"

    def test_roundtrip(self):
        """to_minor and from_minor should roundtrip cleanly."""
        original = Decimal("1234.56")
        assert from_minor(to_minor(original)) == original

    def test_roundtrip_negative(self):
        original = Decimal("-999.99")
        assert from_minor(to_minor(original)) == original


class TestFormatAmount:
    """Test formatting for API responses."""

    def test_basic(self):
        assert format_amount(10050) == "100.50"

    def test_negative(self):
        assert format_amount(-4200) == "-42.00"

    def test_zero(self):
        assert format_amount(0) == "0.00"

    def test_one_ore(self):
        assert format_amount(1) == "0.01"


class TestFloatToMinor:
    """Test legacy float → minor conversion (migration helper)."""

    def test_basic(self):
        assert float_to_minor(100.50) == 10050

    def test_negative(self):
        assert float_to_minor(-150.0) == -15000

    def test_problematic_float(self):
        # 0.1 + 0.2 == 0.30000000000000004 in float
        # float_to_minor should handle this correctly via Decimal(str(...))
        val = 0.1 + 0.2
        assert float_to_minor(val) == 30

    def test_zero(self):
        assert float_to_minor(0.0) == 0
