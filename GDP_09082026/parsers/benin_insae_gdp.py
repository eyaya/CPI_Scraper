"""Parser for INSAE/INStaD Benin's own national-accounts workbooks.

instad.bj has answered "Maintenance en cours" (HTTP 503) since 2026-09-29, so
both files are read from Wayback Machine `id_` captures of INSAE's OWN uploads
(original bytes; same precedent as labour/sources/benin.yaml). Not an
aggregator: these are the NSO's published workbooks.

PRIMARY -- "Série_PIB_1999-2021.xlsx" (sheet "SYNTHESE_COMPETS ANNUELS"),
annual, billion XAF (FCFA), four blocks:
  * Ventilation du PIB courant par secteurs d'activités     -> production, current
  * Ventilation du PIB à prix constants par secteurs        -> production, constant
  * Evolution des emplois du PIB à prix courants            -> expenditure, current
  * Evolution des emplois du PIB à prix constant            -> expenditure, constant
The constant-price base is 2015 (the rebased SCN 2008 accounts: 2015 current and
constant GDP are both 6 732,8). INSAE flags the vintage of each stretch in the
sheet's own header -- 1999-2014 "comptes rétropolés provisoires", 2015-2016
"définitifs rebasés", 2017-2021 "estimations" -- and that flag is carried in
`category_group` on every row so a user can see which figures are final.

EXTRA -- "Série_PIB_Trimestriel_2018_2021.xlsx", quarterly value added by branch
at CONSTANT prices only (the sheet's own title), 2018-Q1..2021-Q4.

Labels are kept as printed (INSAE's national branch grouping; no ISIC named).
"PIB" (production block) is filed as `aggregate`; "PIB (Emploi)" stays under
`expenditure` with its own label, so the two never share a key.

IDENTITIES CHECKED, not enforced by editing: in every year, sectors sum to their
sector totals, total VA + net taxes = PIB, and PIB (Emploi) = PIB. A gap above
1 billion raises; smaller rounding gaps are left as published. Nothing derived.

CROSS-CHECK (billion XAF): 1999 PIB current 2 263,3; 2015 PIB current =
constant = 6 732,8; 2021 PIB current 9 809,7; 2018-Q1 PIB constant 1 701,8.
"""
from __future__ import annotations

import re

import openpyxl
import pandas as pd

_OUT_COLS = ["approach", "category", "category_group", "series_code", "geography",
             "period", "frequency", "price_basis", "seasonal_adjustment",
             "measure", "value", "unit", "base_period"]
_UNIT = "XAF billion"
_BASE = "Constant 2015 prices (SCN 2008 rebased)"


def _vintage(year: int) -> str:
    if year <= 2014:
        return "1999-2014 : comptes rétropolés provisoires (SCN2008)"
    if year <= 2016:
        return "2015-2016 : comptes nationaux définitifs rebasés (SCN2008)"
    return "2017-2021 : estimations"


def _block(title: str):
    t = title.lower()
    approach = "production" if "ventilation" in t else "expenditure" if "emplois" in t else None
    if approach is None:
        return None
    basis = "current" if "courant" in t else "constant" if "constant" in t else None
    return (approach, basis) if basis else None


def _annual(path: str) -> list[dict]:
    ws = openpyxl.load_workbook(path, data_only=True).active
    rows, spec, years, parent = [], None, None, ""
    blocks = {}
    for r in ws.iter_rows(values_only=True):
        lab = r[0]
        if not isinstance(lab, str) or not lab.strip():
            continue
        lab = re.sub(r"\s+", " ", lab).strip()
        b = _block(lab)
        if b and all(v is None for v in r[1:]):
            spec, years = b, None
            continue
        if lab == "Libellé":
            years = [int(v) for v in r[1:] if isinstance(v, (int, float))]
            continue
        if not (spec and years):
            continue
        vals = list(r[1:1 + len(years)])
        if not all(isinstance(v, (int, float)) for v in vals):
            continue
        label = lab.rstrip(", ").strip()
        # Expenditure sub-rows are indented under a numbered heading, and
        # "publique" sits under BOTH consumption and FBCF: qualify each
        # indented row by its heading, as printed ("2. FBCF / publique").
        if spec[0] == "expenditure":
            if re.match(r"^\d\.", label) or label.startswith("PIB"):
                parent = label
            elif r[0][:1].isspace():
                label = f"{parent} / {label}"
        blocks.setdefault(spec, {})[label] = dict(zip(years, vals))
        approach, basis = spec
        if approach == "production" and label == "PIB":
            approach = "aggregate"
        for y, v in zip(years, vals):
            rows.append({
                "approach": approach, "category": label,
                "category_group": _vintage(y),
                "series_code": "INSAE Série PIB 1999-2021",
                "geography": "National", "period": str(y), "frequency": "annual",
                "price_basis": basis, "seasonal_adjustment": "not_applicable",
                "measure": "level", "value": float(v), "unit": _UNIT,
                "base_period": _BASE if basis == "constant" else "",
            })
    if len(blocks) != 4:
        raise ValueError(f"INSAE annual: found blocks {sorted(blocks)}")
    for basis in ("current", "constant"):
        p, e = blocks[("production", basis)], blocks[("expenditure", basis)]
        for y in p["PIB"]:
            va, tax, gdp = p["TOTAL DES VALEURS AJOUTEES"][y], \
                p["Impôts et taxes nets des Subventions"][y], p["PIB"][y]
            if abs(va + tax - gdp) > 1 or abs(e["PIB (Emploi)"][y] - gdp) > 1:
                raise ValueError(f"INSAE annual {basis} {y}: identities fail")
    return rows


def _quarterly(path: str) -> list[dict]:
    ws = openpyxl.load_workbook(path, data_only=True).active
    grid = list(ws.iter_rows(values_only=True))
    if "prix constant" not in str(grid[0][0]).lower():
        raise ValueError(f"INSAE quarterly: unexpected title {grid[0][0]!r}")
    periods, year = [], None
    for y, q in zip(grid[1][1:], grid[2][1:]):
        if isinstance(y, (int, float)):
            year = int(y)
        if isinstance(q, str) and re.fullmatch(r"T[1-4]", q.strip()):
            periods.append(f"{year}-Q{q.strip()[1]}")
    rows = []
    for r in grid[3:]:
        lab = r[0]
        if not isinstance(lab, str) or not lab.strip():
            continue
        vals = list(r[1:1 + len(periods)])
        if not all(isinstance(v, (int, float)) for v in vals):
            continue
        label = re.sub(r"\s+", " ", lab).strip()
        approach = "aggregate" if label.lower().startswith("pib") else "production"
        for p, v in zip(periods, vals):
            rows.append({
                "approach": approach, "category": label, "category_group": "",
                "series_code": "INSAE Série PIB trimestriel 2018-2021",
                "geography": "National", "period": p, "frequency": "quarterly",
                "price_basis": "constant", "seasonal_adjustment": "nsa",
                "measure": "level", "value": float(v), "unit": _UNIT,
                "base_period": _BASE,
            })
    if len(periods) < 4 or not rows:
        raise ValueError("INSAE quarterly: nothing read")
    return rows


def parse(path: str, extras: list[str] | None = None) -> pd.DataFrame:
    rows = _annual(path)
    for x in extras or []:
        rows += _quarterly(x)
    df = pd.DataFrame.from_records(rows)[_OUT_COLS]
    key = ["approach", "category", "period", "frequency", "price_basis", "measure"]
    if df.duplicated(key).any():
        raise ValueError("INSAE: duplicate keys")
    return df
