import json

import pytest

from app.services.coop_service import process_coop_file, validate_coop_json
from app.services.kvitteringer_service import (
    get_kvitteringer_status,
    link_peng_transaction_to_receipt,
)
from app.services.storebox_service import process_storebox_file


@pytest.fixture
def sample_coop_json_bytes():
    receipts = [
        {
            "receiptId": "260713009488880242",
            "storeName": "Kvickly Buddinge",
            "purchaseDate": "2026-07-13",
            "purchaseDateTime": "2026-07-13T14:30:00Z",
            "totalPrice": "192.55",
            "totalAmountMinor": 19255,
            "currency": "DKK",
            "lines": [
                {
                    "name": "2 x WASA KNÆKBRØD",
                    "price": "53.90",
                    "priceMinor": 5390,
                    "quantity": 2,
                },
                {
                    "name": "Rabat",
                    "price": "-8.95",
                    "priceMinor": -895,
                },
                {
                    "name": "ØKO DANBO",
                    "price": "64.95",
                    "priceMinor": 6495,
                    "quantity": 1,
                },
                {
                    "name": "2 x TEMPTY SQUARE",
                    "price": "59.90",
                    "priceMinor": 5990,
                    "quantity": 2,
                },
                {
                    "name": "ØKO SALSA 300 G",
                    "price": "17.95",
                    "priceMinor": 1795,
                    "quantity": 1,
                },
                {
                    "name": "ØKO TORTILLA 240 G",
                    "price": "13.75",
                    "priceMinor": 1375,
                    "quantity": 1,
                },
                {
                    "name": "Rabat",
                    "price": "-8.95",
                    "priceMinor": -895,
                },
            ],
        },
        {
            "receiptId": "260705252088880072",
            "storeName": "365discount Buddinge",
            "purchaseDate": "2026-07-05",
            "purchaseDateTime": "2026-07-05T10:15:00Z",
            "totalPrice": "34.50",
            "totalAmountMinor": 3450,
            "currency": "DKK",
            "lines": [
                {
                    "name": "ØKO COURGETTE",
                    "price": "8.50",
                    "priceMinor": 850,
                },
                {
                    "name": "DANSKE AUBERGINE",
                    "price": "10.00",
                    "priceMinor": 1000,
                },
                {
                    "name": "ØKO BRUNE CHAMPIGNON",
                    "price": "17.50",
                    "priceMinor": 1750,
                },
                {
                    "name": "Rabat",
                    "price": "-1.50",
                    "priceMinor": -150,
                },
            ],
        },
    ]
    return json.dumps(receipts).encode("utf-8")


@pytest.fixture
def sample_storebox_json_bytes():
    receipts = [
        {
            "id": "storebox-netto-12345",
            "merchant": {"name": "Netto Buddinge", "id": 101},
            "purchaseDate": "2026-07-10T12:00:00Z",
            "total": 50.0,
            "currency": "DKK",
            "receiptLines": [
                {"name": "MÆLK", "price": 15.0},
                {"name": "BRØD", "price": 35.0},
            ],
        }
    ]
    return json.dumps(receipts).encode("utf-8")


def test_validate_coop_json_valid(sample_coop_json_bytes):
    data = validate_coop_json(sample_coop_json_bytes)
    assert len(data) == 2
    assert data[0]["receiptId"] == "260713009488880242"


def test_validate_coop_json_invalid():
    with pytest.raises(ValueError, match="empty"):
        validate_coop_json(b"")

    with pytest.raises(ValueError, match="Invalid JSON"):
        validate_coop_json(b"not json")

    with pytest.raises(ValueError, match="JSON array"):
        validate_coop_json(b'{"key": "value"}')

    with pytest.raises(ValueError, match="missing 'receiptId'"):
        validate_coop_json(b'[{"purchaseDate": "2026-07-13", "lines": []}]')


def test_process_coop_file_import(sample_coop_json_bytes, tmp_path, monkeypatch):
    source_dir = tmp_path / "storebox_source"
    db_path = tmp_path / "kvitteringer.db"

    monkeypatch.setattr(
        "app.services.kvitteringer_service.get_storebox_source_dir", lambda: source_dir
    )
    monkeypatch.setattr(
        "app.services.kvitteringer_service.get_kvitteringer_db_path", lambda: db_path
    )

    result = process_coop_file(sample_coop_json_bytes, "coop-receipts.json")

    assert result["deduplicated_receipt_count"] == 2
    assert result["uploaded_source_file"] == "receipts-coop.json"

    status = get_kvitteringer_status()
    assert status["database_exists"] is True
    assert status["receipt_count"] == 2
    assert status["merchant_count"] == 2


