"""Parser for the Nigeria NBS CPI data workbook (cpi_1New_*.xlsx), sheet
'Table2' = national ("Composite") index.

Layout:
  - col 0 = year (only on each January row), col 1 = month name.
  - Row 2 = category headers; row 3 = weights; data from row 4.
  - Columns 2..13 are special aggregates (All Items, Core, Food, Energy...);
    columns 14..26 are the 13 COICOP-2018 divisions.

We select All-items + the 13 divisions by matching the HEADER TEXT (not fixed
column positions), so the parser survives column reordering between months.
The series is post-2024-rebasing, base 2024 = 100, from Jan 2023.
"""
from __future__ import annotations
import re
import pandas as pd

SHEET = "Table2"
_MONTHS = {
    "jan": "01", "feb": "02", "mar": "03", "apr": "04", "may": "05", "jun": "06",
    "jul": "07", "aug": "08", "sep": "09", "oct": "10", "nov": "11", "dec": "12",
}

# (division code, predicate on the cleaned lowercase header). startswith is used
# so e.g. 'ALLITEMS LESS FOOD AND NON ALCOHOLIC...' does not match division 01,
# and 'HOUSING (RENT) INDEX' does not match division 04.
_RULES = [
    ("00", lambda s: s == "all items"),
    ("01", lambda s: s.startswith("food and non")),
    ("02", lambda s: s.startswith("alcoholic beverages")),
    ("03", lambda s: s.startswith("clothing")),
    ("04", lambda s: s.startswith("housing, water")),
    ("05", lambda s: s.startswith("furnishings")),
    ("06", lambda s: s.startswith("health")),
    ("07", lambda s: s.startswith("transport")),
    ("08", lambda s: s.startswith("information and communication")),
    ("09", lambda s: s.startswith("recreation")),
    ("10", lambda s: s.startswith("education")),
    ("11", lambda s: s.startswith("restaurant")),
    ("12", lambda s: s.startswith("insurance")),
    ("13", lambda s: s.startswith("personal care")),
]


def _clean(h) -> str:
    return re.sub(r"\s+", " ", str(h).replace("\n", " ")).strip()


def parse(xlsx_path: str) -> pd.DataFrame:
    df = pd.read_excel(xlsx_path, sheet_name=SHEET, header=None, dtype=object)
    header = df.iloc[1]

    # map division code -> (column index, source label)
    codemap: dict[str, tuple[int, str]] = {}
    for j, h in header.items():
        if h is None or (isinstance(h, float) and pd.isna(h)):
            continue
        s = _clean(h)
        low = s.lower()
        for code, pred in _RULES:
            if code not in codemap and pred(low):
                codemap[code] = (j, s.rstrip("."))
                break
    if len(codemap) < 14:
        missing = [c for c, _ in _RULES if c not in codemap]
        raise ValueError(f"could not locate division columns: {missing}")

    records = []
    year = None
    for i in range(3, len(df)):
        y = df.iat[i, 0]
        m = df.iat[i, 1]
        if pd.notna(y) and str(y).strip():
            year = str(y).strip().split(".")[0]  # '2023' / 2023.0 -> '2023'
        if pd.isna(m):
            continue
        mkey = str(m).strip().lower()[:3]
        if mkey not in _MONTHS or year is None:
            continue
        period = f"{year}-{_MONTHS[mkey]}"
        for code, (j, label) in codemap.items():
            v = pd.to_numeric(df.iat[i, j], errors="coerce")
            if pd.notna(v):
                records.append(
                    {
                        "coicop_code": code,
                        "coicop_label": label,
                        "geography": "National",
                        "period": period,
                        "value": v,
                    }
                )

    out = pd.DataFrame.from_records(records)
    out["measure"] = "index"
    out["unit"] = "Index"
    out["base_period"] = "2024 = 100"
    out["frequency"] = "monthly"
    return out
