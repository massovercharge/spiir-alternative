import io
import json
import zipfile
from unittest.mock import MagicMock, patch

import pytest
from fastapi.testclient import TestClient
from sqlmodel import Session

from app.main import create_app
from app.models import Household, HouseholdMember, User, all_models
from app.services.inbound_email_service import (
    extract_storebox_link,
    list_inbound_emails,
    process_inbound_email,
    resolve_household_by_token_or_recipient,
)


@pytest.fixture
def test_client():
    app = create_app()
    return TestClient(app)


def _make_dummy_storebox_zip() -> bytes:
    """Create a dummy in-memory ZIP file containing receipts.json."""
    sample_receipts = [
        {
            "receiptId": "receipt_test_101",
            "storeName": "Netto",
            "storeAddress": "Nørrebrogade 1, 2200 København",
            "purchaseDate": "2026-08-10T14:30:00Z",
            "totalPrice": "45.50",
            "currency": "DKK",
            "lines": [
                {"name": "ØKO MÆLK", "price": "14.50"},
                {"name": "RUGBRØD", "price": "21.00"},
                {"name": "RABAT", "price": "-5.00"},
                {"name": "PANT", "price": "15.00"},
            ],
        }
    ]
    buf = io.BytesIO()
    with zipfile.ZipFile(buf, "w") as z:
        z.writestr("receipts.json", json.dumps(sample_receipts))
    return buf.getvalue()


def test_extract_storebox_link():
    # 1. HTML button link with entities
    html_sample = """
    <html>
      <body>
        <p>Hej! Dine Storebox kvitteringer er klar til download.</p>
        <p><a href="https://storebox-export-production.s3.eu-west-1.amazonaws.com/exports/123.zip?X-Amz-Algorithm=AWS4-HMAC-SHA256&amp;X-Amz-Expires=3600">DOWNLOAD DATA</a></p>
      </body>
    </html>
    """
    extracted = extract_storebox_link(html_body=html_sample)
    assert extracted is not None
    assert "s3.eu-west-1.amazonaws.com" in extracted
    assert "&X-Amz-Expires=" in extracted  # Ensure &amp; is properly unescaped to &

    # 2. Plain text email
    text_sample = "Her er dit link til download af kvitteringer: https://app.storebox.com/download/export-999.zip."
    extracted_text = extract_storebox_link(text_body=text_sample)
    assert extracted_text == "https://app.storebox.com/download/export-999.zip"

    # 3. No links
    assert extract_storebox_link(text_body="Hej her er en mail uden links.") is None


def test_resolve_household():
    with Session(all_models.engine) as db:
        hh = Household(name="Familien Hansen", inbound_email_token="testtoken123")
        db.add(hh)
        db.commit()
        db.refresh(hh)
        hh_id = hh.id

    # Resolve by To header with plus-addressing
    matched = resolve_household_by_token_or_recipient(["receipts+testtoken123@inbound.peng.local"])
    assert matched is not None
    assert matched.id == hh_id

    # Resolve by token in text body (forwarded email)
    matched_body = resolve_household_by_token_or_recipient(
        ["my_email@gmail.com"],
        body_text="---------- Forwarded message ---------\nTo: receipts+testtoken123@inbound.peng.local",
    )
    assert matched_body is not None
    assert matched_body.id == hh_id


def test_process_inbound_email_success():
    with Session(all_models.engine) as db:
        hh = Household(name="Test Husstand", inbound_email_token="token_success_123")
        db.add(hh)
        db.commit()
        db.refresh(hh)
        hh_id = hh.id

    zip_bytes = _make_dummy_storebox_zip()

    mock_response = MagicMock()
    mock_response.status_code = 200
    mock_response.content = zip_bytes
    mock_response.raise_for_status = MagicMock()

    email_content = {
        "from": "no-reply@storebox.com",
        "to": "receipts+token_success_123@inbound.peng.local",
        "subject": "Dine kvitteringsdata fra Storebox",
        "html_body": '<p><a href="https://s3.amazonaws.com/storebox/receipts.zip">Download data</a></p>',
    }

    with patch("requests.get", return_value=mock_response):
        res = process_inbound_email(email_content, household_id=hh_id)

    assert res["success"] is True
    assert res["status"] == "success"
    assert res["deduplicated_receipt_count"] >= 1

    # Check history log in database
    with Session(all_models.engine) as db:
        logs = list_inbound_emails(hh_id)
        assert len(logs) == 1
        assert logs[0]["status"] == "success"
        assert logs[0]["sender"] == "no-reply@storebox.com"
        assert logs[0]["deduplicated_receipt_count"] >= 1


def test_process_inbound_email_no_link():
    with Session(all_models.engine) as db:
        hh = Household(name="Test Husstand No Link", inbound_email_token="token_nolink_123")
        db.add(hh)
        db.commit()
        db.refresh(hh)
        hh_id = hh.id

    email_content = {
        "from": "friend@example.com",
        "to": "receipts+token_nolink_123@inbound.peng.local",
        "subject": "Hej uden link",
        "text_body": "Her er bare en besked uden noget link.",
    }

    res = process_inbound_email(email_content, household_id=hh_id)
    assert res["success"] is False
    assert res["status"] == "no_link"

    with Session(all_models.engine) as db:
        logs = list_inbound_emails(hh_id)
        assert len(logs) == 1
        assert logs[0]["status"] == "no_link"
        assert "Ingen" in logs[0]["error_message"]


