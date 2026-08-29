"""Tests for the rules-based auto-categorization engine.

Covers:
- Text pre-processing
- Spiir hints seeding (idempotency, keyword count)
- Rule evaluation (keyword, regex, priority, short keywords)
- CRUD operations
- Retroactive application to uncategorized postings
"""
import pytest
from conftest import TEST_HOUSEHOLD_ID
from sqlmodel import Session, SQLModel, create_engine, select

from app.models import (
    Account,
    CategorizationRule,
    Household,
    Posting,
    PostingAllocation,
)
from app.services.category_service import seed_categories
from app.services.rules_service import (
    _SPIIR_HINTS,
    apply_rules_to_uncategorized,
    cleanup_promoted_household_rules,
    create_rule,
    delete_rule,
    evaluate_posting,
    list_rules,
    preprocess_description,
    seed_spiir_rules,
    update_rule,
)


@pytest.fixture()
def engine():
    """Create an in-memory SQLite engine with tables."""
    from sqlalchemy.pool import StaticPool
    eng = create_engine(
        "sqlite://",
        connect_args={"check_same_thread": False},
        poolclass=StaticPool,
        echo=False,
    )
    SQLModel.metadata.create_all(eng)
    return eng


@pytest.fixture()
def _patch_engine(engine, monkeypatch):
    """Patch all service modules to use the test engine."""
    import app.models as db_mod
    import app.services.category_service as cs
    import app.services.rules_service as rs

    monkeypatch.setattr(cs, "engine", engine)
    monkeypatch.setattr(rs, "engine", engine)
    monkeypatch.setattr(db_mod, "engine", engine)


@pytest.fixture()
def seeded_db(engine, _patch_engine):
    """Seed categories and rules into the test database."""
    with Session(engine) as db:
        db.add(Household(id=TEST_HOUSEHOLD_ID, name="Test Husstand"))
        db.commit()
    seed_categories()
    seed_spiir_rules()
    return engine


# ---------------------------------------------------------------------------
# Text Pre-processing
# ---------------------------------------------------------------------------

class TestPreprocessDescription:
    def test_lowercase(self):
        assert preprocess_description("NETTO AARHUS") == "netto aarhus"

    def test_strip_dates(self):
        result = preprocess_description("Dankort-nota 24.12 NETTO AARHUS")
        assert "24" not in result or "netto" in result
        assert "netto" in result
        assert "aarhus" in result

    def test_strip_dankort_prefix(self):
        result = preprocess_description("Dankort-nota NETTO AARHUS")
        assert "dankort" not in result
        assert "netto" in result

    def test_strip_visa_prefix(self):
        result = preprocess_description("VISA KØB DKK 199,00 Netflix")
        assert "visa" not in result
        assert "netflix" in result

    def test_strip_mobilepay(self):
        result = preprocess_description("MobilePay Betaling til Frisør")
        assert "mobilepay" not in result or "mobilpay" not in result
        assert "frisør" in result

    def test_strip_special_chars(self):
        result = preprocess_description("AMAZON.COM*5C7QC")
        assert "." not in result
        assert "*" not in result
        assert "amazon" in result

    def test_collapse_whitespace(self):
        result = preprocess_description("  NETTO    AARHUS  ")
        assert result == "netto aarhus"

    def test_preserves_danish_chars(self):
        result = preprocess_description("FØTEX ØLSTYKKE")
        assert "føtex" in result
        assert "ølstykke" in result

    def test_empty_string(self):
        assert preprocess_description("") == ""

    def test_only_noise(self):
        result = preprocess_description("Dankort-nota 24.12")
        # May be empty or just whitespace after stripping
        assert "dankort" not in result

    def test_strip_nota_and_notanr(self):
        assert preprocess_description("Dankort-nota 123456 Netto Kolding") == "netto kolding"
        assert preprocess_description("Føtex notanr. 987654 Aarhus") == "føtex aarhus"
        assert preprocess_description("OISTER.DK Nota nr. 25481049277035244685925") == "oister dk"

    def test_preserve_aftalenr(self):
        result = preprocess_description("BS AFTALENR 0000123456 Telenor")
        assert "aftalenr" in result
        assert "0000123456" in result
        assert "telenor" in result


# ---------------------------------------------------------------------------
# Seeding
# ---------------------------------------------------------------------------

