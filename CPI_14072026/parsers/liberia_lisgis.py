"""Parser for the LISGIS Liberia monthly CPI Newsletter PDF (Tier 3).

The newsletter's 'Table 1: Consumer Price Indices and rates' is a clean 13-month
series for the national all-items CPI (base Dec 2005 = 100):

  Month       CPI (Dec 2005=100)   Monthly (m/m)   Yearly (y/y)
  May 2025    780.1                0.2             11.7
  …
  May 2026    …                    …               5.3

We emit index + inflation_mom + inflation_yoy for code 00 (all items) for every
month in the table. The newsletter's by-division figures are published only as
bar charts (values fused into the labels), so they are not extracted here.
"""
from __future__ import annotations
import re
import pdfplumber
import pandas as pd

_BASE_PERIOD = "Dec 2005 = 100"
_MON = {"jan": "01", "feb": "02", "mar": "03", "apr": "04", "may": "05", "jun": "06",
        "jul": "07", "aug": "08", "sep": "09", "oct": "10", "nov": "11", "dec": "12"}
# <Month>[.] <Year> <index> <m/m> <y/y>
_ROW = re.compile(
    r"\b([A-Za-z]{3,9})\.?\s+(20\d\d)\s+(\d{2,4}\.\d)\s+(-?\d{1,3}\.\d)\s+(-?\d{1,3}\.\d)\b")


def parse(pdf_path: str) -> pd.DataFrame:
    with pdfplumber.open(pdf_path) as pdf:
        text = "\n".join((p.extract_text() or "") for p in pdf.pages)

    seen, records = set(), []
    for mon, yr, idx, mom, yoy in _ROW.findall(text):
        mm = _MON.get(mon.lower()[:3])
        if not mm:
            continue
        period = f"{yr}-{mm}"
        if period in seen:
            continue
        seen.add(period)
        records.append(("00", "All items", period, "index", float(idx), "Index", _BASE_PERIOD))
        records.append(("00", "All items", period, "inflation_mom", float(mom), "percent", ""))
        records.append(("00", "All items", period, "inflation_yoy", float(yoy), "percent", ""))

    if not records:
        raise ValueError("Liberia CPI: Table 1 rows not found")
    out = pd.DataFrame.from_records(
        records, columns=["coicop_code", "coicop_label", "period", "measure",
                          "value", "unit", "base_period"])
    out["geography"] = "National"
    out["frequency"] = "monthly"
    return out
