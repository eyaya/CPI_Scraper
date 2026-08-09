"""Parser for the Namibia Statistics Agency (NSA) Quarterly GDP tables workbook.

Unlike the other national-accounts files this one is transposed: each 'Table N'
sheet has time down the rows (col A = Year on the Q1 row, col B = Quarter 1..4)
and the industries / expenditure components across the columns.

Tables (from the workbook's Table of Contents):
  1,2   GDP by activity, current prices ($ million)         -> production level current
  3,4   GDP by activity, current prices, percentage share   -> production share
  5,6   GDP by activity, constant 2015 prices ($ million)   -> production level constant
  7,8   GDP by activity, constant prices, percentage growth -> production real growth (YoY)
  9     GDP by expenditure, current prices                  -> expenditure level current
  10    GDP by expenditure, current prices, share           -> expenditure share
  11    GDP by expenditure, constant 2015 prices            -> expenditure level constant
  12    GDP by expenditure, constant prices, growth         -> expenditure real growth (YoY)

The 'continue' tables (2,4,6,8) just carry more industry columns of the same
measure. Everything is as published by NSA; nothing is derived.
"""
from __future__ import annotations
import re
import pandas as pd

# table number -> (approach, measure, price_basis, unit)
_TABLES = {
    1:  ("production",  "level",      "current",  "NAD million"),
    2:  ("production",  "level",      "current",  "NAD million"),
    3:  ("production",  "share",      "current",  "percent"),
    4:  ("production",  "share",      "current",  "percent"),
    5:  ("production",  "level",      "constant", "NAD million"),
    6:  ("production",  "level",      "constant", "NAD million"),
    7:  ("production",  "growth_yoy", "constant", "percent"),
    8:  ("production",  "growth_yoy", "constant", "percent"),
    9:  ("expenditure", "level",      "current",  "NAD million"),
    10: ("expenditure", "share",      "current",  "percent"),
    11: ("expenditure", "level",      "constant", "NAD million"),
    12: ("expenditure", "growth_yoy", "constant", "percent"),
}

_OUT_COLS = ["approach", "category", "category_group", "series_code", "geography",
             "period", "frequency", "price_basis", "seasonal_adjustment",
             "measure", "value", "unit", "base_period"]


def _norm(x):
    if x is None or (isinstance(x, float) and pd.isna(x)):
        return ""
    return re.sub(r"\s+", " ", str(x)).strip()


def _parse_table(df, approach, measure, basis, unit):
    # header row = the one whose first cell is 'Year'
    hdr = None
    for i in range(min(6, len(df))):
        if _norm(df.iat[i, 0]).lower() == "year":
            hdr = i
            break
    if hdr is None:
        raise ValueError("no 'Year' header row")
    # industry columns: col >= 2 with a non-empty header
    cols = {c: _norm(df.iat[hdr, c]) for c in range(2, df.shape[1])
            if _norm(df.iat[hdr, c])}
    base = "constant 2015 prices" if basis == "constant" else ""

    rows, year = [], None
    for r in range(hdr + 1, len(df)):
        y = _norm(df.iat[r, 0])
        if re.match(r"^\d{4}$", y):
            year = y
        q = _norm(df.iat[r, 1])
        qm = re.match(r"^([1-4])$", q)
        if not (year and qm):
            continue
        period = f"{year}-Q{qm.group(1)}"
        for c, label in cols.items():
            v = pd.to_numeric(df.iat[r, c], errors="coerce")
            if pd.isna(v):
                continue
            l = label.lower()
            row_ap = "aggregate" if ("gross domestic product" in l or l == "gdp"
                                     or "gdp at market" in l) else approach
            rows.append({
                "approach": row_ap, "category": label, "category_group": "",
                "series_code": "", "geography": "National", "period": period,
                "frequency": "quarterly", "price_basis": basis,
                "seasonal_adjustment": "nsa", "measure": measure,
                "value": float(v), "unit": unit, "base_period": base,
            })
    return rows


def parse(xlsx_path: str) -> pd.DataFrame:
    xl = pd.ExcelFile(xlsx_path)
    rows = []
    for n, (approach, measure, basis, unit) in _TABLES.items():
        sheet = f"Table {n}"
        if sheet not in xl.sheet_names:
            continue
        df = pd.read_excel(xlsx_path, sheet_name=sheet, header=None, dtype=str)
        rows.extend(_parse_table(df, approach, measure, basis, unit))
    if not rows:
        raise ValueError("no GDP rows parsed from Namibia workbook")
    return pd.DataFrame.from_records(rows)[_OUT_COLS]
