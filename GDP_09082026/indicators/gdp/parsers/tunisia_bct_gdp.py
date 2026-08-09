"""Parser for the Central Bank of Tunisia (BCT) GDP statistics (HTML tables).

INS Tunisia's national accounts sit behind an interactive portal, but the BCT
renders two GDP tables straight into its statistics pages (stable JSP URLs):

  'Gross domestic product (GDP)'   -> GDP total (a 'Current prices' and an empty
                                      'Constant prices' row), annual
  'Use of gross domestic product'  -> the expenditure components (private &
                                      government consumption, gross fixed capital
                                      formation, change in stocks, exports, imports)

Both are current prices, in millions of Tunisian dinars (TND), 2017-2022. Each is
an HTML table shaped 'Indicateurs | <year> …'. We read every populated row (rows
that are entirely 0.0 are the portal's unfilled placeholders — constant prices,
GFCF sub-items — and are skipped). A row labelled '<basis> prices' is the GDP
aggregate; the other rows are expenditure components. Verified: GDP at current
prices 2022 = 143,767.7 million TND (~US$46bn). Nothing derived.
"""
from __future__ import annotations
import re
from bs4 import BeautifulSoup
import pandas as pd

_OUT_COLS = ["approach", "category", "category_group", "series_code", "geography",
             "period", "frequency", "price_basis", "seasonal_adjustment",
             "measure", "value", "unit", "base_period"]


def _num(s):
    s = s.strip().replace(" ", "").replace("\xa0", "").replace(" ", "")
    s = s.replace(",", "")
    try:
        return float(s)
    except ValueError:
        return None


def _read_html(path, rows):
    with open(path, encoding="utf-8", errors="replace") as f:
        soup = BeautifulSoup(f.read(), "html.parser")
    for table in soup.find_all("table"):
        trs = table.find_all("tr")
        header = None
        for tr in trs:
            cells = [c.get_text(" ", strip=True) for c in tr.find_all(["th", "td"])]
            years = [(i, c) for i, c in enumerate(cells) if re.fullmatch(r"20\d\d", c)]
            if len(years) >= 3 and header is None:
                header = years
                continue
            if header is None:
                continue
            label = re.sub(r"\s+", " ", cells[0]).strip() if cells else ""
            if not label or not re.search(r"[A-Za-z]{3}", label):
                continue
            vals = {}
            for i, year in header:
                if i < len(cells):
                    v = _num(cells[i])
                    if v is not None:
                        vals[year] = v
            if not vals or all(v == 0 for v in vals.values()):
                continue
            low = label.lower()
            m = re.match(r"(current|constant) prices", low)
            if m:
                category, approach = "Gross Domestic Product", "aggregate"
                basis = m.group(1)
            else:
                category, approach, basis = label, "expenditure", "current"
            for year, v in vals.items():
                rows.append({
                    "approach": approach, "category": category,
                    "category_group": "", "series_code": "",
                    "geography": "National", "period": year,
                    "frequency": "annual", "price_basis": basis,
                    "seasonal_adjustment": "nsa", "measure": "level",
                    "value": v, "unit": "TND million", "base_period": "",
                })


def parse(pdf_path: str, extras: list[str] | None = None) -> pd.DataFrame:
    rows = []
    _read_html(pdf_path, rows)
    for ex in (extras or []):
        _read_html(ex, rows)
    if not rows:
        raise ValueError("no GDP rows parsed from BCT Tunisia pages")
    return pd.DataFrame.from_records(rows)[_OUT_COLS].drop_duplicates(
        ["approach", "category", "period", "measure", "price_basis"])
