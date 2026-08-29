"""Rules service — keyword & regex auto-categorization engine.

This module ports the ENTIRE Spiir auto-categorization "hints" system
(324 keywords across 69 subcategories, tuned to the Danish market) into
a rule-based engine stored in the database.

Architecture:
    1. Text pre-processing (strip dates, card prefixes, special chars)
    2. Rule evaluation in priority order (lower number = higher priority)
    3. User rules (priority 500) always override system rules (priority 1000)
    4. ML model can be plugged in as a fallback in a future phase

The system is designed so the app works FULLY without ML. ML is optional
and pluggable via a simple interface in the decision logic.
"""
import contextlib
import functools
import re
from datetime import UTC, datetime
from typing import Any

from sqlmodel import Session, col, select

from app.models import (
    CategorizationRule,
    Posting,
    PostingAllocation,
    engine,
)
from app.services.category_service import make_category_id


def _utcnow_iso() -> str:
    return datetime.now(UTC).isoformat().replace("+00:00", "Z")


# ---------------------------------------------------------------------------
# Text Pre-processing (ported from Spiir auto_categorization_spec.md)
# ---------------------------------------------------------------------------

# Pre-compiled patterns for performance
_DATE_RE = re.compile(r"\b\d{1,2}[./-]\d{1,2}([./-]\d{2,4})?\b")
_PAYMENT_PREFIXES = [
    re.compile(r"dankort[- ]?køb", re.I),
    re.compile(r"visa/dankort", re.I),
    re.compile(r"\bkontaktløs\b", re.I),
    re.compile(r"\bvisa\b", re.I),
    re.compile(r"\bmastercard\b", re.I),
    re.compile(r"\bmobilepay\b|\bmobilpay\b", re.I),
    re.compile(r"\bn\*\d+\b", re.I),
    re.compile(r"\bnet\d+\b", re.I),
    re.compile(r"\bbs\s*betaling\b", re.I),
    re.compile(r"\bpbs\b", re.I),
    re.compile(r"\boverførsel\b", re.I),
]
_NOTA_RE = re.compile(
    r"\b(?:dankort[- ]?|visa(?:[/-]dankort)?[- ]?)?nota(?:\s*nr\.?|\.nr\.?|\.|\:)?\s*[0-9]+\b|\bnotanr\.?\s*[0-9]+\b|\b(?:dankort[- ]?|visa(?:[/-]dankort)?[- ]?)?nota\b|\bnotanr\.?\b",
    re.I,
)
_SPECIAL_CHARS_RE = re.compile(r"[^a-zæøå0-9\s]")
_WHITESPACE_RE = re.compile(r"\s+")


def preprocess_description(raw_desc: str) -> str:
    """Clean a raw bank description for rule matching.

    Ported from Spiir's auto_categorization_spec.md & enhanced:
    1. Lowercase
    2. Remove date patterns (12.03.26, 24/12, etc.)
    3. Remove payment system prefixes (dankort-køb, visa/dankort, etc.)
    4. Remove nota / notanr and associated transaction/receipt codes
    5. Preserve aftalenr (Betalingsservice agreement numbers)
    6. Remove special characters, collapse whitespace
    """
    text = raw_desc.lower()
    text = _DATE_RE.sub("", text)
    for prefix_re in _PAYMENT_PREFIXES:
        text = prefix_re.sub("", text)
    text = _NOTA_RE.sub("", text)
    text = _SPECIAL_CHARS_RE.sub(" ", text)
    text = _WHITESPACE_RE.sub(" ", text).strip()
    return text


# ---------------------------------------------------------------------------
# Spiir Hints → Peng Rules Mapping
#
# This is the COMPLETE port of Spiir's "hints" field from
# categories_metadata.json. Each entry maps a Spiir subcategory name
# (which maps 1:1 to our Category taxonomy) to its list of keywords.
#
# Format: (main_category_name, sub_category_name, [keyword1, keyword2, ...])
# ---------------------------------------------------------------------------

