"""Parser for the NBS Seychelles 'Consumer Price Index Time Series' workbook (Tier 2).

The 'CPI_Series' sheet stacks several blocks (index, then % changes, weights, …)
that all repeat the same row labels. The first (top) block is the index. Its rows
carry the 12 COICOP-1999 divisions + 'ALL ITEMS', laid out under a Food / Non-food
grouping with detailed sub-items in between:

  <label>  <weight> <weight(1)>  Jan2007  Feb2007  …  Feb2026
  FOOD AND NON-ALCOHOLIC BEVERAGE  28.875 …  41.77 …  120.76
  ALL ITEMS  …  100 …  127.21

Period header: row 2 = month, row 3 = year; only true month columns are kept
(weight columns are interleaved). We take each division's FIRST occurrence (the
index block) and emit the index for every reported month. Base 2014 = 100.
"""
from __future__ import annotations
import re
import unicodedata
import pandas as pd

_SHEET = "CPI_Series"
_BASE_PERIOD = "2014 = 100"
_MON = {"jan": "01", "feb": "02", "mar": "03", "apr": "04", "may": "05", "jun": "06",
        "jul": "07", "aug": "08", "sep": "09", "oct": "10", "nov": "11", "dec": "12"}
# (code, canonical label, keyword) — first matching row wins; index block is first.
_DIVS = [
    ("00", "All items", "all items"),
    ("01", "Food and non-alcoholic beverages", "food and non-alcoholic"),
    ("02", "Alcoholic beverages and tobacco", "alcoholic beverages and tobacco"),
    ("03", "Clothing and footwear", "clothing"),
    ("04", "Housing, water, electricity, gas and other fuels", "housing"),
    ("05", "Furnishings, household equipment and routine maintenance", "furniture"),
    ("06", "Health", "health"),
    ("07", "Transport", "transport"),
    ("08", "Communication", "communication"),
    ("09", "Recreation and culture", "recreation"),
    ("10", "Education", "education"),
    ("11", "Restaurants and hotels", "restaurants"),
    ("12", "Miscellaneous goods and services", "miscellaneous"),
]


def _norm(s) -> str:
    s = unicodedata.normalize("NFKD", str(s)).encode("ascii", "ignore").decode()
    return re.sub(r"\s+", " ", s).strip().lower()


def _mm(x):
    return _MON.get(str(x).strip().lower()[:3])


def parse(xlsx_path: str) -> pd.DataFrame:
    df = pd.ExcelFile(xlsx_path).parse(_SHEET, header=None)
    # period columns: a real month name in row 2 and a 20xx year in row 3
    periods = {}
    for c in range(3, df.shape[1]):
        mm, yr = _mm(df.iloc[2, c]), str(df.iloc[3, c]).strip()
        if mm and re.fullmatch(r"20\d\d", yr):
            periods[c] = f"{yr}-{mm}"
    if len(periods) < 12:
        raise ValueError("Seychelles CPI: period header not found")

    records = []
    for code, label, kw in _DIVS:
        hit = next((r for r in range(df.shape[0]) if kw in _norm(df.iloc[r, 0])), None)
        if hit is None:
            raise ValueError(f"Seychelles CPI: missing division {code} ({kw})")
        for c, period in periods.items():
            v = df.iloc[hit, c]
            if pd.notna(v) and isinstance(v, (int, float)):
                records.append((code, label, period, "index", round(float(v), 4),
                                "Index", _BASE_PERIOD))

    out = pd.DataFrame.from_records(
        records, columns=["coicop_code", "coicop_label", "period", "measure",
                          "value", "unit", "base_period"])
    out["geography"] = "National"
    out["frequency"] = "monthly"
    return out
