"""Parser for the Uganda UBOS Quarterly GDP workbooks (current + constant prices).

UBOS publishes two Excel files per quarter — 'QGDP_Current_Prices_*.xlsx' and
'QGDP_Constant_Prices_*.xlsx'; parse() receives both paths and routes by filename.

Layout of the sheets used (all share a two-row header: a fiscal-year row followed
by a Q1..Q4 row, with the series label in the first non-period column):
  Original_VA           GDP by activity, value added        (level)
  Original_Expenditure  expenditure on GDP components       (level, current file)
  Original_%share       activity shares of GDP              (share, current file)

Uganda's fiscal year runs July–June, so a fiscal-quarter is mapped to the calendar
quarter it actually covers: FY2016/17 Q1 = Jul–Sep 2016 = 2016-Q3, Q2 = 2016-Q4,
Q3 = 2017-Q1, Q4 = 2017-Q2. Values are in UGX billion, as published — nothing is
derived. The constant-price growth/deflator sheets (mixed annual+quarterly layout)
and the seasonally-adjusted / trend sheets are left for a later pass.
"""
from __future__ import annotations
import os
import re
import pandas as pd

# fiscal-quarter -> (calendar-year offset from FY start, calendar quarter)
_FQ = {1: (0, 3), 2: (0, 4), 3: (1, 1), 4: (1, 2)}
_FY_RE = re.compile(r"^(20\d\d)/\d\d$")
_Q_RE = re.compile(r"^Q([1-4])$", re.I)

# sheet -> (approach, measure, price_basis, unit); by workbook
_CURRENT = {
    "Original_VA":          ("production",  "level", "current", "UGX billion"),
    "Original_Expenditure": ("expenditure", "level", "current", "UGX billion"),
    "Original_%share":      ("production",  "share", "current", "percent"),
}
_CONSTANT = {
    "Original_VA":          ("production",  "level", "constant", "UGX billion"),
}

_OUT_COLS = ["approach", "category", "category_group", "series_code", "geography",
             "period", "frequency", "price_basis", "seasonal_adjustment",
             "measure", "value", "unit", "base_period"]


def _norm(x):
    if x is None or (isinstance(x, float) and pd.isna(x)):
        return ""
    return re.sub(r"\s+", " ", str(x)).strip()


def _cal_period(fy_start: int, fq: int) -> str:
    off, cq = _FQ[fq]
    return f"{fy_start + off}-Q{cq}"


def _find_headers(df):
    """Return (label_col, {col:(period, 'quarterly')}) by locating the Q1..Q4 row
    and the fiscal-year row above it. label_col = first period col - 1."""
    q_row = None
    for i in range(min(8, len(df))):
        if sum(bool(_Q_RE.match(_norm(x))) for x in df.iloc[i].tolist()) >= 4:
            q_row = i
            break
    if q_row is None:
        raise ValueError("no Q1..Q4 header row")
    yr = [_norm(x) for x in df.iloc[q_row - 1].tolist()]
    qr = [_norm(x) for x in df.iloc[q_row].tolist()]
    pmap, cur = {}, None
    first_pcol = None
    for c in range(len(qr)):
        if c < len(yr) and _FY_RE.match(yr[c]):
            cur = int(yr[c][:4])
        qm = _Q_RE.match(qr[c])
        if cur and qm:
            pmap[c] = _cal_period(cur, int(qm.group(1)))
            if first_pcol is None:
                first_pcol = c
    if not pmap:
        raise ValueError("no period columns resolved")
    return max(0, first_pcol - 1), pmap


def _find_second_header(df, first_q_row):
    """Row index of the next Q1..Q4 header after the first block (some sheets
    stack a second '% of GDP' table below the levels table); len(df) if none."""
    for i in range(first_q_row + 1, len(df)):
        if sum(bool(_Q_RE.match(_norm(x))) for x in df.iloc[i].tolist()) >= 4:
            return i
    return len(df)


def _parse_sheet(df, approach, measure, basis, unit):
    label_col, pmap = _find_headers(df)
    q_row = next(i for i in range(len(df))
                 if sum(bool(_Q_RE.match(_norm(x))) for x in df.iloc[i].tolist()) >= 4)
    end = _find_second_header(df, q_row)             # stop before any stacked 2nd table
    base = "constant 2016/17 prices" if basis == "constant" else ""
    rows = []
    for r in range(end):
        label = _norm(df.iat[r, label_col])
        if not label or _FY_RE.match(label) or _Q_RE.match(label):
            continue
        if any(k in label.lower() for k in ("updated", "table ", "source", "accounts for")):
            continue
        l = label.lower()
        row_ap = "aggregate" if ("gdp at market" in l or "gross domestic product" in l) else approach
        for c, period in pmap.items():
            if c >= df.shape[1]:
                continue
            v = pd.to_numeric(df.iat[r, c], errors="coerce")
            if pd.isna(v):
                continue
            rows.append({
                "approach": row_ap, "category": label, "category_group": "",
                "series_code": "", "geography": "National", "period": period,
                "frequency": "quarterly", "price_basis": basis,
                "seasonal_adjustment": "nsa", "measure": measure,
                "value": float(v), "unit": unit, "base_period": base,
            })
    return rows


def _parse_workbook(path, sheets):
    xl = pd.ExcelFile(path)
    rows = []
    for sheet, (approach, measure, basis, unit) in sheets.items():
        if sheet in xl.sheet_names:
            df = pd.read_excel(path, sheet_name=sheet, header=None, dtype=str)
            rows.extend(_parse_sheet(df, approach, measure, basis, unit))
    return rows


def parse(paths) -> pd.DataFrame:
    if isinstance(paths, str):
        paths = [paths]
    paths = [p["path"] if isinstance(p, dict) else p for p in paths]
    rows = []
    for p in paths:
        fname = os.path.basename(p).lower()
        if "constant" in fname:
            rows += _parse_workbook(p, _CONSTANT)
        elif "current" in fname:
            rows += _parse_workbook(p, _CURRENT)
    if not rows:
        raise ValueError("no GDP rows parsed from Uganda UBOS workbooks")
    return pd.DataFrame.from_records(rows)[_OUT_COLS].drop_duplicates(
        ["approach", "category", "series_code", "period", "measure", "price_basis"])
