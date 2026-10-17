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


def parse(pdf_path: str, extras: list[str] | None = None) -> pd.DataFrame:
    """The current edition, plus OLDER EDITIONS (extras) for the years it does
    not print.

    Each annual report prints only its two latest years, so the series is
    built from successive editions: the 2023 provisional accounts add 2022 and
    the 2022 definitive accounts ("révisés 2016-2021") add 2016-2021. Extras
    are read newest first, and an edition contributes ONLY the years no newer
    edition already gave -- so every year comes from the latest report that
    prints it. `category_group` names the edition each row came from, because
    branch labels and revisions differ between editions and a reader must be
    able to see where a year's figures were published.

    Only the by-branch current-price table (annexe 2) is readable in the older
    multi-year editions: their volume table (annexe 3), like the expenditure
    and income annexes here, renders letter-spaced with values detached.
    """
    df = _parse_one(pdf_path)
    have = set(df["period"])
    for ex in sorted(extras or [], key=_edition_year, reverse=True):
        old = _parse_one(ex)
        old = old[~old["period"].isin(have)]
        if old.empty:
            continue
        old["category_group"] = _edition_label(ex)
        have |= set(old["period"])
        df = pd.concat([df, old], ignore_index=True)
    return df


def _edition_year(path: str) -> int:
    m = re.search(r"(20\d\d)", path.rsplit("/", 1)[-1].rsplit("\\", 1)[-1])
    return int(m.group(1)) if m else 0


def _edition_label(path: str) -> str:
    name = path.replace("\\", "/").rsplit("/", 1)[-1].lower()
    if "definitif" in name:
        return f"INS Niger CEN définitifs {_edition_year(path)} (révisés antérieurs)"
    if "provisoire" in name:
        return f"INS Niger CEN provisoires {_edition_year(path)}"
    return f"INS Niger CEN {_edition_year(path)}"


def _parse_one(pdf_path: str) -> pd.DataFrame:
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
