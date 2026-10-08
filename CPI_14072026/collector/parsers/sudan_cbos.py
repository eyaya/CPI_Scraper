"""Parser for the CBOS Sudan 'Economic & Financial Statistics Review' (Tier 3).

PARTIAL, and a central-bank fallback: Sudan's NSO — the Central Bureau of
Statistics — has no reachable website (cbs.gov.sd does not resolve), so the CPI
is taken from the Central Bank of Sudan's statistics review, whose Table No. (20)
'Consumer Price Index & Inflation Rates' is CBS's own series, republished
unchanged and credited to it ('Source: Central Bureau of Statistics') rather than
re-estimated.

The table is bilingual, one row per period, English on the left and Arabic on the
right, base year 2007 = 100:

  Period                    CPI        Inflation Rate%
  December 2023        130,391.1                  92.7      2023 ربمسيد
  2024                                                       2024
  January              154,276.3                 127.9      رياني

so a year on its own line opens a block of months, while the December rows of
earlier years carry their year inline. All-items only: the review publishes no
COICOP breakdown, and the rate is year on year (Dec-2024's 187.8 % is exactly
375,310.5 over 130,391.1), so it is emitted as `inflation_yoy`.

Extraction quirk worked around: the PDF splits a leading digit off some rates
('8 7.3' for 87.3, '9 2.7' for 92.7), so the tokens after the CPI value are
joined until one carries a decimal point. Arabic text is cut before any parsing,
which also drops the trailing Arabic year that follows some rates.
"""
from __future__ import annotations
import re
import pdfplumber
import pandas as pd

_GEOGRAPHY = "National"
_LABEL = "Consumer Price Index"
_MONTHS = {"january": "01", "february": "02", "march": "03", "april": "04",
           "may": "05", "june": "06", "july": "07", "august": "08",
           "september": "09", "october": "10", "november": "11",
           "december": "12"}
_ARABIC = re.compile(r"[؀-ۿ].*$")
_TABLE = re.compile(r"consumer price index\s*&?\s*inflation rate", re.I)
_BASE = re.compile(r"base year\s*(\d{4})\s*=\s*(\d+)", re.I)
_YEAR_ONLY = re.compile(r"^(20\d\d)(?:\s+20\d\d)?$")
_ROW = re.compile(
    r"^(" + "|".join(_MONTHS) + r")\s*(20\d\d)?\s+"          # month [year]
    r"(\d{1,3}(?:,\d{3})*\.\d+)\s+"                          # CPI
    r"(.+)$", re.I)                                          # rate, maybe split


def _rate(rest: str) -> float | None:
    """Join the tokens after the CPI until one carries the decimal point: the
    PDF splits '87.3' into '8' and '7.3'. A trailing year token never gets
    reached because the accumulated value already has its point by then."""
    acc = ""
    for token in rest.split():
        acc += token
        if "." in acc:
            return float(acc) if re.fullmatch(r"-?\d+\.\d+", acc) else None
    return None


def parse(pdf_path: str) -> pd.DataFrame:
    with pdfplumber.open(pdf_path) as pdf:
        page = next((p for p in pdf.pages if _TABLE.search(p.extract_text() or "")
                     and "Source" in (p.extract_text() or "")), None)
        if page is None:
            raise ValueError("Sudan CPI: Table 20 (CPI & Inflation Rates) not found")
        lines = [_ARABIC.sub("", ln).strip()
                 for ln in (page.extract_text() or "").splitlines()]

    b = _BASE.search(" ".join(lines))
    base_period = f"{b.group(1)} = {b.group(2)}" if b else ""

    records, year = [], None
    for line in lines:
        y = _YEAR_ONLY.match(line)
        if y:
            year = y.group(1)
            continue
        m = _ROW.match(line)
        if not m:
            continue
        row_year = m.group(2) or year
        rate = _rate(m.group(4))
        if not row_year or rate is None:
            continue
        period = f"{row_year}-{_MONTHS[m.group(1).lower()]}"
        records.append((period, "index", float(m.group(3).replace(",", "")),
                        "Index", base_period))
        records.append((period, "inflation_yoy", rate, "percent", ""))

    if len(records) < 12:
        raise ValueError(f"Sudan CPI: only {len(records) // 2} periods parsed")

    out = pd.DataFrame.from_records(
        records, columns=["period", "measure", "value", "unit", "base_period"])
    out["coicop_code"] = "00"
    out["coicop_label"] = _LABEL
    out["geography"] = _GEOGRAPHY
    out["frequency"] = "monthly"
    return out.drop_duplicates(["period", "measure"])
