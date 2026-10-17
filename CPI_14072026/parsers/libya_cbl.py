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

from .ihpc_note_pdf import over_issues

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


_PAGE_BASE = re.compile(r"(?:100\s*=\s*(\d{4})|(\d{4})\s*=\s*100)")
_MONTHS_FULL = ["january", "february", "march", "april", "may", "june", "july",
                "august", "september", "october", "november", "december"]
# year-grid rate cells print a trailing minus ('2.3-' = -2.3)
_GRID_NUM = re.compile(r"(\d+\.\d+)(-?)")


def _parse_one(pdf_path: str) -> pd.DataFrame:
    """Every page, each on the base IT states ('100=2008', '2024=100').

    1. 'Consumer Price Index by Commodity Groups' rows (Mon-YY + 12 groups +
       Overall [+ annual inflation]) -- the COICOP table. A page whose rows
       carry fewer than 13 numbers (the 2004-2008 file's 8-group table, a
       different classification) is not read as COICOP.
    2. The all-items year grid ('Month | 2009 CPI, rate | 2010 CPI, rate | …')
       of the back-series files, for months no group table covers (2004-2008).
    """
    with pdfplumber.open(pdf_path) as pdf:
        pages = [p.extract_text() or "" for p in pdf.pages]
    records, seen = [], set()
    for text in pages:
        b = _PAGE_BASE.search(text)
        base = f"{b.group(1) or b.group(2)} = 100" if b else _BASE_PERIOD
        for ln in text.splitlines():
            m = _ROW.match(ln)
            if not m:
                continue
            mm = _MON.get(m.group(1).lower())
            if not mm:
                continue
            nums = _NUM.findall(ln)
            if len(nums) < 13:                      # 12 groups + Overall
                continue
            period = f"20{m.group(2)}-{mm}"
            if period in seen:
                continue
            seen.add(period)
            vals = [float(x) for x in nums]
            for i, (code, label) in enumerate(_COLS):
                records.append((code, label, period, "index", round(vals[i], 4),
                                "Index", base))
            if len(nums) >= 14:                     # trailing overall annual inflation
                records.append(("00", "Overall index (All items)", period,
                                "inflation_yoy", round(vals[13], 4), "percent", ""))
    for text in pages:
        b = _PAGE_BASE.search(text)
        lines = text.splitlines()
        hdr = next((ln for ln in lines[:4]
                    if re.fullmatch(r"\s*(20\d\d\s+){1,4}20\d\d\s*", ln)), None)
        if not b or not hdr:
            continue
        years = hdr.split()
        for ln in lines:
            w = ln.split()
            if not w or w[0].lower() not in _MONTHS_FULL:
                continue
            cells = _GRID_NUM.findall(" ".join(w[1:]))
            if len(cells) != 2 * len(years):
                continue
            mm = _MONTHS_FULL.index(w[0].lower()) + 1
            for k, y in enumerate(years):
                period = f"{y}-{mm:02d}"
                if period in seen:
                    continue
                cpi, (rate, neg) = float(cells[2 * k][0]), cells[2 * k + 1]
                records.append(("00", "Overall index (All items)", period, "index",
                                cpi, "Index", f"{b.group(1) or b.group(2)} = 100"))
                records.append(("00", "Overall index (All items)", period,
                                "inflation_yoy", -float(rate) if neg else float(rate),
                                "percent", ""))
    if not records:
        raise ValueError("Libya CPI: no monthly rows parsed")
    out = pd.DataFrame.from_records(
        records, columns=["coicop_code", "coicop_label", "period", "measure",
                          "value", "unit", "base_period"])
    out = out.drop_duplicates(["coicop_code", "period", "measure"])
    out["geography"] = "National"
    out["frequency"] = "monthly"
    return out


# Back series (`extras`): newest file wins on a shared period, so 2024 is kept
# on base 2024 (the current file), not on base 2008 (the 2009-Dec2024 file).
parse = over_issues(_parse_one, "libya_cbl")