_SPIIR_HINTS: list[tuple[str, str, list[str]]] = [
    # === INDKOMST ===
    ("Indkomst", "Løn", [
        "løn", "lønoverførsel", "gage",
    ]),
    ("Indkomst", "Pensionsudbetaling", [
        "tjenestemandspension", "førtidspension",
    ]),
    ("Indkomst", "Dagpenge/overførselsindkomst", [
        "kontanthjælp",
    ]),
    ("Indkomst", "Børnepenge", [
        "familieydelse", "børnecheck", "børne og ungeydelse", "ungeydelse",
    ]),
    ("Indkomst", "Udbytte & afkast", [
        "bonus",
    ]),
    ("Indkomst", "Overskydende skat", [
        "overskydende skat", "skat overskydende",
    ]),
    ("Indkomst", "Anden indkomst", [
        "arveforskud", "pengegaver", "fødevarecheck",
    ]),
    ("Indkomst", "Boligstøtte", [
        "boligsikring", "boligtilskud",
    ]),

    # === BOLIG ===
    ("Bolig", "Boliglån/husleje", [
        "pantebreve", "realkreditlån", "rent",
    ]),
    ("Bolig", "El, vand, varme & renovation", [
        "gas", "oliefyr", "naturgas", "fjernvarme", "affald", "skrald",
    ]),
    ("Bolig", "Ejerforening", [
        "grundejerforening", "parcelforening",
    ]),
    ("Bolig", "Ejendomsskat", [
        "grundskyld",
    ]),
    ("Bolig", "Husforsikring", [
        "villaforsikring",
    ]),
    ("Bolig", "Indbo- & familieforsikring", [
        "basisforsikring", "tryg forsikring", "tryg",
    ]),
    ("Bolig", "Udgifter fritidshus", [
        "udgifter sommerhus", "udgifter campingvogn",
    ]),
    ("Bolig", "Ombygning & vedligehold", [
        "udbygning", "maler", "vvs", "tømrer", "murer", "elektriker",
        "nyt køkken", "reparation", "arkitekt", "lavprisvvs", "lavprisvvs dk",
    ]),
    ("Bolig", "Andre boligudgifter", [
        "flytning", "advokat", "ejendomsmægler", "ejerskifteforsikring",
        "depositum", "møntvaskeri", "vaskeri", "tøjvask",
    ]),
    ("Bolig", "Have & planter", [
        "blomster", "potter",
    ]),

    # === TRANSPORT ===
    ("Transport", "Bil-, MC-, bådlån o.l.", [
        "billån", "motorcykellån",
    ]),
    ("Transport", "Brændstof", [
        "benzin", "diesel", "tankstation", "eon drive", "e on drive",
    ]),
    ("Transport", "Bilforsikring & autohjælp", [
        "falck", "fdm", "vejhjælp",
    ]),
    ("Transport", "Ejerafgift/grøn afgift", [
        "vægtafgift", "bilafgift",
    ]),
    ("Transport", "Bus, tog, færge o.l.", [
        "brobizz", "metro", "s-tog", "arriva", "dsb", "dsb app", "broafgift",
        "månedskort", "togkort", "buskort", "vejafgift", "pendlerkort",
        "periodekort", "rejsekort", "klippekort",
    ]),
    ("Transport", "Taxi", [
        "taxa", "hyrevogn", "uber",
    ]),
    ("Transport", "Parkering", [
        "parkpark", "easypark", "qpark",
    ]),
    ("Transport", "Værksted & reservedele", [
        "syn", "service", "vinterdæk", "fælge", "bilreparation", "bilvask",
        "cykelgear", "cykelgear dk", "fri bikeshop", "fri bike shop",
        "thansen", "t hansen",
    ]),
    ("Transport", "Anden transport", [
        "ny bil", "ny motorcykel", "ny båd", "ny cykel", "ny mc",
        "gomore", "cykel", "el-løbehjul",
    ]),

    # === HUSHOLDNING ===
    ("Husholdning", "Dagligvarer", [
        "mad", "supermarked", "madvarer",
        # Additional well-known Danish grocery chains (from kvitteringer_service)
        "netto", "rema", "rema 1000", "rema1000", "føtex", "bilka",
        "aldi", "lidl", "meny", "irma", "fakta", "kvickly",
        "superbrugsen", "nemlig", "365discount", "coop", "coop365", "min købmand", "re:\\b365\\s+[a-zæøå]",
    ]),
    ("Husholdning", "Kiosk, bager & specialbutikker", [
        "brød", "kager", "frugt", "købmand", "slik", "friluftslageret",
    ]),
    ("Husholdning", "Kantine- & frokostordning", [
        "madordning", "skolemad",
    ]),

    # === ANDRE LEVEOMKOSTNINGER ===
    ("Andre leveomkostninger", "Apotek & medicin", [
        "creme", "personlig pleje", "astma", "apotek",
    ]),
    ("Andre leveomkostninger", "Institution", [
        "klassekasse", "børnehave", "vuggestue", "sfo",
        "fritidshjem", "dagpleje", "efterskole", "privatskole",
        "daginstitution",
    ]),
    ("Andre leveomkostninger", "Fagforening & a-kasse", [
        "fagligt kontingent", "akasse", "a-kasse", "hk", "3f", "prosa",
        "danmarks lærerforening", "dlf", "ida ingeniørfore", "ingeniørforeningen", "ida",
    ]),
    ("Andre leveomkostninger", "Livs- & ulykkesforsikring", [
        "gruppeliv",
    ]),
    ("Andre leveomkostninger", "Sundheds- & sygeforsikring", [
        "forebygger",
    ]),
    ("Andre leveomkostninger", "TV & streaming", [
        "kabel tv", "viasat", "sattelit", "antenneforening", "radio",
        "netflix", "netflix.com", "hbo", "viaplay", "disney+", "disney plus",
        "dr licens", "tv2 play", "tv 2 play", "tv2 dk", "tv 2", "amazon prime",
    ]),
    ("Andre leveomkostninger", "Telefoni & internet", [
        "mobiltelefon", "taletidskort", "udlandstelefoni", "fastnet",
        "fiber", "adsl", "bredbånd", "telia", "telenor", "3 mobil",
        "yousee", "fullrate", "oister", "lebara", "lycamobile", "eesy",
    ]),
    ("Andre leveomkostninger", "Behandling & læger", [
        "tandlæge", "øjenlæge", "speciallæge", "kiropraktor",
        "fysioterapeut", "psykolog", "hypnotisør", "akupunktør",
        "zoneterapeut",
    ]),
    ("Andre leveomkostninger", "Briller & kontaktlinser", [
        "optiker",
    ]),
    ("Andre leveomkostninger", "Studieudgifter", [
        "studiebøger", "kopier",
    ]),
    ("Andre leveomkostninger", "Foreninger & kontingenter", [
        "medlemsskab", "ældre sagen", "ecykleklub",
    ]),

    # === PRIVATFORBRUG ===
    ("Privatforbrug", "Sport & fritid", [
        "spejder", "fitness", "styrketræning", "aftenskole", "håndbold",
        "fodbold", "basket", "badminton", "tennis", "svømning",
        "squash", "golf", "bison boulders", "boulders", "familiespejd",
    ]),
    ("Privatforbrug", "Hus & havehjælp", [
        "rengøring", "gartner", "vinduespudser",
    ]),
    ("Privatforbrug", "Fastfood & takeaway", [
        "junkfood", "burger", "sushi", "pizzaria", "takeaway", "indisk",
        "mcdonalds", "burger king", "subway", "dominos", "pizza",
        "wolt", "just eat", "hungry", "bindia", "re:\\bmcd",
    ]),
    ("Privatforbrug", "Bar, cafe & restaurant", [
        "diskotek", "værtshus", "disco", "fest", "middag",
        "cafe", "restaurant",
    ]),
    ("Privatforbrug", "Tøj, sko & accessories", [
        "smykker", "bukser", "bluse", "jeans", "kjole", "taske",
        "jakke", "frakke", "støvler", "ring", "halskæde", "t-shirt",
        "skjorte", "beklædning", "h&m", "zara", "zalando", "nielsens",
    ]),
    ("Privatforbrug", "Møbler & boligudstyr", [
        "køkkenudstyr", "sofa", "seng", "bord", "stole", "hvidevarer",
        "lamper", "malerier", "kunst", "inventar", "ikea", "jysk",
        "idemøbler", "ilva", "imerco", "imerco dk",
    ]),
    ("Privatforbrug", "Elektronik & computerudstyr", [
        "ny mobiltelefon", "playstation", "wii", "xbox", "konsol",
        "pc", "nintendo", "elgiganten", "power", "proshop",
        "computersalg",
    ]),
    ("Privatforbrug", "Spil & legetøj", [
        "playstation spil", "xbox spil", "wii spil", "pc spil",
        "br legetøj", "lego",
    ]),
    ("Privatforbrug", "Hobby & sportsudstyr", [
        "skitøj", "golfudstyr", "surfudstyr", "løbesko", "løbetøj",
        "pulsmåler", "sportmaster", "intersport",
    ]),
    ("Privatforbrug", "Frisør & personlig pleje", [
        "parfume", "klipning", "hårklip", "massage",
        "coaching", "wellness", "solcenter", "frisør", "økofamilien", "okofamilien",
    ]),
    ("Privatforbrug", "Film, musik & læsestof", [
        "bøger", "blade", "aviser", "magasiner", "dvd", "cd", "mp3",
        "itunes", "dameblade", "faglitteratur", "fagbøger",
        "skønlitteratur", "spotify", "saxo", "saxo com", "audible", "blockbuster",
    ]),
    ("Privatforbrug", "Biograf, koncerter & forlystelser", [
        "museum", "kultur", "biffen", "musik", "billetter",
        "tivoli", "sommerland", "fyns sommerland", "legeland", "biograf", "kino",
        "odense zoo", "zoo odense", "moesgaard museum", "moesgaardmuseum", "danmarks jernbanemuseum",
        "dinoland", "minigolf",
    ]),
    ("Privatforbrug", "Tips & lotto", [
        "poker", "klasselotteri", "casino", "odds", "kasino",
        "lotteri", "banko", "bingo", "danske spil", "bet365",
    ]),
    ("Privatforbrug", "Babyudstyr", [
        "barnevogn", "klapvogn", "barneseng",
    ]),
    ("Privatforbrug", "Kæledyr", [
        "hund", "kat", "edderkop", "dyrlæge",
    ]),
    ("Privatforbrug", "Gaver & velgørenhed", [
        "nødhjælp", "donationer", "røde kors", "red barnet",
        "folkekirkens nødhjælp", "wwf verdensnaturfonden", "wspa",
        "børnefonde", "læger uden grænser", "amnesty international",
        "unicef", "gave", "dansk flygtningehjælp", "flygtningehjælp", "oxfam", "oxfam danmark",
        "sos børnebyerne", "den danske naturfond", "foreningen sand",
    ]),
    ("Privatforbrug", "Tobak & alkohol", [
        "spiritus", "cigaretter", "øl", "vin", "snus", "vape",
    ]),
    ("Privatforbrug", "Kontanthævning & check", [
        "hæveautomat",
    ]),
    ("Privatforbrug", "Online services & software", [
        "webhotel", "domæne", "apps", "apple", "google play", "10er dk", "10er",
    ]),
    ("Privatforbrug", "Andet privatforbrug", [
        "barnepige", "frimærker", "babysitter", "fragt", "posthus",
        "pakker", "lommepenge", "kontorartikler", "tøjrens", "renseri",
        "kreditkort",
    ]),
    ("Privatforbrug", "Serviceydelser & rådgivning", [
        "revisor", "privatøkonomisk rådgiver",
    ]),

    # === FERIE ===
    ("Ferie", "Fly & Hotel", [
        "charterferie", "rejser", "booking.com", "airbnb", "hotels.com",
        "momondo", "sas", "norwegian", "ryanair", "easyjet",
    ]),
    ("Ferie", "Billeje", [
        "hertz", "avis", "europcar", "sixt",
    ]),
    ("Ferie", "Ferieaktiviteter", [
        "skileje", "liftkort", "skiskole", "thurø strand camp", "strand camp",
    ]),

    # === DIVERSE ===
    ("Diverse", "Ukendt", [
        "ved ikke",
    ]),
    ("Diverse", "Bøder & afgifter", [
        "fartbøde", "parkeringsbøde",
    ]),
    ("Diverse", "Offentligt gebyr", [
        "pas", "kørekort", "kommune", "told",
    ]),

    # === PENSION & OPSPARING ===
    ("Pension & Opsparing", "Pensionsopsparing", [
        "ratepension", "kapitalpension",
    ]),
    ("Pension & Opsparing", "Anden opsparing", [
        "ferieopsparing",
    ]),
    ("Pension & Opsparing", "Værdipapirshandel", [
        "investering", "aktier", "nordnet", "saxo bank",
    ]),
]


