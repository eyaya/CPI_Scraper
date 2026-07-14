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


def parse(pdf_path: str) -> pd.DataFrame:
    with pdfplumber.open(pdf_path) as pdf:
        text = "\n".join((p.extract_text() or "") for p in pdf.pages)
    period = _period(pdf_path, text)
    if not period:
        raise ValueError("Sierra Leone CPI: report month not found")

    picked = {}
    for ln in text.splitlines():
        low = ln.lower()
        hit = next(((c, lab) for c, lab, kw in _DIVS if kw in low), None)
        if not hit or hit[0] in picked:
            continue
        nums = _NUM.findall(ln)
        if len(nums) >= 5:                                 # weight + >=1 index + 3 rates
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
