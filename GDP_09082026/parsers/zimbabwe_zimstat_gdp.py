"""Parser for the ZimStat Quarterly GDP workbook (Zimbabwe, ZWG series).

Clean Excel. Each 'Table 1.x' sheet is quarterly GDP by industry: a two-row header
(year row + Q1..Q4 row) across the columns and the industries down the rows.

Sheets used (the current ZWG series, 2023 onward):
  Table 1.1  QGDP current prices    -> production level current
  Table 1.2  QGDP constant prices   -> production level constant
  Table 1.3  Q-o-Q growth rate      -> production real QoQ growth
  Table 1.5  Y-o-Y growth rate      -> production real YoY growth
  Table 1.4  constant contribution  -> contribution to growth
  Implied deflators                 -> deflator

Values are in ZWG (Zimbabwe Gold) for levels, percent for growth, index for the
deflator. The 2.x tables (2019-2023 in the old ZWL currency) are left for a later
pass. Everything as published; nothing derived.
"""
from __future__ import annotations
import re
import pandas as pd

# sheet-name prefix -> (measure, price_basis, unit)
_SHEETS = [
    ("Table 1.1", ("level", "current", "ZWG")),
    ("Table 1.2", ("level", "constant", "ZWG")),
    ("Table 1.3", ("growth_qoq", "constant", "percent")),
    ("Table 1.5", ("growth_yoy", "constant", "percent")),
    ("Table 1.4", ("contribution", "constant", "percentage points")),
    ("Implied deflators", ("deflator", "not_applicable", "index")),
]

_OUT_COLS = ["approach", "category", "category_group", "series_code", "geography",
             "period", "frequency", "price_basis", "seasonal_adjustment",
             "measure", "value", "unit", "base_period"]


def _cell(v):
    return "" if v is None or (isinstance(v, float) and pd.isna(v)) else str(v).strip()


def _period_map(df):
    """Find the year row and the Q1..Q4 row; map each column to a period."""
    year_row = q_row = None
    for i in range(min(6, len(df))):
        texts = [_cell(df.iat[i, c]) for c in range(df.shape[1])]
        if year_row is None and sum(bool(re.fullmatch(r"20\d\d", t)) for t in texts) >= 3:
            year_row = i
        if q_row is None and sum(bool(re.fullmatch(r"Q[1-4]", t)) for t in texts) >= 3:
            q_row = i
    if year_row is None or q_row is None:
        return None, {}
    pmap, cur = {}, None
    for c in range(df.shape[1]):
        y = _cell(df.iat[year_row, c])
        if re.fullmatch(r"20\d\d", y):
            cur = y
        q = _cell(df.iat[q_row, c])
        if cur and re.fullmatch(r"Q[1-4]", q):
            pmap[c] = f"{cur}-{q}"
    return q_row, pmap


def _parse_sheet(df, measure, basis, unit):
    q_row, pmap = _period_map(df)
    if not pmap:
        return []
    base = "constant prices" if basis == "constant" else ""
    label_col = min(pmap) - 1 if min(pmap) > 0 else 0
    rows = []
    for r in range(q_row + 1, len(df)):
        label = re.sub(r"\s+", " ", _cell(df.iat[r, label_col])).strip()
        if not label or len(label) < 3:
            continue
        low = label.lower()
        if any(k in low for k in ("source", "table", "note", "industry")):
            continue
        approach = "aggregate" if ("gross domestic product" in low or low == "gdp"
                                   or "gdp at market" in low or low.startswith("total")) else "production"
        for c, period in pmap.items():
            if c >= df.shape[1]:
                continue
            v = pd.to_numeric(_cell(df.iat[r, c]), errors="coerce")
            if pd.isna(v):
                continue
            rows.append({
                "approach": approach, "category": label, "category_group": "",
                "series_code": "", "geography": "National", "period": period,
                "frequency": "quarterly", "price_basis": basis,
                "seasonal_adjustment": "nsa", "measure": measure,
                "value": float(v), "unit": unit, "base_period": base,
            })
    return rows


def parse(xlsx_path: str) -> pd.DataFrame:
    xl = pd.ExcelFile(xlsx_path)
    rows = []
    for prefix, spec in _SHEETS:
        sheet = next((s for s in xl.sheet_names if s.strip().startswith(prefix)), None)
        if sheet:
            df = pd.read_excel(xlsx_path, sheet_name=sheet, header=None, dtype=str)
            rows.extend(_parse_sheet(df, *spec))
    if not rows:
        raise ValueError("no GDP rows parsed from ZimStat workbook")
    return pd.DataFrame.from_records(rows)[_OUT_COLS].drop_duplicates(
        ["approach", "category", "period", "measure", "price_basis"])