# ---------------------------------------------------------------------------
# Seeding — port ALL Spiir hints into CategorizationRule rows
# ---------------------------------------------------------------------------

def seed_spiir_rules() -> int:
    """Seed all Spiir categorization hints as system rules. Idempotent.

    Returns the number of NEW rules created (0 on subsequent runs).
    """
    created = 0
    with Session(engine) as db:
        for main_name, sub_name, keywords in _SPIIR_HINTS:
            category_id = make_category_id(main_name, sub_name)

            for keyword in keywords:
                keyword_lower = keyword.lower().strip()
                if not keyword_lower:
                    continue

                is_regex = False
                pattern_str = keyword_lower
                if keyword_lower.startswith("re:"):
                    is_regex = True
                    pattern_str = keyword_lower[3:]
                else:
                    pattern_str = preprocess_description(pattern_str)
                    if not pattern_str:
                        continue

                # Check if this exact rule already exists (idempotent)
                existing = db.exec(
                    select(CategorizationRule)
                    .where(CategorizationRule.category_id == category_id)
                    .where(CategorizationRule.match_pattern == pattern_str)
                    .where(CategorizationRule.is_regex == is_regex)
                    .where(CategorizationRule.source == "system")
                ).first()

                if existing is None:
                    db.add(CategorizationRule(
                        category_id=category_id,
                        match_pattern=pattern_str,
                        is_regex=is_regex,
                        priority=1000,
                        source="system",
                        is_active=True,
                    ))
                    created += 1

        db.commit()

    # Always ensure existing stored rules are cleaned up and migrated
    clean_and_migrate_stored_rules()
    return created


