"""Parser for the Central Bank of Libya (CBL) CPI workbook PDF (Tier 3, CB fallback).

Libya's NSO (Census & Statistics Dept.) has no reachable public site, so we use
the central bank, which republishes that department's official CPI without
re-estimating it. The 'Consumer Price Index by Commodity Groups' table (base
2024 = 100) is a wide monthly index series — one row per month, one column per
COICOP-1999 group plus an Overall Index:

  Month   Food  Tobacco  Clothing … Misc  Overall  [annual inflation %]
  Jan-24  100.0 100.0    100.0    … 100.0 100.0    -
  May-26  …                       …       115.8    14.0

Columns are in a fixed order (confirmed by the weights row), so we map by
position: the first 12 numbers are divisions 01–12 and the 13th is Overall (00).
The trailing annual-inflation column (Overall) is emitted as inflation_yoy for 00.
"""
from __future__ import annotations
import re
import pdfplumber
import pandas as pd

_BASE_PERIOD = "2024 = 100"
_MON = {"jan": "01", "feb": "02", "mar": "03", "apr": "04", "may": "05", "jun": "06",
        "jul": "07", "aug": "08", "sep": "09", "oct": "10", "nov": "11", "dec": "12"}
# fixed column order → (code, canonical label)
_COLS = [
    ("01", "Foods and beverages"),
    ("02", "Tobacco"),
    ("03", "Clothing and footwear"),
    ("04", "Housing, water, electricity, gas and other fuels"),
    ("05", "Furniture and household equipment"),
    ("06", "Health"),
    ("07", "Transport"),
    ("08", "Communication"),
    ("09", "Recreation and culture"),
    ("10", "Education"),
    ("11", "Restaurants and hotels"),
    ("12", "Miscellaneous goods and services"),
    ("00", "Overall index (All items)"),
]
_ROW = re.compile(r"^\s*([A-Za-z]{3})-(\d{2})\b")
_NUM = re.compile(r"-?\d+\.\d+")


def parse(pdf_path: str) -> pd.DataFrame:
    with pdfplumber.open(pdf_path) as pdf:
        text = "\n".join((p.extract_text() or "") for p in pdf.pages)

    records, seen = [], set()
    for ln in text.splitlines():
        m = _ROW.match(ln)
        if not m:
            continue
        mm = _MON.get(m.group(1).lower())
        if not mm:
            continue
        nums = _NUM.findall(ln)
        if len(nums) < 13:                          # 12 groups + Overall
            continue
        period = f"20{m.group(2)}-{mm}"
        if period in seen:
            continue
        seen.add(period)
        vals = [float(x) for x in nums]
        for i, (code, label) in enumerate(_COLS):
            records.append((code, label, period, "index", round(vals[i], 4),
                            "Index", _BASE_PERIOD))
        if len(nums) >= 14:                         # trailing overall annual inflation
            records.append(("00", "Overall index (All items)", period, "inflation_yoy",
                            round(vals[13], 4), "percent", ""))

    if not records:
        raise ValueError("Libya CPI: no monthly rows parsed")
    out = pd.DataFrame.from_records(
        records, columns=["coicop_code", "coicop_label", "period", "measure",
                          "value", "unit", "base_period"])
    out["geography"] = "National"
    out["frequency"] = "monthly"
    return out
