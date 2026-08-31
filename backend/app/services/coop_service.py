from __future__ import annotations

import json
from typing import Any

from .kvitteringer_service import replace_coop_upload


def validate_coop_json(content: bytes, filename: str | None = None) -> list[dict[str, Any]]:
    """Validates that uploaded Coop JSON contains a valid receipt list."""
    if not content:
        raise ValueError("Uploaded Coop JSON is empty.")

    try:
        payload = json.loads(content.decode("utf-8"))
    except (json.JSONDecodeError, UnicodeDecodeError) as e:
        raise ValueError(f"Invalid JSON format in Coop export: {e}") from e

    if not isinstance(payload, list):
        raise ValueError("Invalid format: expected a JSON array of receipts.")

    if not payload:
        raise ValueError("Coop JSON array contains 0 receipts.")

    for idx, receipt in enumerate(payload):
        if not isinstance(receipt, dict):
            raise ValueError(f"Receipt at index {idx} is not an object.")

        receipt_id = receipt.get("receiptId") or receipt.get("id")
        if not receipt_id:
            raise ValueError(f"Receipt at index {idx} is missing 'receiptId'.")

        purchase_date = receipt.get("purchaseDate") or receipt.get("purchaseDateTime")
        if not purchase_date:
            raise ValueError(f"Receipt '{receipt_id}' is missing 'purchaseDate'.")

        lines = receipt.get("lines") or receipt.get("receiptLines") or receipt.get("items")
        if not isinstance(lines, list):
            raise ValueError(f"Receipt '{receipt_id}' is missing 'lines' array.")

    return payload


def process_coop_file(content: bytes, filename: str | None = None) -> dict[str, object]:
    """Processes an uploaded Coop JSON export and imports it into Peng's receipt engine."""
    validate_coop_json(content, filename)
    return replace_coop_upload(content, filename or "receipts-coop.json")