def test_multi_source_coexistence(
    sample_coop_json_bytes, sample_storebox_json_bytes, tmp_path, monkeypatch
):
    source_dir = tmp_path / "storebox_source"
    db_path = tmp_path / "kvitteringer.db"

    monkeypatch.setattr(
        "app.services.kvitteringer_service.get_storebox_source_dir", lambda: source_dir
    )
    monkeypatch.setattr(
        "app.services.kvitteringer_service.get_kvitteringer_db_path", lambda: db_path
    )

    # 1. Upload Coop receipts
    process_coop_file(sample_coop_json_bytes, "coop-receipts.json")
    status1 = get_kvitteringer_status()
    assert status1["receipt_count"] == 2
    assert (source_dir / "receipts-coop.json").exists()

    # 2. Upload Storebox receipts
    process_storebox_file(sample_storebox_json_bytes, "receipts.json")
    status2 = get_kvitteringer_status()
    # Both files must coexist and total 3 receipts
    assert (source_dir / "receipts-coop.json").exists()
    assert (source_dir / "receipts-upload.json").exists()
    assert status2["receipt_count"] == 3


def test_coop_transaction_linking(sample_coop_json_bytes, tmp_path, monkeypatch):
    source_dir = tmp_path / "storebox_source"
    db_path = tmp_path / "kvitteringer.db"

    monkeypatch.setattr(
        "app.services.kvitteringer_service.get_storebox_source_dir", lambda: source_dir
    )
    monkeypatch.setattr(
        "app.services.kvitteringer_service.get_kvitteringer_db_path", lambda: db_path
    )

    process_coop_file(sample_coop_json_bytes)

    # Match Kvickly purchase: 192.55 DKK (19255 øre)
    tx_payload = {
        "transaction_id": "tx-coop-1",
        "date": "2026-07-13",
        "amount": -192.55,
        "description": "Dankort-køb Kvickly Buddinge",
    }
    link_result = link_peng_transaction_to_receipt(tx_payload)
    assert link_result["linked"] is True
    assert link_result["receipt_id"] == "260713009488880242"
    assert link_result["confidence"] == "high"

    # Match 365discount purchase: 34.50 DKK
    tx_payload_365 = {
        "transaction_id": "tx-coop-2",
        "date": "2026-07-05",
        "amount": -34.50,
        "description": "365discount Buddinge",
    }
    link_result_365 = link_peng_transaction_to_receipt(tx_payload_365)
    assert link_result_365["linked"] is True
    assert link_result_365["receipt_id"] == "260705252088880072"


def test_inbound_coop_webhook(sample_coop_json_bytes, tmp_path, monkeypatch):
    from fastapi.testclient import TestClient
    from sqlmodel import Session

    import app.models as models
    from app.main import app
    from app.models import Household

    source_dir = tmp_path / "storebox_source"
    db_path = tmp_path / "kvitteringer.db"

    monkeypatch.setattr(
        "app.services.kvitteringer_service.get_storebox_source_dir", lambda: source_dir
    )
    monkeypatch.setattr(
        "app.services.kvitteringer_service.get_kvitteringer_db_path", lambda: db_path
    )

    with Session(models.engine) as db:
        hh = Household(name="Test Household", inbound_email_token="test_token_123")
        db.add(hh)
        db.commit()
        db.refresh(hh)

    client = TestClient(app)
    receipts_data = json.loads(sample_coop_json_bytes.decode("utf-8"))

    # Test with valid token
    res = client.post("/api/inbound/coop/test_token_123", json=receipts_data)
    assert res.status_code == 200
    data = res.json()
    assert data["raw_receipt_count"] == 2
    assert data["deduplicated_receipt_count"] == 2

    # Test with invalid token
    res_bad = client.post("/api/inbound/coop/invalid_token_999", json=receipts_data)
    assert res_bad.status_code == 404

