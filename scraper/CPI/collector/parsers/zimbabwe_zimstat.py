"""Parser for the ZimStat 'Weighted CPI' workbook (Tier 2, Excel from the WP site).

Since 2024 ZimStat's headline is the Weighted (blended) CPI, base April 2024 = 100.
The 'CPI 2' sheet is a wide monthly index series: col 0 the division label, col 1
the weight, and a datetime period header on row 2 over the index columns:

  <label>            <weight>  2024-04  2024-05  …  2026-04
  Food & Non Alcoholic Beverages  31.3  100  98.10  …  …
  All  Items                      100   100  …

We capture the 12 COICOP-1999 divisions + 'All Items' as index for every reported
month. Rows are matched by keyword on first occurrence, so the analytical Food /
Non-food aggregates at the bottom never shadow a division.
"""
from __future__ import annotations
import pandas as pd

_SHEET = "CPI 2"
_BASE_PERIOD = "April 2024 = 100"
# (code, canonical label, keyword) — first matching row wins
_DIVS = [
    ("00", "All items", "all items"),
    ("01", "Food and non-alcoholic beverages", "food & non"),
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


def parse(xlsx_path: str) -> pd.DataFrame:
    df = pd.ExcelFile(xlsx_path).parse(_SHEET, header=None)
    # period header: the row whose columns (from col 2) parse as dates
    periods, hdr_row = {}, None
    for r in range(min(6, df.shape[0])):
        mp = {c: pd.to_datetime(df.iloc[r, c], errors="coerce")
              for c in range(2, df.shape[1])}
        mp = {c: ts.strftime("%Y-%m") for c, ts in mp.items() if pd.notna(ts)}
        if len(mp) >= 6:
            periods, hdr_row = mp, r
            break
    if not periods:
        raise ValueError("Zimbabwe CPI: period header not found")

    records = []
    for code, label, kw in _DIVS:
        hit = next((r for r in range(hdr_row + 1, df.shape[0])
                    if kw in _norm(df.iloc[r, 0])), None)
        if hit is None:
            raise ValueError(f"Zimbabwe CPI: missing division {code} ({kw})")
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
