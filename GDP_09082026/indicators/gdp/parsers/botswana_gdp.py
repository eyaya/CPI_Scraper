"""Parser for the Statistics Botswana Quarterly GDP report PDF (Tier 3).

The statistical annex has one table per measure, each a wide grid with the periods
down column A ('Calendar year': annual years then 'YYYY Q1'/'Q2'.. rows) and the
kinds of economic activity / expenditure across the columns. As in the CPI report,
the COLUMN HEADERS render right-to-left, so each header cell is reversed to read
the activity name; the period labels and the numbers themselves are not reversed.
Wide tables split across a page and its "CONT'D" continuation by ROWS (more
periods), and every page repeats the header, so each page is parsed on its own.

Tables (detected from each page's caption):
  Table 1  Value Added by Kind of Economic Activity at Current Prices   -> prod level current
  Table 3  Value Added … at Constant 2016 Prices                        -> prod level constant
  Table 4  Percentage Change in Gross Value Added …                     -> prod real growth
  Table 2  Contribution of Gross Value Added to GDP …                   -> prod share
  Table 5  GDP by Type of Expenditure at Current Prices                 -> exp level current
  Table 6  GDP by Type of Expenditure at Constant 2016 Prices           -> exp level constant

Values are in P (BWP) million. Everything as published; nothing derived.
"""
from __future__ import annotations
import re
import pdfplumber
import pandas as pd

_OUT_COLS = ["approach", "category", "category_group", "series_code", "geography",
             "period", "frequency", "price_basis", "seasonal_adjustment",
             "measure", "value", "unit", "base_period"]


def _spec(caption: str):
    """Map a page caption to (approach, measure, price_basis, unit) or None."""
    c = caption.lower()
    if "contribution of gross value added" in c:
        return ("production", "share", "not_applicable", "percent")
    if "percentage change in gross value added" in c:
        return ("production", "growth_yoy", "constant", "percent")
    if "value added by kind of economic activity" in c:
        basis = "constant" if "constant" in c else "current"
        return ("production", "level", basis, "BWP million")
    if "gross domestic product by type of expenditure" in c:
        basis = "constant" if "constant" in c else "current"
        return ("expenditure", "level", basis, "BWP million")
    return None


# The PDF renders header cells right-to-left INCONSISTENTLY — some cells are
# reversed, some forward, and multi-line cells scramble word order. So for each
# cell we compare the forward reading against a reconstructed reversed reading
# (each line reversed, line order flipped) and keep whichever matches more known
# national-accounts words.
_KNOWN = [
    "calendar", "agriculture", "forestry", "fishing", "mining", "quarrying",
    "manufact", "electricity", "water", "construct", "wholesale", "retail",
    "diamond", "trader", "transport", "storage", "accommod", "food", "information",
    "communicat", "finance", "insurance", "pension", "real estate", "professional",
    "scientif", "technical", "administrat", "support", "public", "defence",
    "education", "health", "social", "other services", "taxes", "subsidies",
    "value added", "gdp", "gross domestic product", "household", "government",
    "final consumption", "capital formation", "gross fixed", "inventories",
    "exports", "imports", "errors", "omissions", "expenditure", "domestic",
]


def _score(s: str) -> int:
    l = s.lower()
    return sum(k in l for k in _KNOWN)


def _orient(cell) -> str:
    raw = str(cell or "")
    fwd = re.sub(r"\s+", " ", raw.replace("\n", " ")).strip()
    lines = [ln for ln in raw.split("\n") if ln.strip()]
    rev = re.sub(r"\s+", " ", " ".join(ln[::-1] for ln in reversed(lines))).strip()
    return rev if _score(rev) > _score(fwd) else fwd


def _period(s, last_year):
    s = re.sub(r"\s+", " ", str(s or "")).strip()
    m = re.match(r"^(\d{4})\s+Q([1-4])$", s)
    if m:
        return f"{m.group(1)}-Q{m.group(2)}", "quarterly", m.group(1)
    m = re.match(r"^Q([1-4])$", s)
    if m and last_year:
        return f"{last_year}-Q{m.group(1)}", "quarterly", last_year
    m = re.match(r"^(\d{4})$", s)
    if m:
        return m.group(1), "annual", m.group(1)
    return None, None, last_year


def _num(s):
    if s is None:
        return None
    t = str(s).strip().replace(",", "")
    neg = t.startswith("(") and t.endswith(")")
    t = t.strip("()")
    if not re.fullmatch(r"-?\d+(\.\d+)?", t):
        return None
    v = float(t)
    return -v if neg else v


def _is_aggregate(label: str) -> bool:
    l = label.lower()
    return ("gdp" in l or "gross domestic product" in l
            or "total gdp" in l or "gross domestic expenditure" in l)


def _parse_page(tb, approach, measure, basis, unit):
    # header row = the one whose reversed col0 reads 'Calendar year'
    hdr = None
    for i, row in enumerate(tb[:6]):
        if "calendar" in _orient(row[0]).lower():
            hdr = i
            break
    if hdr is None:
        return []
    activities = {j: _orient(tb[hdr][j]) for j in range(1, len(tb[hdr])) if _orient(tb[hdr][j])}
    base = "constant 2016 prices" if basis == "constant" else ""
    rows, last_year = [], None
    for r in tb[hdr + 1:]:
        period, freq, last_year = _period(r[0] if r else "", last_year)
        if not period:
            continue
        for j, activity in activities.items():
            if j >= len(r):
                continue
            v = _num(r[j])
            if v is None:
                continue
            ap = "aggregate" if _is_aggregate(activity) else approach
            rows.append({
                "approach": ap, "category": activity, "category_group": "",
                "series_code": "", "geography": "National", "period": period,
                "frequency": freq, "price_basis": basis,
                "seasonal_adjustment": "nsa" if freq == "quarterly" else "not_applicable",
                "measure": measure, "value": v, "unit": unit, "base_period": base,
            })
    return rows


def parse(pdf_path: str) -> pd.DataFrame:
    rows = []
    with pdfplumber.open(pdf_path) as pdf:
        for i, page in enumerate(pdf.pages):
            if i < 10:                       # skip cover + summary section
                continue
            spec = _spec(page.extract_text() or "")
            if not spec:
                continue
            for tb in page.extract_tables():
                rows.extend(_parse_page(tb, *spec))
    if not rows:
        raise ValueError("no GDP rows parsed from Botswana report")
    out = pd.DataFrame.from_records(rows)[_OUT_COLS]
    return out.drop_duplicates(["approach", "category", "period", "measure", "price_basis"])
