"""Parser for the Morocco HCP national-accounts indicators (Google Sheets).

HCP publishes each headline national-accounts indicator as its own one-series
Google Sheet (col B = period, col C = value). We collect the GDP-relevant ones;
parse() gets the primary file plus the rest via `extras`, and routes each by its
saved filename. Quarterly periods are written 'YYYY:Q' -> 'YYYY-Qn'; the per-capita
series is annual. Everything is as published by HCP (DCN); nothing is derived.

Covered: real GDP growth, non-agricultural GDP growth, agricultural value-added
growth, GDP per capita (dirham), and the implicit GDP price deflator change. The
detailed by-branch / by-expenditure tables HCP issues only as PDF reports are a
later pass.
"""
from __future__ import annotations
import os
import re
import pandas as pd

# filename substring -> (approach, category, measure, price_basis, unit).
# Order matters: the more specific keys must precede the generic 'GDP_growth'
# (else 'Morocco_NonAg_GDP_growth' would match 'GDP_growth' first).
_FILES = {
    "NonAg":       ("aggregate",   "Non-agricultural GDP", "growth_yoy", "constant", "percent"),
    "Agri_VA":     ("production",  "Agriculture (value added)", "growth_yoy", "constant", "percent"),
    "per_capita":  ("aggregate",   "GDP per capita", "per_capita", "current", "MAD per capita"),
    "deflator":    ("aggregate",   "GDP implicit price deflator (YoY change)",
                    "growth_yoy", "not_applicable", "percent"),
    "GDP_growth":  ("aggregate",   "GDP", "growth_yoy", "constant", "percent"),
}

_QP_RE = re.compile(r"^(\d{4})\s*[:._-]\s*([1-4])$")
_YR_RE = re.compile(r"^(\d{4})$")

_OUT_COLS = ["approach", "category", "category_group", "series_code", "geography",
             "period", "frequency", "price_basis", "seasonal_adjustment",
             "measure", "value", "unit", "base_period"]


def _spec_for(path):
    name = os.path.basename(path)
    for key, spec in _FILES.items():
        if key.lower() in name.lower():
            return spec
    return None


def _period(s):
    s = str(s).strip()
    m = _QP_RE.match(s)
    if m:
        return f"{m.group(1)}-Q{m.group(2)}", "quarterly"
    if _YR_RE.match(s):
        return s, "annual"
    return None, None


def _parse_file(path, approach, category, measure, basis, unit):
    df = pd.read_excel(path, sheet_name=0, header=None, dtype=str)
    # the two data columns are the last two non-empty ones (period, value)
    rows = []
    for i in range(len(df)):
        # find period + value in the row (period in col with 'YYYY' or 'YYYY:Q')
        cells = [("" if pd.isna(x) else str(x).strip()) for x in df.iloc[i].tolist()]
        per = val = None
        for j, c in enumerate(cells):
            p, freq = _period(c)
            if p and j + 1 < len(cells):
                nxt = pd.to_numeric(cells[j + 1].replace(",", "."), errors="coerce")
                if pd.notna(nxt):
                    per, val, fq = p, float(nxt), freq
                    break
        if per is None:
            continue
        rows.append({
            "approach": approach, "category": category, "category_group": "",
            "series_code": "", "geography": "National", "period": per,
            "frequency": fq, "price_basis": basis,
            "seasonal_adjustment": "nsa" if fq == "quarterly" else "not_applicable",
            "measure": measure, "value": val, "unit": unit, "base_period": "",
        })
    return rows


def parse(primary_path, extras=None) -> pd.DataFrame:
    paths = [primary_path] + list(extras or [])
    rows = []
    for p in paths:
        spec = _spec_for(p)
        if spec:
            rows.extend(_parse_file(p, *spec))
    if not rows:
        raise ValueError("no GDP rows parsed from Morocco HCP sheets")
    return pd.DataFrame.from_records(rows)[_OUT_COLS]
