"""COICOP 2018 division reference (the classification Stats SA and most
modern African NSOs now use for CPI).

`DIVISIONS` maps the 2-digit division code to the canonical COICOP 2018 label.
Individual sources may use slightly different wording (we keep the source's own
label in `coicop_label`); this table is for cross-country standardisation later.
"""

DIVISIONS = {
    "00": "All items",
    "01": "Food and non-alcoholic beverages",
    "02": "Alcoholic beverages, tobacco and narcotics",
    "03": "Clothing and footwear",
    "04": "Housing, water, electricity, gas and other fuels",
    "05": "Furnishings, household equipment and routine household maintenance",
    "06": "Health",
    "07": "Transport",
    "08": "Information and communication",
    "09": "Recreation, sport and culture",
    "10": "Education services",
    "11": "Restaurants and accommodation services",
    "12": "Insurance and financial services",
    "13": "Personal care, social protection and miscellaneous goods and services",
}

# Number of divisions incl. "All items" — used as a validation floor.
N_DIVISIONS = len(DIVISIONS)  # 14


import re as _re

# (code, predicate on normalised lowercase label). startswith keeps e.g.
# 'all items less food...' or 'housing (rent)' from matching the wrong division.
_LABEL_RULES = [
    ("00", lambda s: s in ("total", "all items", "all groups", "overall",
                           "overall index", "all products", "general index")
                     or s.startswith("all item") or s.startswith("all product")),
    ("01", lambda s: s.startswith("food and non")),
    ("02", lambda s: s.startswith("alcoholic beverages")),
    ("03", lambda s: s.startswith("clothing")),
    ("04", lambda s: s.startswith("housing") and "(rent)" not in s),
    ("05", lambda s: s.startswith("furnishing")),
    ("06", lambda s: s.startswith("health")),
    ("07", lambda s: s.startswith("transport")),
    ("08", lambda s: s.startswith("information and communication")),
    ("09", lambda s: s.startswith("recreation")),
    ("10", lambda s: s.startswith("education")),
    ("11", lambda s: s.startswith("restaurant")),
    ("12", lambda s: s.startswith("insurance")),
    ("13", lambda s: s.startswith("personal care")),
]


def code_for_label(label: str) -> str | None:
    """Map a COICOP-2018 division label (any common NSO wording) to its
    2-digit code, or None if it isn't a top-level division. Shared by parsers."""
    s = _re.sub(r"\s+", " ", str(label).replace("\n", " ")).strip().rstrip(".").lower()
    for code, pred in _LABEL_RULES:
        if pred(s):
            return code
    return None