def clean_and_migrate_stored_rules() -> int:
    """Clean stored categorization rules by stripping nota/notanr reference numbers
    and removing invalid system rules (such as 'nota').

    Returns the number of rules updated or removed.
    """
    updated_count = 0
    with Session(engine) as db:
        rules = db.exec(select(CategorizationRule)).all()
        for rule in rules:
            # 1. Delete invalid broad system rules matching standalone "nota" or "notanr"
            if rule.source == "system" and rule.match_pattern in ("nota", "notanr", "dankort-nota", "dankort nota"):
                db.delete(rule)
                updated_count += 1
                continue

            if not rule.is_regex:
                cleaned_pattern = preprocess_description(rule.match_pattern)
                if not cleaned_pattern:
                    db.delete(rule)
                    updated_count += 1
                elif cleaned_pattern != rule.match_pattern:
                    # Check for duplicate
                    dup = db.exec(
                        select(CategorizationRule)
                        .where(CategorizationRule.id != rule.id)
                        .where(CategorizationRule.category_id == rule.category_id)
                        .where(CategorizationRule.match_pattern == cleaned_pattern)
                        .where(CategorizationRule.source == rule.source)
                    ).first()
                    if dup:
                        db.delete(rule)
                    else:
                        rule.match_pattern = cleaned_pattern
                        rule.updated_at = _utcnow_iso()
                        db.add(rule)
                    updated_count += 1

        db.commit()

    updated_count += cleanup_promoted_household_rules()
    return updated_count


