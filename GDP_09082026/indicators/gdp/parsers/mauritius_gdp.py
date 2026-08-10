"""Parser for the Statistics Mauritius Quarterly National Accounts workbook (HS_QNA).

Each 'Tab N' sheet is a formatted table sharing the same column layout: col A =
label, then per year five columns Q1 Q2 Q3 Q4 Yr (Yr = the annual figure). Two
header rows: row 3 = year (forward-filled), row 4 = the Q1..Q4 / Yr labels.

Tabs used (basis of the growth tables verified empirically — the published growth
matches the reference-2018-price levels, i.e. real/volume growth):
  Tab 1  production GVA level, current basic prices     Tab 6  expenditure level current
  Tab 3  production GVA level, reference 2018 prices     Tab 8  expenditure level ref 2018
  Tab 4  production GVA deflators (2018=100)             Tab 9  expenditure deflators
  Tab 2  production GVA real YoY growth                  Tab 7  expenditure real YoY growth
  Tab11  seasonally-adjusted GDP sectoral QoQ growth (real)

Tab 5 and Tab 10 (fiscal-year layouts) are skipped. Everything is as published by
Statistics Mauritius (levels, deflators, growth); nothing is derived.
"""
from __future__ import annotations
import re
import pandas as pd

# sheet -> (approach, measure, price_basis, seasonal, unit)
_TABS = {
    "Tab 1":  ("production",  "level",      "current",        "nsa", "MUR million"),
    "Tab 3":  ("production",  "level",      "constant",       "nsa", "MUR million"),
    "Tab 4":  ("production",  "deflator",   "not_applicable", "nsa", "index"),
    "Tab 2":  ("production",  "growth_yoy", "constant",       "nsa", "percent"),
    "Tab 6":  ("expenditure", "level",      "current",        "nsa", "MUR million"),
    "Tab 8":  ("expenditure", "level",      "constant",       "nsa", "MUR million"),
    "Tab 9":  ("expenditure", "deflator",   "not_applicable", "nsa", "index"),
    "Tab 7":  ("expenditure", "growth_yoy", "constant",       "nsa", "percent"),
    "Tab11":  ("production",  "growth_qoq", "constant",       "saa", "percent"),
}

_QCOL_RE = re.compile(r"^Q([1-4])$", re.I)
_YEAR_RE = re.compile(r"^(20\d\d)$")

_OUT_COLS = ["approach", "category", "category_group", "series_code", "geography",
             "period", "frequency", "price_basis", "seasonal_adjustment",
             "measure", "value", "unit", "base_period"]


def _norm(s):
    return re.sub(r"\s+", " ", "" if s is None or (isinstance(s, float) and pd.isna(s)) else str(s)).strip()


def _find_headers(df):
    """Locate the year row and the Q/Yr row; return (qrow_index, {col:(period,freq)})."""
    year_row = q_row = None
    for i in range(min(8, len(df))):
        texts = [_norm(x) for x in df.iloc[i].tolist()]
        if year_row is None and sum(bool(_YEAR_RE.match(t)) for t in texts) >= 2:
            year_row = i
        if q_row is None and sum(bool(_QCOL_RE.match(t)) for t in texts) >= 3:
            q_row = i
    if year_row is None or q_row is None:
        raise ValueError("could not find year/quarter header rows")
    yr = [_norm(x) for x in df.iloc[year_row].tolist()]
    qr = [_norm(x) for x in df.iloc[q_row].tolist()]
    # Each year is a fixed-width block of columns (Q1..Q4 Yr). Some sheets label
    # only some years in the header (e.g. Tab 8 labels 2013-2021 then jumps to
    # 2026, leaving 2022-2025 blank), so forward-filling the last seen label would
    # mis-tag those years. Instead derive the year from the column POSITION using
    # the first anchor and the regular block width.
    anchors = [(c, int(yr[c])) for c in range(len(yr)) if _YEAR_RE.match(yr[c])]
    first_col, first_yr = anchors[0]
    gaps = [b[0] - a[0] for a, b in zip(anchors, anchors[1:]) if b[0] > a[0]]
    block = min(gaps) if gaps else 5                 # columns per year
    pmap = {}
    for c in range(1, len(qr)):
        if c < first_col:
            continue
        year = first_yr + (c - first_col) // block
        q = qr[c]
        if _QCOL_RE.match(q):
            pmap[c] = (f"{year}-Q{_QCOL_RE.match(q).group(1)}", "quarterly")
        elif q.lower() == "yr":
            pmap[c] = (str(year), "annual")
    return q_row, pmap


def _approach_for(label, default):
    l = label.lower()
    if "gdp at market" in l or "gross domestic product" in l \
            or "gross value added at basic" in l or "total value added" in l:
        return "aggregate"
    return default


def _parse_tab(df, approach, measure, basis, seasonal, unit):
    q_row, pmap = _find_headers(df)
    base = ""
    if basis == "constant":
        base = "reference 2018 prices"
    if measure == "deflator":
        base = "2018=100"
    rows = []
    section = ""                                       # Exports / Imports context
    _AMBIG = {"goods (f.o.b)", "services", "of which gbc"}
    first_row, inst = {}, {}                            # de-collide repeated labels
    for r in range(q_row + 1, len(df)):
        label = _norm(df.iat[r, 0])
        if not label or label.lower().startswith(("source", "table", "note")):
            continue
        low = label.lower()
        if "exports of goods and services" in low:
            section = "Exports"
        elif "imports of goods and services" in low:
            section = "Imports"
        # 'Goods (f.o.b)' / 'Services' / 'of which GBC' repeat under both Exports
        # and Imports; prefix with the section so the two series stay distinct.
        if section and low in _AMBIG:
            label = f"{label} ({section})"
        # a bare label that recurs on a different source row (e.g. 'Other' under
        # both agriculture and manufacturing) is a distinct series — keep both by
        # tagging the later occurrence, rather than dropping or mislabelling it.
        if label in first_row and first_row[label] != r:
            inst[label] = inst.get(label, 1) + 1
            label = f"{label} [{inst[label]}]"
        else:
            first_row.setdefault(label, r)
        row_ap = _approach_for(label, approach)
        for c, (period, freq) in pmap.items():
            if c >= df.shape[1]:
                continue
            v = pd.to_numeric(df.iat[r, c], errors="coerce")
            if pd.isna(v):
                continue
            rows.append({
                "approach": row_ap, "category": label, "category_group": "",
                "series_code": "", "geography": "National", "period": period,
                "frequency": freq, "price_basis": basis,
                "seasonal_adjustment": seasonal if freq == "quarterly" else "not_applicable",
                "measure": measure, "value": float(v), "unit": unit, "base_period": base,
            })
    return rows


def parse(xlsx_path: str) -> pd.DataFrame:
    xl = pd.ExcelFile(xlsx_path)
    rows = []
    for sheet, (approach, measure, basis, seasonal, unit) in _TABS.items():
        if sheet not in xl.sheet_names:
            continue
        df = pd.read_excel(xlsx_path, sheet_name=sheet, header=None, dtype=str)
        rows.extend(_parse_tab(df, approach, measure, basis, seasonal, unit))
    if not rows:
        raise ValueError("no GDP rows parsed from Mauritius QNA workbook")
    return pd.DataFrame.from_records(rows)[_OUT_COLS]
