"""Parser for the KNBS Quarterly GDP report PDF (Tier 3, mirror-reversed).

KNBS renders its statistical-annex GDP tables RIGHT-TO-LEFT: every text and number
token is stored reversed ('secirP' = 'Prices', '734,634,2' = '2,436,437'). We
reverse each token back. The tables are GDP by activity (activities down the rows,
time across the columns); pdfplumber's extract_tables keeps each YEAR in one column
whose cell packs that year's quarters, in visual order Q1..Q4 — which the whole-cell
reversal flips to Qn..Q1, so the k-th number of an n-number cell is quarter (n-k).
This also handles the newest, partial year (one value = Q1).

Tables (from the reversed caption): Table 1 current prices, Table 2 constant 2016
prices, Table 3 growth rates (real). Values are KSh million (levels) / percent
(growth). Verified: constant GDP-at-market 2024 quarters sum to ~KSh 10.9tn.
Everything as published; nothing derived.
"""
from __future__ import annotations
import re
import pdfplumber
import pandas as pd

_OUT_COLS = ["approach", "category", "category_group", "series_code", "geography",
             "period", "frequency", "price_basis", "seasonal_adjustment",
             "measure", "value", "unit", "base_period"]

_NUM_RE = re.compile(r"^\(?-?[\d,]+(?:\.\d+)?\)?$")


def _rev(s) -> str:
    return re.sub(r"\s+", " ", str(s or "").replace("\n", " "))[::-1].strip()


def _spec(caption: str):
    c = caption.lower()
    if "growth rate" in c:
        return ("growth_yoy", "constant", "percent")
    if "constant" in c:
        return ("level", "constant", "KES million")
    if "current price" in c:
        return ("level", "current", "KES million")
    return None


def _caption(page) -> str:
    lines = [l for l in (page.extract_text() or "").split("\n") if l.strip()][:12]
    joined = " ".join(l[::-1] for l in reversed(lines))
    m = re.search(r"Table\s*\d[^|]{0,70}", joined)
    return m.group(0) if m else ""


def _val(tok: str):
    t = tok.replace(",", "").strip()
    neg = t.startswith("(") and t.endswith(")")
    t = t.strip("()")
    if not re.fullmatch(r"-?\d+(\.\d+)?", t):
        return None
    v = float(t)
    return -v if neg else v


def _nums(cell: str):
    return [t for t in cell.split() if _NUM_RE.match(t)]


def _is_aggregate(label: str) -> bool:
    l = label.lower()
    return "gdp at market" in l or "gross domestic product" in l \
        or l.startswith("gdp") or "gdp," in l


def _parse_table(tb, measure, basis, unit):
    G = [[_rev(c) for c in row] for row in tb]
    # year row: the row with >=4 four-digit years; map column -> year
    yr_i = next((i for i, r in enumerate(G)
                 if sum(bool(re.fullmatch(r"20\d\d", c)) for c in r) >= 4), None)
    if yr_i is None:
        return []
    col_year = {j: int(c) for j, c in enumerate(G[yr_i]) if re.fullmatch(r"20\d\d", c)}
    base = "constant 2016 prices" if basis == "constant" else ""
    rows = []
    for r in G:
        label = r[0].strip()
        if not label or re.fullmatch(r"20\d\d|Quarter|Year", label):
            continue
        if not any(_nums(r[j]) for j in col_year):
            continue
        approach = "aggregate" if _is_aggregate(label) else "production"
        seasonal = "saa" if "seasonally adjusted" in label.lower() else "nsa"
        for j, year in col_year.items():
            if j >= len(r):
                continue
            ns = _nums(r[j])
            n = len(ns)
            for k, tok in enumerate(ns):
                v = _val(tok)
                if v is None:
                    continue
                q = n - k                       # cell is reversed: Qn..Q1
                if not 1 <= q <= 4:
                    continue
                rows.append({
                    "approach": approach, "category": label, "category_group": "",
                    "series_code": "", "geography": "National",
                    "period": f"{year}-Q{q}", "frequency": "quarterly",
                    "price_basis": basis, "seasonal_adjustment": seasonal,
                    "measure": measure, "value": v, "unit": unit, "base_period": base,
                })
    return rows


def parse(pdf_path: str) -> pd.DataFrame:
    rows = []
    with pdfplumber.open(pdf_path) as pdf:
        for page in pdf.pages:
            spec = _spec(_caption(page))
            if not spec:
                continue
            tbls = [tb for tb in page.extract_tables() if len(tb) >= 15]
            for tb in tbls:
                rows.extend(_parse_table(tb, *spec))
    if not rows:
        raise ValueError("no GDP rows parsed from KNBS report")
    out = pd.DataFrame.from_records(rows)[_OUT_COLS]
    return out.drop_duplicates(["approach", "category", "period", "measure", "price_basis", "seasonal_adjustment"])