def cleanup_promoted_household_rules() -> int:
    """Identify and remove user-defined categorization rules that are now
    redundant because global system rules provide the exact same categorization,
    or that have been intentionally promoted/remapped to system rules.

    Returns the number of user rules removed.
    """
    removed_count = 0
    with Session(engine) as db:
        system_rules = db.exec(
            select(CategorizationRule)
            .where(CategorizationRule.source == "system")
            .where(CategorizationRule.is_active == True)  # noqa: E712
            .order_by(col(CategorizationRule.priority).asc())
        ).all()

        user_rules = db.exec(
            select(CategorizationRule)
            .where(CategorizationRule.source == "user")
        ).all()

        # Explicitly promoted / remapped patterns that should be removed from user rules
        explicit_remap_patterns = {
            "fyns sommerland",
            "fyns sommerland koebenhavn s",
            "thurø minigolf",
            "thurø minigolf z034996",
        }

        for rule in user_rules:
            pattern = rule.match_pattern.lower().strip()
            if not pattern:
                db.delete(rule)
                removed_count += 1
                continue

            if pattern in explicit_remap_patterns:
                db.delete(rule)
                removed_count += 1
                continue

            # If system rules evaluate this pattern to the exact same category, user rule is redundant
            matched_cat = evaluate_text(pattern, rules=system_rules)
            if matched_cat is not None and matched_cat == rule.category_id:
                db.delete(rule)
                removed_count += 1

        db.commit()
    return removed_count


# ---------------------------------------------------------------------------
# Rule Evaluation Engine
# ---------------------------------------------------------------------------

