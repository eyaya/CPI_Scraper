"""Parser for the INS Niger 'Comptes économiques de la Nation' annual PDF.

The annex tables extract cleanly as text (line by line). We read the GDP (PIB)
level tables — each begins with a 'Tableau annexe N …' caption and a 'Libellés
<year> <year>' header, then rows of 'label  n1  n2' (French space-grouped
integers, millions of FCFA):

  Annexe 2  PIB par branche, prix courants       -> production current
  Annexe 3  PIB par branche, volume chaîné       -> production constant
  Annexe 6  Emplois du PIB (optique dépense)      -> expenditure
  Annexe 7  PIB nominal, optique revenu           -> income

Section headers set the approach/basis; the 'Produit Intérieur Brut' row is the
aggregate. A few long branch labels wrap across lines; those wrapped value-lines
carry no label and are skipped (never mislabelled). Everything as published.
"""
from __future__ import annotations
import re
import pdfplumber
import pandas as pd

_ANNEX_RE = re.compile(r"tableau\s*annexe\s*(\d+)", re.I)
_LIB_RE = re.compile(r"libell", re.I)
_YEAR_RE = re.compile(r"\b(20\d\d)\b")
_FRINT_RE = re.compile(r"\d{1,3}(?: \d{3})+")

_OUT_COLS = ["approach", "category", "category_group", "series_code", "geography",
             "period", "frequency", "price_basis", "seasonal_adjustment",
             "measure", "value", "unit", "base_period"]


def _spec(caption: str):
    c = caption.lower()
    if "optique revenu" in c:
        return ("income", "current", "level")
    if "emplois" in c and ("pense" in c or "épense" in c):
        return ("expenditure", "current", "level")
    if "par branche" in c or "par secteur" in c:
        if "volume" in c or "chaîn" in c or "chain" in c:
            return ("production", "constant", "level")
        if "courant" in c:
            return ("production", "current", "level")
    return None


# only the by-branch production tables (annex 2/3) extract cleanly; the
# expenditure (6) and income (7) annexes render each label letter-spaced with the
# values detached, so they aren't reliably parseable and are left for later.
_WANTED = {2, 3}


def parse(pdf_path: str) -> pd.DataFrame:
    rows, spec, years = [], None, None
    with pdfplumber.open(pdf_path) as pdf:
        for page in pdf.pages:
            for line in (page.extract_text() or "").split("\n"):
                am = _ANNEX_RE.search(line)
                if am:
                    n = int(am.group(1))
                    spec = _spec(line) if n in _WANTED else None
                    years = None
                    continue
                if spec is None:
                    continue
                if _LIB_RE.search(line):
                    ys = _YEAR_RE.findall(line)
                    if len(ys) >= 2:
                        years = ys
                    continue
                if years is None:
                    continue
                nums = _FRINT_RE.findall(line)
                if len(nums) < len(years):
                    continue
                label = re.sub(r"\s+", " ", line[:line.find(nums[0])]).strip(" .:-()%")
                if len(label) < 4 or _YEAR_RE.search(label):
                    continue
                approach, basis, measure = spec
                is_pib = "produit intérieur brut" in label.lower() or label.lower() == "pib"
                vals = nums[-len(years):]
                for year, tok in zip(years, vals):
                    rows.append({
                        "approach": "aggregate" if is_pib else approach,
                        "category": label, "category_group": "", "series_code": "",
                        "geography": "National", "period": year, "frequency": "annual",
                        "price_basis": basis, "seasonal_adjustment": "not_applicable",
                        "measure": measure, "value": float(tok.replace(" ", "")),
                        "unit": "XOF million",
                        "base_period": "volume chaîné" if basis == "constant" else "",
                    })
    if not rows:
        raise ValueError("no GDP rows parsed from INS Niger report")
    return pd.DataFrame.from_records(rows)[_OUT_COLS].drop_duplicates(
        ["approach", "category", "period", "measure", "price_basis"])
