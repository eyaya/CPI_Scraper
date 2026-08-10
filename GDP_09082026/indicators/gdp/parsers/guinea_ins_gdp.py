"""Parser for the INS Guinea quarterly national-accounts (CNT) PDF (French).

This note publishes RATES, not levels: GDP (PIB) by sector of activity as
year-on-year (T/T-4) percentage changes and contributions. We read them as text
lines ('label  v1 v2 …'); the quarterly columns come from the 'Tn_YYYY' header
(13 quarters), which we take as the leading values (trailing annual columns are
left out to avoid ambiguity).

  Tableau 1  Variations du PIB réel (volume) par secteur   -> real YoY growth
  Tableau 3  Contribution à la croissance du PIB            -> contribution

Values are percent. The deflator-variation table (2) is skipped. Everything as
published; nothing derived.
"""
from __future__ import annotations
import re
import pdfplumber
import pandas as pd

_PERIOD_RE = re.compile(r"T([1-4])[_ ](20\d\d)")
_NUM_RE = re.compile(r"-?\d+(?:,\d+)?")

_OUT_COLS = ["approach", "category", "category_group", "series_code", "geography",
             "period", "frequency", "price_basis", "seasonal_adjustment",
             "measure", "value", "unit", "base_period"]


def _spec(caption: str):
    c = caption.lower()
    if "contribution" in c:
        return ("contribution", "constant")
    if "en volume" in c or "chaîn" in c or "chain" in c:
        return ("growth_yoy", "constant")
    return None                                   # tableau 2 = deflator variation


def parse(pdf_path: str) -> pd.DataFrame:
    rows, spec, periods = [], None, None
    with pdfplumber.open(pdf_path) as pdf:
        for page in pdf.pages:
            text = page.extract_text() or ""
            cap = next((l for l in text.split("\n")
                        if re.search(r"tableau\s*\d", l, re.I)), "")
            page_spec = _spec(cap) if cap else None
            if cap:
                spec, periods = page_spec, None
            if spec is None:
                continue
            for line in text.split("\n"):
                q = [f"{m.group(2)}-Q{m.group(1)}"
                     for m in _PERIOD_RE.finditer(re.sub(r"\s+", " ", line))]
                if len(q) >= 8:
                    seen = set(); periods = [p for p in q if not (p in seen or seen.add(p))]
                    continue
                if periods is None:
                    continue
                nums = _NUM_RE.findall(line)
                label = re.sub(r"\s+", " ", line[:line.find(nums[0])]).strip(" .:-()%") if nums else ""
                if len(label) < 3 or len(nums) < len(periods) or _PERIOD_RE.search(label):
                    continue
                measure, basis = spec
                low = label.lower()
                approach = "aggregate" if low == "pib" or "produit intérieur brut" in low else "production"
                for period, tok in zip(periods, nums[:len(periods)]):
                    rows.append({
                        "approach": approach, "category": label, "category_group": "",
                        "series_code": "", "geography": "National", "period": period,
                        "frequency": "quarterly", "price_basis": basis,
                        "seasonal_adjustment": "nsa", "measure": measure,
                        "value": float(tok.replace(",", ".")),
                        "unit": "percentage points" if measure == "contribution" else "percent",
                        "base_period": "",
                    })
    if not rows:
        raise ValueError("no GDP rows parsed from INS Guinea note")
    return pd.DataFrame.from_records(rows)[_OUT_COLS].drop_duplicates(
        ["approach", "category", "period", "measure"])