@functools.lru_cache(maxsize=2048)
def _compile_pattern_cached(pattern: str, is_regex: bool, partial_match: bool) -> re.Pattern | None:
    if is_regex:
        with contextlib.suppress(re.error):
            return re.compile(pattern, re.IGNORECASE)
        return None

    cleaned = pattern.lower()
    pattern_cleaned = _SPECIAL_CHARS_RE.sub(" ", cleaned)
    pattern_cleaned = _WHITESPACE_RE.sub(" ", pattern_cleaned).strip()
    if not pattern_cleaned:
        return None
    if partial_match:
        return re.compile(re.escape(pattern_cleaned))
    return re.compile(rf"\b{re.escape(pattern_cleaned)}\b")


def get_compiled_regex(rule: CategorizationRule) -> re.Pattern | None:
    """Compile and cache the regex pattern for a CategorizationRule."""
    if hasattr(rule, "_compiled_regex"):
        return rule._compiled_regex

    compiled = _compile_pattern_cached(
        rule.match_pattern,
        bool(rule.is_regex),
        bool(getattr(rule, "partial_match", False)),
    )
    rule._compiled_regex = compiled
    return compiled


def evaluate_text(
    primary_text: str,
    extra_text: str = "",
    rules: list[CategorizationRule] | None = None,
) -> str | None:
    """Evaluate raw text against rules, optionally with extra context text."""
    if not primary_text.strip():
        return None

    cleaned = preprocess_description(primary_text)
    if not cleaned:
        return None

    search_text = f"{cleaned} {extra_text.lower()}".strip()

    if rules is None:
        with Session(engine) as db:
            rules = db.exec(
                select(CategorizationRule)
                .where(CategorizationRule.is_active == True)  # noqa: E712
                .order_by(
                    col(CategorizationRule.source).desc(),
                    col(CategorizationRule.priority).asc(),
                )
            ).all()

    for rule in rules:
        compiled = get_compiled_regex(rule)
        if compiled is not None:
            if compiled.search(search_text):
                return rule.category_id

    return None


def evaluate_posting(
    posting: Posting,
    rules: list[CategorizationRule] | None = None,
) -> str | None:
    """Evaluate a posting against all active rules and return the best match."""
    extra_text = " ".join(filter(None, [
        posting.creditor_name,
        posting.remittance_information,
    ]))
    return evaluate_text(posting.original_description or "", extra_text, rules)


# ---------------------------------------------------------------------------
# CRUD Operations
# ---------------------------------------------------------------------------

def list_rules(
    source: str | None = None,
    category_id: str | None = None,
) -> list[dict[str, Any]]:
    """List categorization rules with optional filtering."""
    with Session(engine) as db:
        query = select(CategorizationRule).order_by(
            col(CategorizationRule.source).desc(),
            col(CategorizationRule.priority).asc(),
            col(CategorizationRule.match_pattern).asc(),
        )
        if source:
            query = query.where(CategorizationRule.source == source)
        if category_id:
            query = query.where(CategorizationRule.category_id == category_id)

        rules = db.exec(query).all()

    return [
        {
            "id": r.id,
            "category_id": r.category_id,
            "match_pattern": r.match_pattern,
            "is_regex": r.is_regex,
            "partial_match": r.partial_match,
            "priority": r.priority,
            "source": r.source,
            "is_active": r.is_active,
        }
        for r in rules
    ]


def create_rule(
    category_id: str,
    match_pattern: str,
    is_regex: bool = False,
    partial_match: bool = False,
    priority: int = 500,
) -> dict[str, Any]:
    """Create a new user-defined categorization rule."""
    now = _utcnow_iso()
    with Session(engine) as db:
        rule = CategorizationRule(
            category_id=category_id,
            match_pattern=match_pattern.lower().strip(),
            is_regex=is_regex,
            partial_match=partial_match,
            priority=priority,
            source="user",
            is_active=True,
            created_at=now,
            updated_at=now,
        )
        db.add(rule)
        db.commit()
        db.refresh(rule)

    return {
        "id": rule.id,
        "category_id": rule.category_id,
        "match_pattern": rule.match_pattern,
        "is_regex": rule.is_regex,
        "partial_match": rule.partial_match,
        "priority": rule.priority,
        "source": rule.source,
        "is_active": rule.is_active,
    }


