"""Parser for the INSEED Comoros national-accounts CSVs (contributions + growth).

INSEED's 'Note sur les comptes nationaux' (Strapi CMS, same host as the CPI
source) exposes its two chart datafiles as CSVs — the only structured GDP data in
the note (the rest is narrative). Both are transposed (years down the rows,
components across the columns) and cover 2021-2023:

  graph1: label, primary, secondary, tertiary, net_taxes, pib
          -> production-side CONTRIBUTIONS to real GDP growth (percentage points)
  graph2: label, final_consumption, investment, net_exports, pib
          -> expenditure-side CONTRIBUTIONS to real GDP growth (percentage points)

The 'pib' column is real GDP growth itself (percent); the component columns are
contributions that sum to it. Verified: 2023 growth 3.1% = primary 0.7 + secondary
0.4 + tertiary 1.6 + net_taxes 0.3 (production side). This note carries no levels,
so only growth and contributions are captured. Nothing derived.
"""
from __future__ import annotations
import csv
import pandas as pd

_OUT_COLS = ["approach", "category", "category_group", "series_code", "geography",
             "period", "frequency", "price_basis", "seasonal_adjustment",
             "measure", "value", "unit", "base_period"]

_COLS = {
    "primary": ("Secteur primaire", "production"),
    "secondary": ("Secteur secondaire", "production"),
    "tertiary": ("Secteur tertiaire", "production"),
    "net_taxes": ("Impots nets sur les produits", "production"),
    "final_consumption": ("Consommation finale", "expenditure"),
    "investment": ("Investissement", "expenditure"),
    "net_exports": ("Exportations nettes", "expenditure"),
}


def _read_csv(path, rows):
    with open(path, encoding="utf-8-sig", errors="replace", newline="") as f:
        reader = list(csv.reader(f))
    if not reader:
        return
    header = [h.strip().lower() for h in reader[0]]
    for row in reader[1:]:
        if not row or not row[0].strip():
            continue
        year = row[0].strip()
        if not year.isdigit():
            continue
        for i, col in enumerate(header):
            if i == 0 or i >= len(row) or not row[i].strip():
                continue
            try:
                v = float(row[i].strip().replace(",", "."))
            except ValueError:
                continue
            if col == "pib":
                approach, category, measure, unit = (
                    "aggregate", "PIB", "growth_yoy", "percent")
            elif col in _COLS:
                category, approach = _COLS[col]
                measure, unit = "contribution", "percentage points"
            else:
                continue
            rows.append({
                "approach": approach, "category": category, "category_group": "",
                "series_code": "", "geography": "National", "period": year,
                "frequency": "annual", "price_basis": "constant",
                "seasonal_adjustment": "nsa", "measure": measure,
                "value": v, "unit": unit, "base_period": "",
            })


def parse(pdf_path: str, extras: list[str] | None = None) -> pd.DataFrame:
    rows = []
    _read_csv(pdf_path, rows)
    for ex in (extras or []):
        _read_csv(ex, rows)
    if not rows:
        raise ValueError("no GDP rows parsed from INSEED Comoros CSVs")
    return pd.DataFrame.from_records(rows)[_OUT_COLS].drop_duplicates(
        ["approach", "category", "period", "measure"])
