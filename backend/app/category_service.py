"""Category service — seeds and queries the taxonomy from the Category table."""
from __future__ import annotations

import re
from typing import Any

from sqlmodel import Session, select

from .database import Category, Transaction, engine

# ---------------------------------------------------------------------------
# Default Taxonomy
# ---------------------------------------------------------------------------

DEFAULT_TAXONOMY: dict[str, list[str]] = {
    "Bolig": [
        "Boliglån/husleje", "El, vand, varme & renovation", "Ejerforening",
        "Ejendomsskat", "Husforsikring", "Indbo- & familieforsikring",
        "Alarmsystem", "Udgifter fritidshus", "Ombygning & vedligehold",
        "Have & planter", "Andre boligudgifter",
    ],
    "Transport": [
        "Bil-, MC-, bådlån o.l.", "Brændstof", "Bilforsikring & autohjælp",
        "Ejerafgift/grøn afgift", "Bus, tog, færge o.l.", "Taxi", "Parkering",
        "Værksted & reservedele", "Anden transport",
    ],
    "Husholdning": [
        "Dagligvarer", "Kiosk, bager & specialbutikker",
        "Kantine- & frokostordning",
    ],
    "Andre leveomkostninger": [
        "Apotek & medicin", "Behandling & læger", "Underholds- & børnebidrag",
        "Institution", "Fagforening & a-kasse", "Livs- & ulykkesforsikring",
        "Sundheds- & sygeforsikring", "Briller & kontaktlinser",
        "TV & streaming", "Telefoni & internet", "Studieudgifter",
        "Foreninger & kontingenter",
    ],
    "Privatforbrug": [
        "Fastfood & takeaway", "Bar, cafe & restaurant",
        "Tøj, sko & accessories", "Møbler & boligudstyr",
        "Elektronik & computerudstyr", "Film, musik & læsestof",
        "Online services & software", "Hobby & sportsudstyr",
        "Biograf, koncerter & forlystelser", "Frisør & personlig pleje",
        "Sport & fritid", "Hus & havehjælp", "Spil & legetøj",
        "Tips & lotto", "Babyudstyr", "Kæledyr", "Gaver & velgørenhed",
        "Tobak & alkohol", "Kontanthævning & check",
        "Højskole- & kursusophold", "Serviceydelser & rådgivning",
        "Andet privatforbrug",
    ],
    "Ferie": [
        "Fly & Hotel", "Billeje", "Sommerhus & camping",
        "Ferieaktiviteter", "Rejseforsikring",
    ],
    "Diverse": [
        "Ukendt", "Bankgebyrer", "Rykkergebyrer", "Bøder & afgifter",
        "Restskat", "Offentligt gebyr", "Ikke kategoriseret",
    ],
    "Lån & gæld": [
        "Studielån", "Forbrugslån", "Private lån (venner & familie)",
        "Udlånsrenter",
    ],
    "Pension & Opsparing": [
        "Pensionsopsparing", "Børneopsparing", "Anden opsparing",
        "Værdipapirshandel",
    ],
    "Indkomst": [
        "Løn", "Pensionsudbetaling", "Dagpenge/overførselsindkomst",
        "SU & studielån", "Børnepenge", "Underholds- & børnebidrag",
        "Feriepenge", "Renteindtægter", "Udbytte & afkast",
        "Overskydende skat", "Boligstøtte", "Anden indkomst",
    ],
    "Vis ikke": ["Kontooverførsel", "Udlæg", "Ignorer"],
}

INCOME_MAIN_CATEGORIES = {"Indkomst"}
EXCLUDED_MAIN_CATEGORIES = {"Vis ikke"}

_SLUG_RE = re.compile(r"[^a-z0-9æøå]+")


def _slugify(text: str) -> str:
    return _SLUG_RE.sub("-", text.lower()).strip("-") or "unknown"


def make_category_id(main_name: str, sub_name: str) -> str:
    return f"{_slugify(main_name)}|{_slugify(sub_name)}"


# ---------------------------------------------------------------------------
# Seed
# ---------------------------------------------------------------------------

def seed_categories() -> int:
    """Insert default taxonomy into the Category table. Idempotent."""
    count = 0
    with Session(engine) as db:
        for main_name, subs in DEFAULT_TAXONOMY.items():
            cat_type = "Income" if main_name in INCOME_MAIN_CATEGORIES else "Expense"
            for sub_name in subs:
                cat_id = make_category_id(main_name, sub_name)
                existing = db.get(Category, cat_id)
                if existing is None:
                    db.add(Category(
                        id=cat_id,
                        main_name=main_name,
                        sub_name=sub_name,
                        category_type=cat_type,
                    ))
                    count += 1
        db.commit()
    return count


# ---------------------------------------------------------------------------
# Query
# ---------------------------------------------------------------------------

def list_categories() -> list[dict[str, Any]]:
    """Return the full taxonomy grouped by main category."""
    with Session(engine) as db:
        categories = db.exec(
            select(Category).order_by(Category.main_name, Category.sub_name)
        ).all()

    return [
        {
            "id": cat.id,
            "mainCategoryName": cat.main_name,
            "categoryName": cat.sub_name,
            "categoryType": cat.category_type,
        }
        for cat in categories
    ]


def get_taxonomy_response() -> dict[str, Any]:
    """Build the taxonomy response expected by the frontend."""
    categories = list_categories()

    # Count actual usage per category from transactions
    usage_counts: dict[str, int] = {}
    with Session(engine) as db:
        rows = db.exec(
            select(Transaction.category_id)
            .where(Transaction.category_id.is_not(None))  # type: ignore[union-attr]
        ).all()
        for cat_id in rows:
            if cat_id:
                usage_counts[cat_id] = usage_counts.get(cat_id, 0) + 1

    for cat in categories:
        cat["usage_count"] = usage_counts.get(cat["id"], 0)
        cat["mainCategoryId"] = _slugify(cat["mainCategoryName"])
        cat["categoryId"] = cat["id"]
        cat["search_aliases"] = []

    return {
        "categories": categories,
        "hashtags": [],
    }