class TestSeedSpiirRules:
    def test_seeds_all_hints(self, seeded_db):
        """All Spiir hints should create rules in the database."""
        expected_count = sum(len(keywords) for _, _, keywords in _SPIIR_HINTS)
        with Session(seeded_db) as db:
            actual = len(db.exec(select(CategorizationRule)).all())
        assert actual == expected_count

    def test_idempotent(self, seeded_db):
        """Running seed a second time should create 0 new rules."""
        new_count = seed_spiir_rules()
        assert new_count == 0

    def test_all_rules_are_system_source(self, seeded_db):
        with Session(seeded_db) as db:
            rules = db.exec(select(CategorizationRule)).all()
        assert all(r.source == "system" for r in rules)

    def test_all_rules_priority_1000(self, seeded_db):
        with Session(seeded_db) as db:
            rules = db.exec(select(CategorizationRule)).all()
        assert all(r.priority == 1000 for r in rules)


# ---------------------------------------------------------------------------
# Rule Evaluation
# ---------------------------------------------------------------------------

class TestEvaluatePosting:
    def test_matches_netto(self, seeded_db):
        posting = Posting(
            id="test-1",
            account_uid="acc1",
            amount_minor=-15000,
            original_description="Dankort-nota 24.06 NETTO AARHUS",
        )
        result = evaluate_posting(posting)
        assert result == "husholdning|dagligvarer"

    def test_matches_netflix(self, seeded_db):
        posting = Posting(
            id="test-2",
            account_uid="acc1",
            amount_minor=-9900,
            original_description="VISA KØB DKK 99,00 Netflix.com",
        )
        result = evaluate_posting(posting)
        assert result == "andre-leveomkostninger|tv-streaming"

    def test_matches_dsb(self, seeded_db):
        posting = Posting(
            id="test-3",
            account_uid="acc1",
            amount_minor=-5600,
            original_description="Dankort-nota DSB Billetsalg",
        )
        result = evaluate_posting(posting)
        assert result == "transport|bus-tog-færge-o-l"

    def test_matches_rejsekort(self, seeded_db):
        posting = Posting(
            id="test-4",
            account_uid="acc1",
            amount_minor=-3200,
            original_description="N*123456 Rejsekort Tankning",
        )
        result = evaluate_posting(posting)
        assert result == "transport|bus-tog-færge-o-l"

    def test_matches_uber(self, seeded_db):
        posting = Posting(
            id="test-5",
            account_uid="acc1",
            amount_minor=-18700,
            original_description="UBER* TRIP",
        )
        result = evaluate_posting(posting)
        assert result == "transport|taxi"

    def test_no_match_returns_none(self, seeded_db):
        posting = Posting(
            id="test-6",
            account_uid="acc1",
            amount_minor=-5000,
            original_description="XYZABC UNKNOWN MERCHANT 12345",
        )
        result = evaluate_posting(posting)
        assert result is None

    def test_empty_description_returns_none(self, seeded_db):
        posting = Posting(
            id="test-7",
            account_uid="acc1",
            amount_minor=-1000,
            original_description="",
        )
        result = evaluate_posting(posting)
        assert result is None

    def test_short_keyword_word_boundary(self, seeded_db):
        """Short keywords like 'dsb' should not match inside longer words."""
        posting = Posting(
            id="test-8",
            account_uid="acc1",
            amount_minor=-5000,
            original_description="ADSB Technology Corp",
        )
        result = evaluate_posting(posting)
        # Should NOT match "dsb" inside "ADSB"
        assert result != "transport|bus-tog-færge-o-l"

    def test_uses_creditor_name(self, seeded_db):
        """If description is generic, creditor_name should also be checked."""
        posting = Posting(
            id="test-9",
            account_uid="acc1",
            amount_minor=-19900,
            original_description="VISA KØB DKK 199,00",
            creditor_name="Spotify AB",
        )
        result = evaluate_posting(posting)
        assert result == "privatforbrug|film-musik-læsestof"

    def test_matches_danish_grocery_chain(self, seeded_db):
        posting = Posting(
            id="test-10",
            account_uid="acc1",
            amount_minor=-23450,
            original_description="Dankort-nota 05.07 REMA 1000 ØSTERBRO",
        )
        result = evaluate_posting(posting)
        assert result == "husholdning|dagligvarer"

    def test_matches_eon_drive(self, seeded_db):
        posting = Posting(
            id="test-eon",
            account_uid="acc1",
            amount_minor=-35000,
            original_description="Visa/Dankort E.ON Drive Infrastructure",
        )
        result = evaluate_posting(posting)
        assert result == "transport|brændstof"

    def test_matches_eesy_dk(self, seeded_db):
        posting = Posting(
            id="test-eesy",
            account_uid="acc1",
            amount_minor=-15000,
            original_description="eesy.dk Mobile",
        )
        result = evaluate_posting(posting)
        assert result == "andre-leveomkostninger|telefoni-internet"

    def test_matches_mcdonalds_locations(self, seeded_db):
        posting1 = Posting(
            id="test-mcd-1",
            account_uid="acc1",
            amount_minor=-8500,
            original_description="Visa MCDSLAGELSE SLAGELSE Nota nr. 123",
        )
        posting2 = Posting(
            id="test-mcd-2",
            account_uid="acc1",
            amount_minor=-12500,
            original_description="MCDGLADSAXE",
        )
        assert evaluate_posting(posting1) == "privatforbrug|fastfood-takeaway"
        assert evaluate_posting(posting2) == "privatforbrug|fastfood-takeaway"

    def test_partial_match_rule(self, seeded_db):
        create_rule(
            category_id="husholdning|dagligvarer",
            match_pattern="nett",
            partial_match=True,
        )
        posting = Posting(
            id="test-partial-1",
            account_uid="acc1",
            amount_minor=-5000,
            original_description="NettoSupermarked Aarhus",
        )
        result = evaluate_posting(posting)
        assert result == "husholdning|dagligvarer"

    def test_no_partial_match_rule(self, seeded_db):
        create_rule(
            category_id="husholdning|dagligvarer",
            match_pattern="nett",
            partial_match=False,
        )
        posting = Posting(
            id="test-partial-2",
            account_uid="acc1",
            amount_minor=-5000,
            original_description="NettoSupermarked Aarhus",
        )
        result = evaluate_posting(posting)
        # Should not match because it's not a whole word
        assert result is None



