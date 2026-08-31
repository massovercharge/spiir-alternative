from app.services.kvitteringer_service import _description_matches_merchant


def test_coop_mobilepay_and_alias_matching():
    """Verify that Coop sub-chains match MobilePay NOTPROVIDED, Coop App, and Nota formats."""
    # 1. 365discount, Kvickly, Brugsen matching MobilePay NOTPROVIDED
    assert _description_matches_merchant(
        "MobilePay køb NOTPROVIDED", "365discount Buddinge", "365discount-buddinge"
    ) is True
    assert _description_matches_merchant(
        "MobilePay køb NOTPROVIDED", "Kvickly Buddinge", "kvickly-buddinge"
    ) is True
    assert _description_matches_merchant(
        "MobilePay køb NOTPROVIDED", "SuperBrugsen Ringkøbing", "superbrugsen-ringk-bing"
    ) is True
    assert _description_matches_merchant(
        "MobilePay køb NOTPROVIDED", "Brugsen Sorgenfri Torv", "brugsen-sorgenfri-torv"
    ) is True
    assert _description_matches_merchant(
        "MobilePay køb NOTPROVIDED", "Ukendt butik", "ukendt-butik"
    ) is True

    # 2. Coop App & Nota variants
    assert _description_matches_merchant(
        "MobilePay køb Coop App", "365discount Buddinge", "365discount-buddinge"
    ) is True
    assert _description_matches_merchant(
        "MobilePay køb Coop App", "Ukendt butik", "ukendt-butik"
    ) is True
    assert _description_matches_merchant(
        "Dankort-køb Coop App Nota 0890C5YI2D", "Brugsen Sorgenfri Torv", "brugsen-sorgenfri-torv"
    ) is True
    assert _description_matches_merchant(
        "Dankort-køb Coop App Nota 1580CG56T2", "Kvickly Buddinge", "kvickly-buddinge"
    ) is True

    # 3. Non-Coop merchants should NOT match NOTPROVIDED or Coop App
    assert _description_matches_merchant(
        "MobilePay køb NOTPROVIDED", "IKEA Taastrup", "ikea-taastrup"
    ) is False
    assert _description_matches_merchant(
        "MobilePay køb Coop App", "Netto Gladsaxe", "netto-gladsaxe"
    ) is False
    assert _description_matches_merchant(
        "MobilePay køb Coop App", "Bauhaus", "bauhaus"
    ) is False


def test_auto_link_coop_notprovided_transaction():
    """Verify description match calculation for MobilePay NOTPROVIDED with Coop receipt."""
    payload = {
        "booking_date": "2026-07-15",
        "amount": 123.45,
        "description": "MobilePay køb NOTPROVIDED",
    }

    assert _description_matches_merchant(
        payload["description"],
        "365discount Buddinge",
        "365discount-buddinge",
    ) is True
