"""Parser for the Kenya KNBS monthly CPI PDF press release (Tier 3).

KNBS does not publish the by-division CPI *index level* — only, in 'Table 1'
(one page), each of the 13 COICOP divisions + Total with:
    <division label>  <weight %>  <month-on-month %>  <year-on-year %>
e.g.  'Food and Non-Alcoholic Beverages 32.9094 0.3 8.6'

So we emit two measures per division: inflation_mom and inflation_yoy. The
report month is taken from the PDF filename (…-June-2026.pdf), falling back to
the cover-page text.
"""
from __future__ import annotations
import os
import re
import pdfplumber
import pandas as pd

from ..coicop import code_for_label

_MONTHS = {
    "january": "01", "february": "02", "march": "03", "april": "04",
    "may": "05", "june": "06", "july": "07", "august": "08",
    "september": "09", "october": "10", "november": "11", "december": "12",
}
_DATE_RE = re.compile(
    r"(january|february|march|april|may|june|july|august|september|october|"
    r"november|december)[-_ ]+(\d{4})",
    re.IGNORECASE,
)
# a data line: label, then weight, month-on-month, year-on-year
_ROW_RE = re.compile(
    r"^(.+?)\s+(\d+\.\d+)\s+(-?\d+\.\d+)\s+(-?\d+\.\d+)\s*$"
)


def _period_from(path: str, pdf) -> str:
    m = _DATE_RE.search(os.path.basename(path))
    if not m:
        m = _DATE_RE.search(pdf.pages[0].extract_text() or "")
    if not m:
        raise ValueError("could not determine report month/year")
    return f"{m.group(2)}-{_MONTHS[m.group(1).lower()]}"


def parse(pdf_path: str) -> pd.DataFrame:
    with pdfplumber.open(pdf_path) as pdf:
        period = _period_from(pdf_path, pdf)

        # find the page whose lines yield the most COICOP-division matches
        best_rows = []
        for page in pdf.pages:
            rows = []
            for line in (page.extract_text() or "").splitlines():
                m = _ROW_RE.match(line.strip())
                if not m:
                    continue
                code = code_for_label(m.group(1))
                if code is None:
                    continue
                rows.append((code, m.group(1).strip(), float(m.group(3)),
                             float(m.group(4))))
            if len(rows) > len(best_rows):
                best_rows = rows

    if len(best_rows) < 14:
        raise ValueError(f"only found {len(best_rows)} division rows (need 14)")

    records = []
    seen = set()
    for code, label, mom, yoy in best_rows:
        if code in seen:  # guard against a stray duplicate line
            continue
        seen.add(code)
        for measure, val in (("inflation_mom", mom), ("inflation_yoy", yoy)):
            records.append({
                "coicop_code": code,
                "coicop_label": label.rstrip("."),
                "geography": "National",
                "period": period,
                "measure": measure,
                "value": val,
            })

    out = pd.DataFrame.from_records(records)
    out["unit"] = "percent"
    out["base_period"] = ""
    out["frequency"] = "monthly"
    return out