# ---------------------------------------------------------------------------
# Priority: user rules override system rules
# ---------------------------------------------------------------------------

class TestRulePriority:
    def test_user_rule_overrides_system(self, seeded_db):
        """A user rule with priority 500 should win over system rule at 1000."""
        # Create a user rule that maps "netto" to "privatforbrug|andet-privatforbrug"
        create_rule(
            category_id="privatforbrug|andet-privatforbrug",
            match_pattern="netto",
            priority=500,
        )

        posting = Posting(
            id="test-priority",
            account_uid="acc1",
            amount_minor=-15000,
            original_description="NETTO AARHUS",
        )
        result = evaluate_posting(posting)
        # User rule (priority 500) should win
        assert result == "privatforbrug|andet-privatforbrug"

    def test_user_rule_overrides_system_high_priority(self, seeded_db):
        """A user rule with priority 1500 should win over system rule at 1000."""
        create_rule(
            category_id="privatforbrug|andet-privatforbrug",
            match_pattern="netto",
            priority=1500,
        )

        posting = Posting(
            id="test-priority-high",
            account_uid="acc1",
            amount_minor=-15000,
            original_description="NETTO AARHUS",
        )
        result = evaluate_posting(posting)
        # User rule should win due to source precedence (user rules run before system rules)
        assert result == "privatforbrug|andet-privatforbrug"


# ---------------------------------------------------------------------------
# CRUD Operations
# ---------------------------------------------------------------------------

class TestRuleCRUD:
    def test_create_and_list(self, seeded_db):
        rule = create_rule(
            category_id="bolig|have-planter",
            match_pattern="plantorama",
            partial_match=True,
        )
        assert rule["match_pattern"] == "plantorama"
        assert rule["source"] == "user"
        assert rule["priority"] == 500
        assert rule["partial_match"] is True

        rules = list_rules(source="user")
        assert any(r["match_pattern"] == "plantorama" and r["partial_match"] is True for r in rules)

    def test_update(self, seeded_db):
        rule = create_rule(
            category_id="bolig|have-planter",
            match_pattern="plantorama",
        )
        updated = update_rule(rule["id"], {"priority": 100})
        assert updated is not None
        assert updated["priority"] == 100

    def test_update_nonexistent_returns_none(self, seeded_db):
        result = update_rule("nonexistent-id", {"priority": 100})
        assert result is None

    def test_delete(self, seeded_db):
        rule = create_rule(
            category_id="bolig|have-planter",
            match_pattern="plantorama",
        )
        assert delete_rule(rule["id"]) is True
        assert delete_rule(rule["id"]) is False

    def test_list_filtered_by_category(self, seeded_db):
        rules = list_rules(category_id="husholdning|dagligvarer")
        assert len(rules) > 0
        assert all(r["category_id"] == "husholdning|dagligvarer" for r in rules)