def update_rule(rule_id: str, patch: dict[str, Any]) -> dict[str, Any] | None:
    """Update an existing categorization rule."""
    now = _utcnow_iso()
    with Session(engine) as db:
        rule = db.get(CategorizationRule, rule_id)
        if rule is None:
            return None

        for key in ("category_id", "match_pattern", "is_regex", "partial_match", "priority", "is_active"):
            if key in patch:
                value = patch[key]
                if key == "match_pattern":
                    value = value.lower().strip()
                setattr(rule, key, value)

        rule.updated_at = now
        db.commit()
        db.refresh(rule)

    return {
        "id": rule.id,
        "category_id": rule.category_id,
        "match_pattern": rule.match_pattern,
        "is_regex": rule.is_regex,
        "partial_match": rule.partial_match,
        "priority": rule.priority,
        "source": rule.source,
        "is_active": rule.is_active,
    }


def delete_rule(rule_id: str) -> bool:
    """Delete a categorization rule. Returns True if found and deleted."""
    with Session(engine) as db:
        rule = db.get(CategorizationRule, rule_id)
        if rule is None:
            return False
        db.delete(rule)
        db.commit()
    return True


# ---------------------------------------------------------------------------
# Retroactive Application
# ---------------------------------------------------------------------------

def apply_rules_to_uncategorized() -> dict[str, Any]:
    """Apply rules to all postings that currently lack a categorized allocation.

    This is useful when:
    - New rules have been added
    - Rules have been modified
    - Existing postings were imported without categorization

    Only postings with NO allocation, or whose allocations point to
    the default "diverse|ikke-kategoriseret" category, are processed.
    """
    from app.models.all_models import Household, current_household_id

    now = _utcnow_iso()
    categorized = 0
    skipped = 0

    target_households: list[str] = []
    with contextlib.suppress(LookupError):
        current_hh = current_household_id.get()
        if current_hh:
            target_households = [current_hh]

    if not target_households:
        with Session(engine) as db:
            hhs = db.exec(select(Household.id)).all()
            target_households = list(hhs)

    with Session(engine) as db:
        active_rules = db.exec(
            select(CategorizationRule)
            .where(CategorizationRule.is_active == True)  # noqa: E712
            .order_by(
                col(CategorizationRule.source).desc(),
                col(CategorizationRule.priority).asc(),
            )
        ).all()

    for hh_id in target_households:
        token = current_household_id.set(hh_id)
        try:
            with Session(engine) as db:
                postings = db.exec(select(Posting)).all()
                all_allocs = db.exec(select(PostingAllocation)).all()

                allocs_by_posting: dict[str, list[PostingAllocation]] = {}
                for a in all_allocs:
                    allocs_by_posting.setdefault(a.posting_id, []).append(a)

                for posting in postings:
                    allocs = allocs_by_posting.get(posting.id, [])

                    has_real_category = any(
                        a.category_id and a.category_id not in ("diverse|ikke-kategoriseret", "diverse|ukategoriseret")
                        for a in allocs
                    )
                    if has_real_category:
                        skipped += 1
                        continue

                    # If splits exist with all un-categorized, categorize the splits
                    if len(allocs) > 1:
                        all_uncat = all(
                            not a.category_id or a.category_id in ("diverse|ikke-kategoriseret", "diverse|ukategoriseret")
                            for a in allocs
                        )
                        if all_uncat:
                            matched_category = evaluate_posting(posting, rules=active_rules)
                            if matched_category:
                                for a in allocs:
                                    a.category_id = matched_category
                                    a.updated_at = now
                                    db.add(a)
                                categorized += 1
                                continue
                        skipped += 1
                        continue

                    # Try to match a rule
                    matched_category = evaluate_posting(posting, rules=active_rules)
                    if matched_category is None:
                        skipped += 1
                        continue

                    if allocs:
                        alloc = allocs[0]
                        alloc.category_id = matched_category
                        alloc.updated_at = now
                        db.add(alloc)
                    else:
                        db.add(PostingAllocation(
                            posting_id=posting.id,
                            category_id=matched_category,
                            amount_minor=posting.amount_minor,
                            created_at=now,
                            updated_at=now,
                        ))

                    categorized += 1

                db.commit()
        finally:
            current_household_id.reset(token)

    # Now detect and categorize internal transfers
    from app.services.transfer_service import detect_internal_transfers
    transfer_results = detect_internal_transfers()

    return {
        "categorized": categorized,
        "skipped": skipped,
        "total_processed": categorized + skipped,
        "transfers": transfer_results,
    }
