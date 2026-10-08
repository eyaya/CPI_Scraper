"""Parser for the NBS Seychelles Quarterly National Accounts workbook.

The 'Tables 1-6' sheet stacks six by-industry GDP tables. Each begins with a
'Table N:' caption, then a header whose col A / col B are 'Year' / 'Quarter' and
whose remaining columns are the industrial activities; the data rows carry the
year (on the Q1 row) + quarter and one value per activity.

Tables:
  1 GDP in current prices by activity        -> production level current
  2 GDP in constant prices (base 2014)        -> production level constant
  3 % change, current prices                  -> production nominal YoY growth
  4 % change, constant prices                 -> production real YoY growth
  5 Point contribution to real GDP growth     -> contribution
  6 Implicit price deflator                    -> deflator

Values are SCR million (levels) / percent (growth) / index (deflator). The
expenditure tables (7-8, a different transposed layout) are left for a later pass.
Everything as published; nothing derived.
"""
from __future__ import annotations
import re
import pandas as pd

_CAPTION_RE = re.compile(r"table\s*(\d)\s*:", re.I)

# caption keyword -> (measure, price_basis, unit). Order matters: the specific
# growth/contribution/deflator captions must be tested before the level captions
# (a '% change in constant prices' caption also contains 'constant prices').
_SPECS = [
    ("percentage change in quarterly gdp in current", ("growth_yoy", "current", "percent")),
    ("percentage change in quarterly gdp in constant", ("growth_yoy", "constant", "percent")),
    ("contribution to real gdp growth", ("contribution", "constant", "percentage points")),
    ("implicit price deflator", ("deflator", "not_applicable", "index")),
    ("current prices", ("level", "current", "SCR million")),
    ("constant prices", ("level", "constant", "SCR million")),
]

_OUT_COLS = ["approach", "category", "category_group", "series_code", "geography",
             "period", "frequency", "price_basis", "seasonal_adjustment",
             "measure", "value", "unit", "base_period"]


def _cell(df, r, c):
    v = df.iat[r, c] if c < df.shape[1] else None
    return "" if v is None or (isinstance(v, float) and pd.isna(v)) else str(v).strip()


def _spec_for(caption: str):
    c = caption.lower()
    for key, spec in _SPECS:
        if key in c:
            return spec
    return None


def _parse_block(df, top, end, measure, basis, unit):
    # header row within the block: col A starts with 'Year' (or 'Year on Year'
    # on the percentage-change tables)
    hdr = None
    for r in range(top, min(end, top + 6)):
        if _cell(df, r, 0).lower().startswith("year"):
            hdr = r
            break
    if hdr is None:
        return []
    activities = {c: re.sub(r"\s+", " ", _cell(df, hdr, c)).strip()
                  for c in range(2, df.shape[1]) if _cell(df, hdr, c)}
    base = "base 2014" if basis == "constant" else ""
    rows, year = [], None
    for r in range(hdr + 1, end):
        y = _cell(df, r, 0)
        m = re.match(r"(20\d\d)", y)    # '2015' or the YoY pair '2015/2014'
        if m:
            year = m.group(1)
        q = _cell(df, r, 1)
        if not (year and re.fullmatch(r"Q[1-4]", q)):
            continue
        period = f"{year}-{q}"
        for c, activity in activities.items():
            v = pd.to_numeric(_cell(df, r, c), errors="coerce")
            if pd.isna(v):
                continue
            low = activity.lower()
            approach = "aggregate" if ("gdp" in low or "gross domestic" in low
                                       or low.startswith("total")) else "production"
            rows.append({
                "approach": approach, "category": activity, "category_group": "",
                "series_code": "", "geography": "National", "period": period,
                "frequency": "quarterly", "price_basis": basis,
                "seasonal_adjustment": "nsa", "measure": measure,
                "value": float(v), "unit": unit, "base_period": base,
            })
    return rows


def parse(xlsx_path: str) -> pd.DataFrame:
    df = pd.read_excel(xlsx_path, sheet_name="Tables 1-6", header=None, dtype=str)
    caps = [(r, _cell(df, r, 0)) for r in range(len(df))
            if _CAPTION_RE.match(_cell(df, r, 0))]
    caps.append((len(df), ""))
    rows = []
    for i in range(len(caps) - 1):
        top, caption = caps[i]
        end = caps[i + 1][0]
        spec = _spec_for(caption)
        if spec:
            rows.extend(_parse_block(df, top + 1, end, *spec))
    if not rows:
        raise ValueError("no GDP rows parsed from NBS Seychelles workbook")
    return pd.DataFrame.from_records(rows)[_OUT_COLS].drop_duplicates(
        ["approach", "category", "period", "measure", "price_basis"])