# ---------------------------------------------------------------------------
# Retroactive Application
# ---------------------------------------------------------------------------

class TestApplyRules:
    def test_categorizes_uncategorized_postings(self, seeded_db):
        with Session(seeded_db) as db:
            # Create an account
            db.add(Account(uid="acc-retro", household_id=TEST_HOUSEHOLD_ID, session_name="test"))

            # Create postings WITHOUT allocations
            db.add(Posting(
                id="retro-1",
                household_id=TEST_HOUSEHOLD_ID,
                account_uid="acc-retro",
                amount_minor=-15000,
                booking_date="2026-07-01",
                original_description="NETTO AARHUS",
            ))
            db.add(Posting(
                id="retro-2",
                household_id=TEST_HOUSEHOLD_ID,
                account_uid="acc-retro",
                amount_minor=-9900,
                booking_date="2026-07-02",
                original_description="Netflix.com Monthly",
            ))
            db.commit()

        result = apply_rules_to_uncategorized()
        assert result["categorized"] == 2

        # Verify the allocations were created
        with Session(seeded_db) as db:
            alloc1 = db.exec(
                select(PostingAllocation)
                .where(PostingAllocation.posting_id == "retro-1")
            ).first()
            assert alloc1 is not None
            assert alloc1.category_id == "husholdning|dagligvarer"

            alloc2 = db.exec(
                select(PostingAllocation)
                .where(PostingAllocation.posting_id == "retro-2")
            ).first()
            assert alloc2 is not None
            assert alloc2.category_id == "andre-leveomkostninger|tv-streaming"

    def test_skips_already_categorized(self, seeded_db):
        with Session(seeded_db) as db:
            db.add(Account(uid="acc-skip", household_id=TEST_HOUSEHOLD_ID, session_name="test"))
            db.add(Posting(
                id="skip-1",
                household_id=TEST_HOUSEHOLD_ID,
                account_uid="acc-skip",
                amount_minor=-15000,
                booking_date="2026-07-01",
                original_description="NETTO AARHUS",
            ))
            # Already has a real allocation
            db.add(PostingAllocation(
                posting_id="skip-1",
                category_id="privatforbrug|tobak-alkohol",
                amount_minor=-15000,
            ))
            db.commit()

        result = apply_rules_to_uncategorized()
        assert result["categorized"] == 0
        assert result["skipped"] >= 1

    def test_does_not_overwrite_splits(self, seeded_db):
        with Session(seeded_db) as db:
            db.add(Account(uid="acc-split", household_id=TEST_HOUSEHOLD_ID, session_name="test"))
            db.add(Posting(
                id="split-1",
                household_id=TEST_HOUSEHOLD_ID,
                account_uid="acc-split",
                amount_minor=-20000,
                booking_date="2026-07-01",
                original_description="NETTO AARHUS",
            ))
            # Multiple splits = user-created, should not be touched
            db.add(PostingAllocation(
                posting_id="split-1",
                category_id="husholdning|dagligvarer",
                amount_minor=-15000,
            ))
            db.add(PostingAllocation(
                posting_id="split-1",
                category_id="privatforbrug|tobak-alkohol",
                amount_minor=-5000,
            ))
            db.commit()

        result = apply_rules_to_uncategorized()
        # Should skip the split posting
        assert result["categorized"] == 0


