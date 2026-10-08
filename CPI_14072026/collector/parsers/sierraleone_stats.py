"""Parser for the Statistics Sierra Leone monthly CPI press release PDF (Tier 3).

Stats SL publishes 'Table 1: National CPI and rates of inflation by main COICOP
functions (December 2021 = 100)' — one row per COICOP-1999 division + All Items:

  <label>  <weight>  <idx …>  <idx current>  <1m %>  <3m %>  <12m %>
  Food and Non-Alcoholic Beverages  40.3  264.65 273.61 273.19 275.19 278.33  1.14 1.73 5.17
  All Items  100.0  241.73 258.26 264.14 267.77 272.41  1.73 5.48 12.69

The header is letter-spaced (unreadable), but each row's trailing three numbers
are the 1-/3-/12-month % changes, so the current index is nums[-4], MoM nums[-3],
YoY nums[-1]. We emit index + inflation_mom + inflation_yoy for the report month
(from the filename). Base December 2021 = 100.

Two traps this parser has to avoid. The long division labels WRAP, leaving the
numbers on a line of their own ('Alcoholic Beverages, Tobacco and 1.0' / the
numbers / 'Narcotics'), so a row is matched on a prev+own+next window rather than
on its own line. And the release's narrative pages discuss each division by name
with numbers in the sentence ('Alcoholic beverages … increased from -4.26 percent
…'), which would match those keywords first — so the scan is scoped to the page
carrying the Table 1 caption.

Table 1 also shows four earlier index columns (the same month a year before, then
m-3 … m-1). They are not emitted: the header is letter-spaced beyond reading, so
their periods could only be inferred. History accumulates across monthly runs.
"""
from __future__ import annotations
import os
import re
import pdfplumber
import pandas as pd

_BASE_PERIOD = "Dec 2021 = 100"
_MONTHS = {"jan": "01", "feb": "02", "mar": "03", "apr": "04", "may": "05",
           "jun": "06", "jul": "07", "aug": "08", "sep": "09", "oct": "10",
           "nov": "11", "dec": "12"}
# (code, label, keyword) — first match wins; 'food and non' before 'alcoholic'
_DIVS = [
    ("00", "All items", "all items"),
    ("01", "Food and non-alcoholic beverages", "food and non"),
    ("02", "Alcoholic beverages, tobacco and narcotics", "alcoholic"),
    ("03", "Clothing and footwear", "clothing"),
    ("04", "Housing, water, electricity, gas and other fuels", "housing"),
    ("05", "Furnishings, household equipment and routine maintenance", "furnishing"),
    ("06", "Health", "health"),
    ("07", "Transport", "transport"),
    ("08", "Communication", "communication"),
    ("09", "Recreation and culture", "recreation"),
    ("10", "Education services", "education"),
    ("11", "Restaurants and hotels", "restaurant"),
    ("12", "Miscellaneous goods and services", "miscellaneous"),
]
_NUM = re.compile(r"-?\d+\.\d+")
_FMONTHS = ("january|february|march|april|may|june|july|august|september|"
            "october|november|december")


def _period(path: str, text: str) -> str | None:
    m = re.search(r"(" + _FMONTHS + r")[-_ ]*(20\d\d)", os.path.basename(path), re.IGNORECASE) \
        or re.search(r"(" + _FMONTHS + r")[-_ ,]*(20\d\d)", text, re.IGNORECASE)
    return f"{m.group(2)}-{_MONTHS[m.group(1).lower()[:3]]}" if m else None


_TABLE1 = re.compile(r"table\s*1\s*:\s*national cpi", re.I)
_ROW_NUMS = 8          # 5 monthly indices + the 1-/3-/12-month rates


def parse(pdf_path: str) -> pd.DataFrame:
    with pdfplumber.open(pdf_path) as pdf:
        pages = [p.extract_text() or "" for p in pdf.pages]
    text = "\n".join(pages)
    period = _period(pdf_path, text)
    if not period:
        raise ValueError("Sierra Leone CPI: report month not found")

    # The contents page lists the same caption, so score the candidates by how
    # many data rows they actually carry and take the richest.
    def rows_on(page):
        return sum(1 for ln in page.splitlines()
                   if len(_NUM.findall(ln)) >= _ROW_NUMS)

    cands = [p for p in pages if _TABLE1.search(p)]
    table = max(cands, key=rows_on) if cands else None
    if table is None or not rows_on(table):
        raise ValueError("Sierra Leone CPI: 'Table 1: National CPI ...' rows not found")
    lines = table.splitlines()

    def label_only(i):
        """The line at i, if it is label text rather than a data row."""
        if 0 <= i < len(lines) and len(_NUM.findall(lines[i])) < _ROW_NUMS:
            return lines[i]
        return ""

    picked = {}
    for i, ln in enumerate(lines):
        nums = _NUM.findall(ln)
        if len(nums) < _ROW_NUMS:
            continue
        first = _NUM.search(ln)
        own = ln[:first.start()] if first else ""
        context = f"{label_only(i - 1)} {own} {label_only(i + 1)}".lower()
        hit = next(((c, lab) for c, lab, kw in _DIVS if kw in context), None)
        if not hit or hit[0] in picked:
            continue
        picked[hit[0]] = (hit[1], float(nums[-4]), float(nums[-3]), float(nums[-1]))

    missing = [c for c, _, _ in _DIVS if c not in picked]
    if missing:
        raise ValueError(f"Sierra Leone CPI incomplete: missing {missing}")

    records = []
    for code, (label, idx, mom, yoy) in picked.items():
        records.append((code, label, period, "index", round(idx, 4), "Index", _BASE_PERIOD))
        records.append((code, label, period, "inflation_mom", round(mom, 4), "percent", ""))
        records.append((code, label, period, "inflation_yoy", round(yoy, 4), "percent", ""))
    out = pd.DataFrame.from_records(
        records, columns=["coicop_code", "coicop_label", "period", "measure",
                          "value", "unit", "base_period"])
    out["geography"] = "National"
    out["frequency"] = "monthly"
    return out
