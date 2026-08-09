"""Parser for the INSTAT Mali quarterly GDP (PIB) note PDF (Tier 3, French).

Clean francophone note. Four level tables give the quarterly GDP breakdown; each
row is a branch (or expenditure component) and the columns are the quarters
('Tn_YYYY'). The tables are pure levels (growth is in separate 'Taux de
croissance' tables, which we skip):
  Tableau 1  Valeurs ajoutées du PIB en volume chaîné      -> production constant
  Tableau 3  Valeurs ajoutées du PIB à prix courant        -> production current
  Tableau 4  composantes du PIB … optique de dépenses en volume chaîné -> exp constant
  Tableau 6  composantes du PIB … optique de dépenses aux prix courants -> exp current

Per row we read the label and the French numbers in order ('2 494,4' / '2494,4');
the first len(periods) values are the quarterly levels. Values are billion XOF
(FCFA). Everything as published; nothing derived.
"""
from __future__ import annotations
import re
import pdfplumber
import pandas as pd

_PERIOD_RE = re.compile(r"T([1-4])[_ ]?(20\d\d)")

_OUT_COLS = ["approach", "category", "category_group", "series_code", "geography",
             "period", "frequency", "price_basis", "seasonal_adjustment",
             "measure", "value", "unit", "base_period"]


def _spec(caption: str):
    c = caption.lower()
    if "taux de croissance" in c:
        return None
    approach = "expenditure" if "composante" in c else "production"
    if "prix courant" in c:
        basis = "current"
    elif "volume" in c or "chaîn" in c or "chain" in c:
        basis = "constant"
    else:
        return None
    return approach, basis


def _caption(page) -> str:
    for line in (page.extract_text() or "").split("\n"):
        if re.search(r"tableau\s*\d", line, re.I):
            return line
    return ""


def _frval(cell):
    s = str(cell or "").strip().replace(" ", "").replace(" ", "").replace(",", ".")
    return float(s) if re.fullmatch(r"-?\d+(\.\d+)?", s) else None


def _periods(tb):
    for row in tb[:4]:
        pers, seen = [], set()
        for c in row:
            m = _PERIOD_RE.search(re.sub(r"\s", "", str(c or "")))
            if m:
                p = f"{m.group(2)}-Q{m.group(1)}"
                if p not in seen:
                    seen.add(p); pers.append(p)
        if len(pers) >= 4:
            return pers
    return []


def _parse_table(tb, approach, basis):
    periods = _periods(tb)
    if not periods:
        return []
    n = len(periods)
    base = "chained volume" if basis == "constant" else ""
    rows = []
    for row in tb:
        cells = [("" if c is None else str(c).strip()) for c in row]
        label = next((re.sub(r"\s+", " ", c).strip() for c in cells
                      if c and re.search(r"[A-Za-zÀ-ÿ]{3,}", c) and _frval(c) is None), "")
        if not label or len(label) < 3 or _PERIOD_RE.search(label) \
                or any(k in label.lower() for k in ("libellé", "branche", "tableau")):
            continue
        nums = [v for v in (_frval(c) for c in cells) if v is not None]
        if len(nums) < n:
            continue
        low = label.lower()
        ap = "aggregate" if low == "pib" or "produit intérieur brut" in low else approach
        for period, v in zip(periods, nums[0:n]):
            rows.append({
                "approach": ap, "category": label, "category_group": "",
                "series_code": "", "geography": "National", "period": period,
                "frequency": "quarterly", "price_basis": basis,
                "seasonal_adjustment": "nsa", "measure": "level",
                "value": v, "unit": "XOF billion",
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
            tbls = [tb for tb in page.extract_tables() if len(tb) >= 8]
            for tb in tbls:
                rows.extend(_parse_table(tb, *spec))
    if not rows:
        raise ValueError("no GDP rows parsed from INSTAT Mali note")
    return pd.DataFrame.from_records(rows)[_OUT_COLS].drop_duplicates(
        ["approach", "category", "period", "price_basis"])
