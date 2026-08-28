import re
import unicodedata

# Matches leading quantity and unit prefixes, e.g.:
# - "2 x DG SOLSIKKEBOLLER", "2x DG SOLSIKKEBOLLER", "2 X DG SOLSIKKEBOLLER"
# - "2* LETMÆLK", "2*LETMÆLK"
# - "3 stk. Øko Bananer", "3 stk BANANER", "3stk BANANER", "3 stykker Bananer"
# - "2 pk. GÆR", "2pk GÆR", "2 pakker Gær"
# - "3 fl. RØDVIN", "3 flasker Rødvin"
# - "6 ds. COCA COLA", "6 dåser Cola"
# - "2 bdt. FORÅRSLØG", "2 bundter forårsløg"
# - "2 pos. CARROTS", "2 poser gulerødder"
# - "2 ks. ØL", "2 kasser øl"
# - "2 stk. x GULD 45+ ML"
#
# Negative lookahead (?![a-zA-Z0-9]) on [xX] prevents false matches on:
# - "2XL T-SHIRT", "3XL TRØJE", "4X4 OFFROAD"
# Non-unit numbers like "3-STJERNET SALAMI", "7-UP", "84% CHOKOLADE", "1001 NAT THE" do not match.
QUANTITY_PREFIX_RE = re.compile(
    r"^\s*(\d+(?:[.,]\d+)?)\s*(?:stk\.?|stykker|pk\.?|pakker|fl\.?|flasker|ds\.?|dåser|pos\.?|poser|bdt\.?|bundter|ks\.?|kasser)?\s*(?:[xX](?![a-zA-Z0-9])|\*|(?:stk|stykker|pk|pakker|fl|flasker|ds|dåser|pos|poser|bdt|bundter|ks|kasser)\.?(?!\w))\s*",
    re.IGNORECASE,
)


def clean_item_name(name: str | None) -> str:
    """Strip leading quantity / multiplier prefixes from item name while preserving valid product names."""
    if not name:
        return ""
    normalized = unicodedata.normalize("NFKC", str(name)).strip()
    cleaned = QUANTITY_PREFIX_RE.sub("", normalized).strip()
    return cleaned if cleaned else normalized


def extract_quantity_and_clean_name(name: str | None) -> tuple[float | None, str]:
    """Extract numeric quantity if present as a leading multiplier and return (quantity, clean_name)."""
    if not name:
        return None, ""
    normalized = unicodedata.normalize("NFKC", str(name)).strip()
    match = QUANTITY_PREFIX_RE.match(normalized)
    if match:
        raw_qty = match.group(1).replace(",", ".")
        try:
            qty = float(raw_qty)
        except (ValueError, TypeError):
            qty = None
        cleaned = normalized[match.end():].strip()
        return qty, (cleaned if cleaned else normalized)
    return None, normalized
