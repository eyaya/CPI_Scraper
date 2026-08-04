"""Parser for the Rwanda NISR monthly CPI PDF (Tier 3).

Unlike Kenya, NISR publishes index LEVELS by division. 'Annex 3: Consumer Price
Index, All Rwanda' (the national aggregate) is a table:

  Code Categories Weights May-25 Apr-26 May-26 on Apr.2026 on May.2025 1m 12m
  00 GENERAL INDEX 100% 208.2 232.3 233.8 0.6% 12.3% 0.6% 12.3%
  01 Food and non-alcoholic beverages 39% 262.8 280.0 282.7 ...

Three index columns (prev-year, prev-month, current) => three periods of data
per report. We keep division-level rows only (2-digit codes 00..12; sub-items
like '01.1.1' are skipped). Base Feb 2014 = 100. COICOP-1999 (12 divisions).
"""
from __future__ import annotations
import re
import pdfplumber
import pandas as pd

_MON = {"jan": "01", "feb": "02", "mar": "03", "apr": "04", "may": "05",
        "jun": "06", "jul": "07", "aug": "08", "sep": "09", "oct": "10",
        "nov": "11", "dec": "12"}

# canonical fallback labels (division 05's label wraps across lines in the PDF)
_LABELS = {
    "00": "General index",
    "01": "Food and non-alcoholic beverages",
    "02": "Alcoholic beverages, tobacco and narcotics",
    "03": "Clothing and footwear",
    "04": "Housing, water, electricity, gas and other fuels",
    "05": "Furnishings, household equipment and routine household maintenance",
    "06": "Health", "07": "Transport", "08": "Communication",
    "09": "Recreation and culture", "10": "Education",
    "11": "Restaurants and hotels", "12": "Miscellaneous goods and services",
}

_HDR_RE = re.compile(r"\b([A-Za-z]{3})-(\d{2})\b")
# division row: 2-digit code, optional label, weight%, then 3 index numbers
_ROW_RE = re.compile(
    r"^(\d{2})\s+(.*?)\s*(\d+)%\s+([\d.]+)\s+([\d.]+)\s+([\d.]+)\b"
)


def parse(pdf_path: str) -> pd.DataFrame:
    with pdfplumber.open(pdf_path) as pdf:
        text = None
        for page in pdf.pages:
            t = page.extract_text() or ""
            if "All Rwanda" in t and "GENERAL INDEX" in t:
                text = t
                break
    if text is None:
        raise ValueError("'All Rwanda' annex not found")

    lines = text.splitlines()

    periods = None
    for ln in lines:
        found = _HDR_RE.findall(ln)
        if len(found) >= 3:
            periods = [f"20{yy}-{_MON[mon.lower()]}" for mon, yy in found[:3]]
            break
    if not periods:
        raise ValueError("index-column period header not found")

    records = []
    for ln in lines:
        m = _ROW_RE.match(ln.strip())
        if not m:
            continue
        code = m.group(1)
        if code not in _LABELS:            # keep divisions 00..12 only
            continue
        label = m.group(2).strip() or _LABELS[code]
        idx_vals = [m.group(4), m.group(5), m.group(6)]
        for period, val in zip(periods, idx_vals):
            records.append({
                "coicop_code": code,
                "coicop_label": label,
                "geography": "National",     # 'All Rwanda'
                "period": period,
                "measure": "index",
                "value": float(val),
            })

    out = pd.DataFrame.from_records(records)
    out["unit"] = "Index"
    out["base_period"] = "Feb 2014 = 100"
    out["frequency"] = "monthly"
    return out