def test_process_inbound_email_download_failure():
    with Session(all_models.engine) as db:
        hh = Household(name="Test Husstand Failed Download", inbound_email_token="token_failed_123")
        db.add(hh)
        db.commit()
        db.refresh(hh)
        hh_id = hh.id

    email_content = {
        "from": "no-reply@storebox.com",
        "to": "receipts+token_failed_123@inbound.peng.local",
        "subject": "Storebox download",
        "text_body": "Download: https://s3.amazonaws.com/storebox/expired.zip",
    }

    with patch("requests.get", side_effect=Exception("403 Forbidden (Link expired)")):
        res = process_inbound_email(email_content, household_id=hh_id)

    assert res["success"] is False
    assert res["status"] == "failed"

    with Session(all_models.engine) as db:
        logs = list_inbound_emails(hh_id)
        assert len(logs) == 1
        assert logs[0]["status"] == "failed"
        assert "403" in logs[0]["error_message"]


def test_inbound_api_endpoints(test_client):
    with Session(all_models.engine) as db:
        user = User(logto_id="test_user_inbound", email="test@peng.dk", name="Tester")
        db.add(user)
        db.commit()
        db.refresh(user)

        hh = Household(name="API Husstand", inbound_email_token="apitoken123")
        db.add(hh)
        db.commit()
        db.refresh(hh)
        hh_id = hh.id
        hh_token = hh.inbound_email_token

        member = HouseholdMember(household_id=hh.id, user_id=user.id, role="owner")
        db.add(member)
        db.commit()

    # 1. Get Inbound Config
    res_cfg = test_client.get(f"/api/households/{hh_id}/inbound-config")
    assert res_cfg.status_code == 200
    cfg = res_cfg.json()
    assert "email_address" in cfg
    assert "apitoken123" in cfg["email_address"]

    # 2. Public Webhook simulation
    zip_bytes = _make_dummy_storebox_zip()
    mock_resp = MagicMock()
    mock_resp.status_code = 200
    mock_resp.content = zip_bytes
    mock_resp.raise_for_status = MagicMock()

    with patch("requests.get", return_value=mock_resp):
        res_webhook = test_client.post(
            f"/api/inbound/email/{hh_token}",
            json={
                "sender": "sender@test.dk",
                "subject": "Storebox Test",
                "html_body": '<a href="https://storebox.com/download/test.zip">Download</a>',
            },
        )
    assert res_webhook.status_code == 200
    assert res_webhook.json()["success"] is True

    # 3. Get Inbound History
    res_hist = test_client.get(f"/api/households/{hh_id}/inbound-emails")
    assert res_hist.status_code == 200
    history = res_hist.json()
    assert len(history) >= 1
    assert history[0]["status"] == "success"
    log_id = history[0]["id"]

    # 4. Delete Single Inbound Email
    res_del = test_client.delete(f"/api/households/{hh_id}/inbound-emails/{log_id}")
    assert res_del.status_code == 200
    assert res_del.json()["success"] is True

    # 5. Clear All Inbound Emails
    res_clear = test_client.delete(f"/api/households/{hh_id}/inbound-emails")
    assert res_clear.status_code == 200
    assert res_clear.json()["success"] is True


def test_merchant_matching_variations():
    from app.services.kvitteringer_service import _description_matches_merchant

    # Real-world REMA 1000 example with store location and card prefix
    desc1 = "REMA1000 TOMMERUP, TOMMERUP Notanr 15641"
    assert _description_matches_merchant(desc1, "REMA1000", "rema1000") is True
    assert _description_matches_merchant(desc1, "REMA 1000", "rema-1000") is True
    assert _description_matches_merchant(desc1, "REMA 1000 Tommerup", "rema-1000-tommerup") is True
    assert _description_matches_merchant(desc1, "REMA1000, Tallerupvej 18-20, 5690, Tommerup", "rema1000") is True

    # Netto, Føtex, Meny, Matas, Coop
    assert _description_matches_merchant("Dankort-nota NETTO 4321", "Netto", "netto") is True
    assert _description_matches_merchant("FOETEX VESTERBRO", "Føtex", "foetex") is True
    assert _description_matches_merchant("MENY RUNGSTED", "Meny", "meny") is True
    assert _description_matches_merchant("MATAS 1234 ODENSE", "Matas", "matas") is True
    assert _description_matches_merchant("COOP 365DISCOUNT KBH", "365discount", "coop") is True


def test_suggested_receipts_endpoint(test_client):
    import uuid

    from sqlmodel import Session, select

    import app.models as models
    from app.models.all_models import Account, Household, Posting

    with Session(models.all_models.engine) as db:
        hh = db.exec(select(Household)).first()
        if not hh:
            hh = Household(name="Test HH")
            db.add(hh)
            db.commit()
            db.refresh(hh)

        acc = Account(
            uid=str(uuid.uuid4()),
            household_id=hh.id,
            account_id="acc-001",
            iban="DK0000000000",
            name="Lønkonto",
            currency="DKK",
        )
        db.add(acc)
        db.commit()
        db.refresh(acc)

        posting = Posting(
            id=str(uuid.uuid4()),
            household_id=hh.id,
            account_uid=acc.uid,
            booking_date="2026-08-05",
            original_description="REMA1000 TOMMERUP, TOMMERUP Notanr 15641",
            amount_minor=-4295,
            currency="DKK",
        )
        db.add(posting)
        db.commit()
        db.refresh(posting)

    res = test_client.get(f"/api/transactions/{posting.id}/suggested-receipts")
    assert res.status_code == 200
    assert isinstance(res.json(), list)


