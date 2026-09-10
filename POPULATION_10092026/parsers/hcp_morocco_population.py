"""HCP Morocco — national population by single-year age & sex (Tier-2 Excel).

Parser for the Haut-Commissariat au Plan workbook "Projections de la population
totale du Maroc par age simple et sexe 2014-2050" (published as a Google Sheet).
Layout (one sheet "Population totale"):
  row 0: year, repeated three times per year (2014..2050)
  row 1: sub-header Masculin | Feminin | Total, per year
  col 0: age (0..79, then "80+", then "Total")
Each year occupies a triplet of columns (Masculin, Feminin, Total).
"""
from __future__ import annotations
import re
import pandas as pd


def _num(v):
    if pd.isna(v):
        return None
    try:
        return int(round(float(v)))
    except (ValueError, TypeError):
        s = re.sub(r"[^\d]", "", str(v))
        return int(s) if s else None


def _age(v):
    if isinstance(v, str):
        s = v.strip()
        if s.lower() == "total":
            return "Total"
        return s                      # "80+"
    if pd.isna(v):
        return None
    return str(int(v))


def parse(local_path: str) -> pd.DataFrame:
    df = pd.read_excel(local_path, sheet_name="Population totale", header=None)
    years = df.iloc[0]
    out = []
    for j in range(1, df.shape[1], 3):
        year = years.iloc[j]
        if pd.isna(year):
            continue
        period = str(int(year))
        for i in range(2, df.shape[0]):
            age = _age(df.iloc[i, 0])
            if age is None:
                continue
            male = _num(df.iloc[i, j])
            female = _num(df.iloc[i, j + 1]) if j + 1 < df.shape[1] else None
            total = _num(df.iloc[i, j + 2]) if j + 2 < df.shape[1] else None
            if male is None or female is None or total is None:
                continue
            if abs(male + female - total) > 5:
                continue
            for sex, val in (("male", male), ("female", female), ("total", total)):
                out.append({
                    "series_type": "projection", "sex": sex, "age_group": age,
                    "geography": "Total country", "period": period,
                    "frequency": "annual", "measure": "count", "value": float(val),
                    "unit": "persons", "series_code": "MA_HCP_PROJ_AGESEX",
                })

    result = pd.DataFrame(out)
    if result.empty:
        raise ValueError("hcp_morocco_population: no rows parsed")
    return result
