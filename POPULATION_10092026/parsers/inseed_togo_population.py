"""INSEED Togo RGPH-5 2022 — national population by age & sex (Tier-3 PDF).

Parser for "Publications du RGPH-5, Livret 01 (Repartition ... par sexe)", the
NIVEAU NATIONAL page, Tableau 1 ("Effectif de la population du Togo par groupe
d'ages, milieu de residence et sexe"). The table is fully ruled; pdfplumber's
lines strategy yields 10 columns:
  age | Urbain(H,F,Ens) | Rural(H,F,Ens) | Total(H,F,Ens)
We take the Total (national) columns. French numbers are space-grouped. The row
"ND" is age-not-stated (kept as published); "Total" is the national total.
"""
from __future__ import annotations
import re
import pdfplumber
import pandas as pd

_TABLE_SETTINGS = {"vertical_strategy": "lines", "horizontal_strategy": "lines"}
_AGE_RE = re.compile(r"^\d{1,2}\s*-\s*\d{1,2}$|^\d{1,2}\s*an[s]?$|^\d{1,2}\s*et\s*\+$")


def _num(cell):
    if cell is None:
        return None
    s = re.sub(r"\s+", "", str(cell))
    return int(s) if re.fullmatch(r"\d+", s) else None


def _age_label(raw):
    s = raw.strip()
    if s.lower() == "total":
        return "Total"
    if s.upper() == "ND":
        return "Not stated"
    if re.fullmatch(r"\d+\s*an[s]?", s, re.I):
        return re.sub(r"\s*an[s]?", "", s, flags=re.I)          # "0 an" -> "0"
    if re.match(r"\d{1,2}\s*et\s*\+", s):
        return re.sub(r"\s*et\s*\+", "+", s)                     # "85 et +" -> "85+"
    if re.fullmatch(r"\d{1,2}\s*-\s*\d{1,2}", s):
        return re.sub(r"\s*-\s*", "-", s)
    return None


def parse(local_path: str) -> pd.DataFrame:
    rows = None
    with pdfplumber.open(local_path) as pdf:
        for p in pdf.pages:
            txt = p.extract_text() or ""
            if "NIVEAU NATIONAL" not in txt.upper():
                continue
            tbl = p.extract_table(_TABLE_SETTINGS)
            if tbl and any((r[0] or "").strip().lower() == "total" for r in tbl):
                rows = tbl
                break
    if rows is None:
        raise ValueError("inseed_togo_population: NIVEAU NATIONAL age-sex table not found")

    out = []
    for r in rows:
        if len(r) < 10:
            continue
        age = _age_label(r[0] or "")
        if age is None:
            continue
        male, female, total = _num(r[7]), _num(r[8]), _num(r[9])
        if male is None or female is None or total is None:
            continue
        if abs(male + female - total) > 5:
            continue
        for sex, v in (("male", male), ("female", female), ("total", total)):
            out.append({
                "series_type": "census", "sex": sex, "age_group": age,
                "geography": "Total country", "period": "2022",
                "frequency": "annual", "measure": "count", "value": float(v),
                "unit": "persons", "series_code": "TG_RGPH5_L1T1",
            })

    df = pd.DataFrame(out)
    if df.empty:
        raise ValueError("inseed_togo_population: no rows parsed")
    return df
