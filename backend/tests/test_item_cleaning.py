from sqlmodel import Session

from app.core.item_utils import clean_item_name, extract_quantity_and_clean_name
from app.models import (
    Account,
    Household,
    Posting,
    PostingAllocation,
    current_household_id,
    engine,
)
from app.services.insights_service import sunburst_data


def test_clean_item_name_standard_multipliers():
    assert clean_item_name("2 x DG SOLSIKKEBOLLER") == "DG SOLSIKKEBOLLER"
    assert clean_item_name("2 X DG SOLSIKKEBOLLER") == "DG SOLSIKKEBOLLER"
    assert clean_item_name("2x DG SOLSIKKEBOLLER") == "DG SOLSIKKEBOLLER"
    assert clean_item_name("2 x GULD 45+ ML") == "GULD 45+ ML"
    assert clean_item_name("2 x LB FULDKORNSBOLLER") == "LB FULDKORNSBOLLER"
    assert clean_item_name("4*SODAVAND") == "SODAVAND"
    assert clean_item_name("2 * LETMÆLK") == "LETMÆLK"
    assert clean_item_name("1,5 x VANDMELON") == "VANDMELON"
    assert clean_item_name("0.5 x GRÆSKAR") == "GRÆSKAR"


def test_clean_item_name_danish_units():
    assert clean_item_name("3 STK BANANER") == "BANANER"
    assert clean_item_name("3 stk. Øko Bananer") == "Øko Bananer"
    assert clean_item_name("2stk AGURK") == "AGURK"
    assert clean_item_name("2 PK GÆR") == "GÆR"
    assert clean_item_name("2pk GÆR") == "GÆR"
    assert clean_item_name("3 fl. RØDVIN") == "RØDVIN"
    assert clean_item_name("6 ds. COCA COLA") == "COCA COLA"
    assert clean_item_name("2 bdt. FORÅRSLØG") == "FORÅRSLØG"
    assert clean_item_name("2 pos. GULERØDDER") == "GULERØDDER"
    assert clean_item_name("2 ks. SODAVAND") == "SODAVAND"
    assert clean_item_name("2 stk. x GULD 45+ ML") == "GULD 45+ ML"


def test_clean_item_name_preserves_valid_products():
    assert clean_item_name("SANDWICH KLAP GOLDEN") == "SANDWICH KLAP GOLDEN"
    assert clean_item_name("LB CHIABOLLER") == "LB CHIABOLLER"
    assert clean_item_name("BONDEBRØD") == "BONDEBRØD"
    assert clean_item_name("2XL T-SHIRT") == "2XL T-SHIRT"
    assert clean_item_name("3XL SWEATER") == "3XL SWEATER"
    assert clean_item_name("3-STJERNET SALAMI") == "3-STJERNET SALAMI"
    assert clean_item_name("7-UP 0.5L") == "7-UP 0.5L"
    assert clean_item_name("4X4 OFFROAD") == "4X4 OFFROAD"
    assert clean_item_name("84% CHOKOLADE") == "84% CHOKOLADE"
    assert clean_item_name("1001 NAT THE") == "1001 NAT THE"
    assert clean_item_name("500G HAKKET OKSEKØD") == "500G HAKKET OKSEKØD"


def test_extract_quantity_and_clean_name():
    qty, name = extract_quantity_and_clean_name("2 x DG SOLSIKKEBOLLER")
    assert qty == 2.0
    assert name == "DG SOLSIKKEBOLLER"

    qty, name = extract_quantity_and_clean_name("3 stk. Øko Bananer")
    assert qty == 3.0
    assert name == "Øko Bananer"

    qty, name = extract_quantity_and_clean_name("1,5 x VANDMELON")
    assert qty == 1.5
    assert name == "VANDMELON"

    qty, name = extract_quantity_and_clean_name("BONDEBRØD")
    assert qty is None
    assert name == "BONDEBRØD"

    qty, name = extract_quantity_and_clean_name("2XL T-SHIRT")
    assert qty is None
    assert name == "2XL T-SHIRT"


def test_insights_sunburst_aggregates_cleaned_items():
    with Session(engine) as session:
        hh = Household(id="hh_item_test", name="Item Test HH")
        session.add(hh)
        session.commit()

        token = current_household_id.set("hh_item_test")
        try:
            acc = Account(
                id="acc_item_test",
                household_id="hh_item_test",
                name="Bank",
                account_type="Checking",
                balance_minor=0,
                currency="DKK",
                created_at="2026-08-01T00:00:00Z",
                updated_at="2026-08-01T00:00:00Z",
            )
            session.add(acc)
            session.commit()

            # Posting 1: bought "2 x GULD 45+ ML" for -14990 øre (149.90 kr)
            p1 = Posting(
                id="p_item_1",
                account_uid=acc.id,
                household_id=hh.id,
                booking_date="2026-08-10",
                original_description="Netto",
                amount_minor=-14990,
                created_at="2026-08-10T10:00:00Z",
            )
            session.add(p1)
            session.commit()

            a1 = PostingAllocation(
                posting_id=p1.id,
                household_id=hh.id,
                category_id="husholdning|dagligvarer",
                amount_minor=-14990,
                item_name="2 x GULD 45+ ML",
                created_at="2026-08-10T10:00:00Z",
                updated_at="2026-08-10T10:00:00Z",
            )
            session.add(a1)

            # Posting 2: bought "GULD 45+ ML" (1 qty) on another day for -14084 øre (140.84 kr)
            p2 = Posting(
                id="p_item_2",
                account_uid=acc.id,
                household_id=hh.id,
                booking_date="2026-08-15",
                original_description="Netto",
                amount_minor=-14084,
                created_at="2026-08-15T10:00:00Z",
            )
            session.add(p2)
            session.commit()

            a2 = PostingAllocation(
                posting_id=p2.id,
                household_id=hh.id,
                category_id="husholdning|dagligvarer",
                amount_minor=-14084,
                item_name="GULD 45+ ML",
                created_at="2026-08-15T10:00:00Z",
                updated_at="2026-08-15T10:00:00Z",
            )
            session.add(a2)
            session.commit()

            res = sunburst_data(year=2026, month=8)
            echarts_data = res.get("echarts_data", [])

            # Find Husholdning -> Dagligvarer
            husholdning = next((n for n in echarts_data if n["name"] == "Husholdning"), None)
            assert husholdning is not None, f"Husholdning not in {echarts_data}"

            dagligvarer = next((c for c in husholdning.get("children", []) if c["name"] == "Dagligvarer"), None)
            assert dagligvarer is not None, f"Dagligvarer not in {husholdning}"

            # In Dagligvarer children: there should be only ONE item child "GULD 45+ ML" with unified sum 290.74 kr
            items = dagligvarer.get("children", [])
            guld_items = [i for i in items if "GULD 45+ ML" in i["name"]]
            assert len(guld_items) == 1, f"Expected 1 GULD item, got: {items}"
            assert guld_items[0]["name"] == "GULD 45+ ML"
            assert guld_items[0]["value"] == 290.74

            # Verify flat labels list does not contain "2 x GULD 45+ ML"
            assert "2 x GULD 45+ ML" not in res["labels"]
            assert "GULD 45+ ML" in res["labels"]

        finally:
            current_household_id.reset(token)
