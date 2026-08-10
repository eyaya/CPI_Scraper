"""Parser for the ANStat Côte d'Ivoire quarterly national-accounts (CNT) PDF.

Two GDP-by-branch tables carry the levels we want (both production approach):
  Tableau 1  'PIB CVS trimestriel en volume'  -> constant (chained, ref 2015),
             seasonally adjusted (CVS); 8 quarters T1-2024 … T4-2025.
  Tableau 4  'PIB trimestriel en valeur'       -> current prices; the 8 quarters
             plus an annual TOTAL column after each year.

Clean French text (not reversed); French numbers ('10 206,3' = 10206.3). Per row
we read the leading label and every French number in order; the first
len(periods) numbers are the levels (the trailing columns are % variations, which
we ignore here). The period header is read left-to-right — 'Tn- YYYY' → quarter,
'TOTAL' → the annual figure of the current year. Contribution tables are skipped.
Values are billion XOF (FCFA). Everything as published; nothing derived.
"""
from __future__ import annotations
import re
import pdfplumber
import pandas as pd

_Q_RE = re.compile(r"T([1-4])-?(20\d\d)")
_FRNUM_RE = re.compile(r"-?\d{1,3}(?:\s\d{3})*(?:,\d+)?")

_OUT_COLS = ["approach", "category", "category_group", "series_code", "geography",
             "period", "frequency", "price_basis", "seasonal_adjustment",
             "measure", "value", "unit", "base_period"]


def _spec(page_text: str):
    # the real basis is on the 'Tableau N : PIB … en valeur/volume' title line;
    # skip contribution tables (they share the 'volumes chaînés' subtitle).
    for title in re.findall(r"Tableau\s*\d\s*:?\s*([^\n]{0,70})", page_text, re.I):
        t = title.lower()
        if "contribution" in t:
            continue
        if "en valeur" in t:
            return ("current", "nsa")
        if "en volume" in t:
            return ("constant", "saa" if "cvs" in t else "nsa")
    return None


def _caption(page) -> str:
    return page.extract_text() or ""


def _periods(tb):
    best = []
    for row in tb[:5]:
        pers, cur = [], None
        for c in row:
            s = re.sub(r"\s", "", str(c or ""))
            m = _Q_RE.match(s)
            if m:
                cur = m.group(2)
                pers.append((f"{m.group(2)}-Q{m.group(1)}", "quarterly"))
            elif "TOTAL" in str(c or "").upper() and cur:
                pers.append((cur, "annual"))
        if len(pers) > len(best):
            best = pers
    return best


def _frval(tok: str):
    t = tok.replace(" ", "").replace(",", ".")
    try:
        return float(t)
    except ValueError:
        return None


def _parse_table(tb, basis, seasonal, base):
    periods = _periods(tb)
    if len(periods) < 4:
        return []
    n = len(periods)
    rows = []
    for row in tb:
        joined = re.sub(r"\s+", " ", " ".join(str(c) for c in row if c)).strip()
        lm = re.match(r"^([^\d]+?)\s*(?=-?\d)", joined)
        if not lm:
            continue
        label = lm.group(1).strip(" .:")
        low = label.lower()
        if (len(label) < 3 or len(label.split()) > 9 or _Q_RE.search(label)
                or any(k in low for k in ("valeurs ajout", "variation", "tableau",
                                          "branche", "source", "total"))):
            continue
        nums = [v for v in (_frval(t) for t in _FRNUM_RE.findall(joined)) if v is not None]
        if len(nums) < n:
            continue
        approach = "aggregate" if low == "pib" or low.startswith("pib ") else "production"
        for (period, freq), v in zip(periods, nums[0:n]):
            rows.append({
                "approach": approach, "category": label, "category_group": "",
                "series_code": "", "geography": "National", "period": period,
                "frequency": freq, "price_basis": basis,
                "seasonal_adjustment": seasonal if freq == "quarterly" else "not_applicable",
                "measure": "level", "value": v, "unit": "XOF billion",
                "base_period": base if basis == "constant" else "",
            })
    return rows


def parse(pdf_path: str) -> pd.DataFrame:
    rows = []
    with pdfplumber.open(pdf_path) as pdf:
        for page in pdf.pages:
            spec = _spec(_caption(page))
            if not spec:
                continue
            for tb in page.extract_tables():
                if len(tb) >= 10:
                    rows.extend(_parse_table(tb, *spec, "reference 2015 prices"))
    if not rows:
        raise ValueError("no GDP rows parsed from ANStat CNT")
    out = pd.DataFrame.from_records(rows)[_OUT_COLS]
    return out.drop_duplicates(["approach", "category", "period", "measure",
                                "price_basis", "seasonal_adjustment"])
