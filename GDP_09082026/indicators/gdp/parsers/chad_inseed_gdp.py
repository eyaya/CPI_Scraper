"""Parser for the INSEED Chad quarterly national-accounts (CNT) PDF (French).

Francophone CEMAC note (like Cameroon). Each table lists GDP (PIB) by branch of
activity across the quarters ('Tn YYYY'), followed by a growth block we ignore:
  Tableau 1  Évolution du PIB trimestriel en volumes chaînés  -> production constant
  Tableau 3  Évolution du PIB trimestriel aux prix courants    -> production current
  Tableau 4  Déflateur du PIB trimestriel (base 100 = 2017)     -> deflator

Per row we read the label and every French number (comma decimal, optional space
thousands: '2341,7', '1 234,5'); the first len(periods) values are the quarterly
levels (or the deflator). Values are billion XAF (FCFA). Everything as published.
"""
from __future__ import annotations
import re
import pdfplumber
import pandas as pd

_PERIOD_RE = re.compile(r"T([1-4])[ _]?(20\d\d)")
# space-grouped ('1 234,5') OR plain ('2341,7' / '246'); the space-group form is
# tried first so a '2 766,5' isn't split, but a spaceless '2766,5' still matches.
_FRNUM_RE = re.compile(r"-?\d{1,3}(?: \d{3})+(?:,\d+)?|-?\d+(?:,\d+)?")

_OUT_COLS = ["approach", "category", "category_group", "series_code", "geography",
             "period", "frequency", "price_basis", "seasonal_adjustment",
             "measure", "value", "unit", "base_period"]


def _spec(caption: str):
    c = caption.lower()
    if "contribution" in c:
        return None
    if "flateur" in c:                       # déflateur
        return ("deflator", "not_applicable", "index", "2017=100")
    if "prix courant" in c:
        return ("level", "current", "XAF billion", "")
    if "volume" in c or "chaîn" in c or "chain" in c:
        return ("level", "constant", "XAF billion", "chained volume, base 2017")
    return None


def _caption(page) -> str:
    for line in (page.extract_text() or "").split("\n"):
        if re.search(r"tableau\s*\d", line, re.I):
            return line
    return ""


def _frval(tok):
    return float(tok.replace(" ", "").replace(",", "."))


def _periods(tb):
    for row in tb[:4]:
        pers, seen = [], set()
        for c in row:
            m = _PERIOD_RE.search(re.sub(r"\s+", " ", str(c or "")))
            if m:
                p = f"{m.group(2)}-Q{m.group(1)}"
                if p not in seen:
                    seen.add(p); pers.append(p)
        if len(pers) >= 4:
            return pers
    return []


def _parse_table(tb, measure, basis, unit, base):
    periods = _periods(tb)
    if not periods:
        return []
    n = len(periods)
    rows = []
    for row in tb:
        joined = re.sub(r"\s+", " ", " ".join(str(c) for c in row if c)).strip()
        lm = re.match(r"^([^\d]+?)\s*(?=-?\d)", joined)
        if not lm:
            continue
        label = lm.group(1).strip(" .:-()%")
        low = label.lower()
        if (len(label) < 3 or len(label.split()) > 9 or _PERIOD_RE.search(label)
                or any(k in low for k in ("libell", "tableau", "source", "volumes",
                                          "prix courant", "flateur"))):
            continue
        nums = [_frval(t) for t in _FRNUM_RE.findall(joined)]
        if len(nums) < n:
            continue
        ap = "aggregate" if low == "pib" or "produit intérieur brut" in low else "production"
        for period, v in zip(periods, nums[0:n]):
            rows.append({
                "approach": ap, "category": label, "category_group": "",
                "series_code": "", "geography": "National", "period": period,
                "frequency": "quarterly", "price_basis": basis,
                "seasonal_adjustment": "nsa", "measure": measure,
                "value": v, "unit": unit, "base_period": base,
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
                if len(tb) >= 8:
                    rows.extend(_parse_table(tb, *spec))
    if not rows:
        raise ValueError("no GDP rows parsed from INSEED Chad note")
    return pd.DataFrame.from_records(rows)[_OUT_COLS].drop_duplicates(
        ["approach", "category", "period", "measure", "price_basis"])
