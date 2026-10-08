"""Parser for the Malawi NSO 'GDP by Expenditure' workbook (2017-rebased).

Two sheets, both the expenditure approach, annual:
  GDP_E_CP  GDP by expenditure, current prices    -> level current
  GDP_E_KP  GDP by expenditure, constant prices   -> level constant (base 2017)

Layout: col A = expenditure item, a header row of years, then one value per year.
Values are MWK million. The 'GDP at …' row is the aggregate. Everything as
published; nothing derived.
"""
from __future__ import annotations
import re
import pandas as pd

# sheet name (stripped) -> (price_basis, base_period)
_SHEETS = {
    "GDP_E_CP": ("current", ""),
    "GDP_E_KP": ("constant", "constant 2017 prices"),
}

_OUT_COLS = ["approach", "category", "category_group", "series_code", "geography",
             "period", "frequency", "price_basis", "seasonal_adjustment",
             "measure", "value", "unit", "base_period"]


def _cell(df, r, c):
    v = df.iat[r, c] if c < df.shape[1] else None
    return "" if v is None or (isinstance(v, float) and pd.isna(v)) else str(v).strip()


def _parse_sheet(df, basis, base):
    # header row = the one with the most 4-digit years
    hdr, ycols = None, {}
    for r in range(min(6, len(df))):
        cols = {c: _cell(df, r, c) for c in range(df.shape[1])
                if re.fullmatch(r"20\d\d", _cell(df, r, c))}
        if len(cols) > len(ycols):
            hdr, ycols = r, cols
    if not ycols:
        return []
    rows = []
    for r in range(hdr + 1, len(df)):
        label = re.sub(r"\s+", " ", _cell(df, r, 0)).strip()
        if not label or len(label) < 3:
            continue
        low = label.lower()
        approach = "aggregate" if ("gdp at" in low or low.startswith("gdp")
                                   or "gross domestic product" in low) else "expenditure"
        for c, year in ycols.items():
            v = pd.to_numeric(_cell(df, r, c), errors="coerce")
            if pd.isna(v):
                continue
            rows.append({
                "approach": approach, "category": label, "category_group": "",
                "series_code": "", "geography": "National", "period": year,
                "frequency": "annual", "price_basis": basis,
                "seasonal_adjustment": "not_applicable", "measure": "level",
                "value": float(v), "unit": "MWK million", "base_period": base,
            })
    return rows


def parse(xlsx_path: str) -> pd.DataFrame:
    xl = pd.ExcelFile(xlsx_path)
    rows = []
    for name in xl.sheet_names:
        spec = _SHEETS.get(name.strip())
        if spec:
            df = pd.read_excel(xlsx_path, sheet_name=name, header=None, dtype=str)
            rows.extend(_parse_sheet(df, *spec))
    if not rows:
        raise ValueError("no GDP rows parsed from Malawi NSO workbook")
    return pd.DataFrame.from_records(rows)[_OUT_COLS].drop_duplicates(
        ["approach", "category", "period", "measure", "price_basis"])
