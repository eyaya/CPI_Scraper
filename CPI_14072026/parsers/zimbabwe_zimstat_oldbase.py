"""ZimStat blended CPI on the OLD base (August 2023 = 100), before the ZiG rebase.

The current parser (`zimbabwe_zimstat.py`) reads the Weighted CPI, base April
2024 = 100, which starts in April 2024. The last headline workbook before the
rebase -- `CPI_02_2024.xls` (February 2024) -- carries the blended series on the
previous base in sheet 'CPI 1' ("Consumer Price Index (Aug 2023=100)"), from
JUNE 2019:

    row 2   header: 12 COICOP-1999 division names, 'All Items', inflation columns
    row 3   'Weights'
    then    annual-average rows (year only, no month)  -- not read
            monthly rows: <year on the first row of each year> <Mon> <indices>

Only rows carrying a MONTH are read; the year-only rows are annual averages, a
different statistic. Columns are matched on ZimStat's own header text, never by
position. Monthly/annual inflation columns are not read (inflation is published
by the current series; the old-base rates are not re-derived).

NOT CHAINED. The CPI merge key has no base_period, so old-base rows are emitted
only for months BEFORE the current series begins (`before`, passed by the
caller). The series breaks there (March 2024 is in neither workbook).

CROSS-CHECK: All Items Aug 2023 = 100; Dec 2022 = 89.489894; Feb 2024 =
127.173091 (annual inflation printed beside it: 47.62%).
"""
from __future__ import annotations
import re
import pandas as pd

SHEET = "CPI 1"
BASE = "August 2023 = 100"
_MONTHS = {"jan": "01", "feb": "02", "mar": "03", "apr": "04", "may": "05",
           "jun": "06", "jul": "07", "aug": "08", "sep": "09", "oct": "10",
           "nov": "11", "dec": "12"}
# (code, canonical label, keyword in ZimStat's header) -- same labels as the
# current parser, so a division reads the same across the break.
_DIVS = [
    ("00", "All items", "all items"),
    ("01", "Food and non-alcoholic beverages", "food and non"),
    ("02", "Alcoholic beverages and tobacco", "tobacco"),
    ("03", "Clothing and footwear", "clothing"),
    ("04", "Housing, water, electricity, gas and other fuels", "housing"),
    ("05", "Furnishings, household equipment and routine maintenance", "furniture"),
    ("06", "Health", "health"),
    ("07", "Transport", "transport"),
    ("08", "Communication", "communication"),
    ("09", "Recreation and culture", "recreation"),
    ("10", "Education", "education"),
    ("11", "Restaurants and hotels", "restaurant"),
    ("12", "Miscellaneous goods and services", "miscellaneous"),
]


def _norm(s) -> str:
    return " ".join(str(s).lower().split())


def is_old_base(path: str) -> bool:
    """True when the workbook's 'CPI 1' sheet is the Aug-2023-base series."""
    try:
        df = pd.read_excel(path, sheet_name=SHEET, header=None, nrows=1)
    except Exception:                                      # noqa: BLE001
        return False
    return "aug 2023=100" in _norm(df.iloc[0, 0]).replace(" =", "=").replace("= ", "=")


def parse(path: str, before: str | None = None) -> pd.DataFrame:
    df = pd.read_excel(path, sheet_name=SHEET, header=None)
    hdr = next((r for r in range(min(8, len(df)))
                if any("all items" in _norm(v) for v in df.iloc[r])), None)
    if hdr is None:
        raise ValueError("ZimStat old-base CPI 1: header row not found")
    cols = {}
    for code, _, kw in _DIVS:
        hits = [c for c in range(df.shape[1]) if kw in _norm(df.iloc[hdr, c])]
        if len(hits) != 1:
            raise ValueError(f"ZimStat old-base CPI 1: division {code} ({kw!r}) "
                             f"matches {len(hits)} columns")
        cols[code] = hits[0]

    records, year = [], None
    for r in range(hdr + 1, len(df)):
        y, m = df.iat[r, 0], df.iat[r, 1]
        if pd.notna(y) and re.fullmatch(r"(19|20)\d\d(\.0)?", str(y).strip()):
            year = str(y).strip()[:4]
        mkey = _norm(m)[:3] if pd.notna(m) else ""
        if mkey not in _MONTHS or year is None:
            continue                       # annual-average or blank row
        period = f"{year}-{_MONTHS[mkey]}"
        if before and period >= before:
            continue
        for code, label, _ in _DIVS:
            v = df.iat[r, cols[code]]
            if pd.notna(v) and isinstance(v, (int, float)):
                records.append((code, label, period, round(float(v), 4)))
    if not records:
        raise ValueError("ZimStat old-base CPI 1: no monthly rows read")
    out = pd.DataFrame.from_records(
        records, columns=["coicop_code", "coicop_label", "period", "value"])
    out["measure"] = "index"
    out["unit"] = "Index"
    out["base_period"] = BASE
    out["geography"] = "National"
    out["frequency"] = "monthly"
    return out
