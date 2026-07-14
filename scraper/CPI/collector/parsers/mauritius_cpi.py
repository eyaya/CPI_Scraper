"""Parser for the Statistics Mauritius monthly CPI note PDF (Tier 3).

Statistics Mauritius publishes a monthly CPI note (base Jan–Dec 2023 = 100) whose
'Division' table extracts cleanly with pdfplumber's table extraction:

  Division                      | January 2026 | February 2026 | % change
  1. Food and non-alcoholic …   | 109.8        | 110.6         | +0.8
  …
  13. Personal care, social …   | 109.5        | 111.0         | +1.4
  All Divisions                 | 109.1        | 109.5         | +0.4

Rows carry a leading COICOP-2018 division number (1..13); 'All Divisions' is All
items (00) — but NOT 'All Divisions, excluding …'. The table shows two dated
index columns, so one note yields two months (previous + current). We emit index
levels; labels use the canonical COICOP-2018 map (the PDF spaces some letters,
e.g. 'H e a lth'). Base Jan–Dec 2023 = 100.
"""
from __future__ import annotations
import re
import pdfplumber
import pandas as pd

from ..coicop import DIVISIONS

_BASE_PERIOD = "Jan-Dec 2023 = 100"
_MONTHS = {"january": "01", "february": "02", "march": "03", "april": "04",
           "may": "05", "june": "06", "july": "07", "august": "08",
           "september": "09", "october": "10", "november": "11", "december": "12"}
_PERIOD = re.compile(r"(january|february|march|april|may|june|july|august|"
                     r"september|october|november|december)\s+(\d{4})", re.IGNORECASE)


def _period(cell) -> str | None:
    if not isinstance(cell, str):
        return None
    m = _PERIOD.search(cell.replace("\n", " "))
    return f"{m.group(2)}-{_MONTHS[m.group(1).lower()]}" if m else None


def _value(cell) -> float | None:
    if isinstance(cell, (int, float)):
        return float(cell)
    if isinstance(cell, str) and re.fullmatch(r"-?\d+(?:\.\d+)?", cell.strip()):
        return float(cell.strip())
    return None


def parse(pdf_path: str) -> pd.DataFrame:
    with pdfplumber.open(pdf_path) as pdf:
        for page in pdf.pages:
            for tb in page.extract_tables():
                hi = next((i for i, r in enumerate(tb)
                           if any(isinstance(c, str) and c.strip().lower() == "division" for c in r)), None)
                if hi is None:
                    continue
                cols = {ci: p for ci, c in enumerate(tb[hi]) if (p := _period(c))}
                if not cols:
                    continue

                records = []
                for row in tb[hi + 1:]:
                    first = str(row[0]).replace("\n", " ").strip() if row and row[0] else ""
                    m = re.match(r"^(\d{1,2})\.", first)
                    if m and 1 <= int(m.group(1)) <= 13:
                        code = f"{int(m.group(1)):02d}"
                    elif first.lower().startswith("all divisions") and "exclud" not in first.lower():
                        code = "00"
                    else:
                        continue
                    label = DIVISIONS.get(code, "All items" if code == "00" else "")
                    for ci, period in cols.items():
                        v = _value(row[ci] if ci < len(row) else None)
                        if v is not None:
                            records.append((code, label, period, round(v, 4)))

                if len({c for c, *_ in records if c != "00"}) >= 13:
                    out = pd.DataFrame.from_records(
                        records, columns=["coicop_code", "coicop_label", "period", "value"])
                    out = out.drop_duplicates(["coicop_code", "period"])
                    out["geography"] = "National"
                    out["measure"] = "index"
                    out["unit"] = "Index"
                    out["base_period"] = _BASE_PERIOD
                    out["frequency"] = "monthly"
                    return out

    raise ValueError("Mauritius CPI division table not found in note")
