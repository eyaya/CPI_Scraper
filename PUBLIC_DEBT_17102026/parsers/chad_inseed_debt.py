"""Chad -- INSEED Annuaire Statistique National 2024, Tableau 13 "Situation de
la dette en 2023 et 2024 (en %)", source line "Direction Générale du
Trésor/Direction de la Dette".

WHY THE YEARBOOK. The Finance Ministry's own site (finances.gouv.td) answers
404 and the Wayback Machine holds an article announcing a 2020-Q1 debt bulletin
but no captured file. The statistics office's yearbook reprints the Treasury's
Debt Directorate figures with that credit line. BEAC's "Principaux indicateurs"
workbook for Chad was rejected: it is sourced "Administrations nationales et
BEAC" (a joint compilation, not a credited reprint) and its total-debt row is
offset two columns against its external-debt row.

COVERAGE: "dette publique", the Debt Directorate's perimeter, not further
stated. Only the three STOCK ratios are collected -- public, domestic and
external debt outstanding as a percent of GDP. The interest and debt-service
ratios beneath them are flows and are out of scope. No amounts are published
in the table, only ratios.

Only the 2024 edition carries the table (the 2019-20 to 2023 editions have no
debt section).

CROSS-CHECK: public debt 28,6 % of GDP (2023), 29,1 % (2024); domestic 15,2 /
13,5; external 13,4 / 15,6 -- and domestic + external = public in both years.
"""
from __future__ import annotations

import re

import pandas as pd
import pdfplumber

_ROWS = {
    "Encours de la dette publique en % du PIB": "Encours de la dette publique",
    "Encours de la dette intérieure en % du PIB": "Encours de la dette intérieure",
    "Encours de la dette extérieure en % du PIB": "Encours de la dette extérieure",
}
_LINE = re.compile(r"^(Encours de la dette (?:publique|intérieure|extérieure) en % du PIB)\s+"
                   r"(\d+,\d)\s+(\d+,\d)$")


def parse(path: str, extras: list[str] | None = None) -> pd.DataFrame:
    years, vals = None, {}
    with pdfplumber.open(path) as pdf:
        for page in pdf.pages[30:60]:
            t = page.extract_text() or ""
            m = re.search(r"Tableau \d+ ?: ?Situation de la dette en (20\d\d) et (20\d\d)", t)
            if m and not re.search(r"\.{6}", t):
                years = [m.group(1), m.group(2)]
            for ln in t.splitlines():
                r = _LINE.match(ln.strip())
                if r:
                    vals[r.group(1)] = [float(r.group(2).replace(",", ".")),
                                        float(r.group(3).replace(",", "."))]
            if years and len(vals) == 3:
                break
    if not years or set(vals) != set(_ROWS):
        raise ValueError(f"INSEED Tableau 13: years {years}, rows {sorted(vals)}")
    pub, dom, ext = (vals[k] for k in _ROWS)
    for j, y in enumerate(years):
        if abs(dom[j] + ext[j] - pub[j]) > 0.15:
            raise ValueError(f"INSEED Tableau 13 {y}: {dom[j]} + {ext[j]} != {pub[j]}")
    rows = []
    for label, comp in _ROWS.items():
        for y, v in zip(years, vals[label]):
            rows.append({"component": comp, "period": y, "frequency": "annual",
                         "measure": "share_of_gdp", "value": v, "unit": "percent",
                         "series_code": "INSEED Annuaire T13"})
    return pd.DataFrame(rows)