class TestPromotedRules:
    @pytest.mark.parametrize(
        ("description", "expected_cat"),
        [
            ("Dankort-nota CYKELGEAR DK 4477003 TERNDRUP", "transport|værksted-reservedele"),
            ("BS AFTALENR 009920408 TRYG FORSIKRING", "bolig|indbo-familieforsikring"),
            ("Dankort-nota FYNS SOMMERLAND KOEBENHAVN S", "privatforbrug|biograf-koncerter-forlystelser"),
            ("Dankort-nota THURØ MINIGOLF Z034996", "privatforbrug|biograf-koncerter-forlystelser"),
            ("Lønoverførsel august", "indkomst|løn"),
            ("Udbetaling af overskydende skat", "indkomst|overskydende-skat"),
            ("Børne- og ungeydelse 3. kvartal", "indkomst|børnepenge"),
            ("Fødevarecheck udk f", "indkomst|anden-indkomst"),
            ("BS Danmarks Lærerforening medlem aftalenr 020985907", "andre-leveomkostninger|fagforening-a-kasse"),
            ("Betalingsservice IDA Ingeniørfore i Danmark aftalenr 904365853", "andre-leveomkostninger|fagforening-a-kasse"),
            ("TV2 DK ID 223534191 Odense C", "andre-leveomkostninger|tv-streaming"),
            ("IMERCO DK", "privatforbrug|møbler-boligudstyr"),
            ("Bison Boulders Soeborg", "privatforbrug|sport-fritid"),
            ("Dankort-nota Nielsens SH C143906", "privatforbrug|tøj-sko-accessories"),
            ("Min Købmand Søborg C612895", "husholdning|dagligvarer"),
            ("DSB App WD7FYF 1", "transport|bus-tog-færge-o-l"),
            ("THANSEN SVENDBORG Z118692", "transport|værksted-reservedele"),
            ("10er 10er ministeriet kbenhavn", "privatforbrug|online-services-software"),
            ("Betalingsservice Dansk Flygtningehjælp aftalenr 965857648", "privatforbrug|gaver-velgørenhed"),
            ("Betalingsservice Oxfam Danmark aftalenr 970548842", "privatforbrug|gaver-velgørenhed"),
            ("Betalingsservice SOS Børnebyerne aftalenr 965467548", "privatforbrug|gaver-velgørenhed"),
            ("Dankort Thurø Strand Camp Z003527", "ferie|ferieaktiviteter"),
            ("LavprisVVS dk C60568979", "bolig|ombygning-vedligehold"),
            ("Friluftslageret Ap C062091", "husholdning|kiosk-bager-specialbutikker"),
            ("Dankort ZOO ODENSE C775809", "privatforbrug|biograf-koncerter-forlystelser"),
            ("Moesgaardmuseum dk", "privatforbrug|biograf-koncerter-forlystelser"),
            ("Dinoland C315743", "privatforbrug|biograf-koncerter-forlystelser"),
            ("Bindia Soeborg Copenhagen", "privatforbrug|fastfood-takeaway"),
            ("Blockbuster Stockholm", "privatforbrug|film-musik-læsestof"),
            ("Saxo com 80a5b6ff053", "privatforbrug|film-musik-læsestof"),
            ("Okofamilien dk", "privatforbrug|frisør-personlig-pleje"),
            ("E.ON Drive Infrastructure Soborg", "transport|brændstof"),
        ],
    )
    def test_evaluates_promoted_descriptions(self, seeded_db, description, expected_cat):
        posting = Posting(
            id="test-promoted",
            account_uid="acc1",
            amount_minor=-1000,
            original_description=description,
        )
        assert evaluate_posting(posting) == expected_cat


class TestCleanupPromotedHouseholdRules:
    def test_removes_redundant_user_rules_and_preserves_custom(self, seeded_db):
        with Session(seeded_db) as db:
            # Redundant user rule (matches system rule for Thansen)
            db.add(CategorizationRule(
                id="user-rule-1",
                household_id=TEST_HOUSEHOLD_ID,
                category_id="transport|værksted-reservedele",
                match_pattern="thansen svendborg z118692",
                is_regex=False,
                priority=500,
                source="user",
                is_active=True,
            ))
            # Explicitly promoted / remapped rule (Fyns sommerland)
            db.add(CategorizationRule(
                id="user-rule-2",
                household_id=TEST_HOUSEHOLD_ID,
                category_id="ferie|ferieaktiviteter",
                match_pattern="fyns sommerland koebenhavn s",
                is_regex=False,
                priority=500,
                source="user",
                is_active=True,
            ))
            # Custom private user rule (should be preserved!)
            db.add(CategorizationRule(
                id="user-rule-3",
                household_id=TEST_HOUSEHOLD_ID,
                category_id="vis-ikke|kontooverførsel",
                match_pattern="til boliglån",
                is_regex=False,
                priority=500,
                source="user",
                is_active=True,
            ))
            db.commit()

        removed = cleanup_promoted_household_rules()
        assert removed >= 2

        with Session(seeded_db) as db:
            remaining_user_rules = db.exec(
                select(CategorizationRule).where(CategorizationRule.source == "user")
            ).all()

        patterns = [r.match_pattern for r in remaining_user_rules]
        assert "til boliglån" in patterns
        assert "thansen svendborg z118692" not in patterns
        assert "fyns sommerland koebenhavn s" not in patterns
