"""Parser for INS Congo's quarterly national-accounts note (Comptes Nationaux
Trimestriels, "CNT"), PDF, French.

Production approach, 20 branches (incl. SIFIM), données brutes (not seasonally
adjusted), billion XAF (FCFA). The note's three annex tables each print seven
quarterly levels followed by six year-on-year rates (T/T-4) and two annual
rates, under one header:

  Tableau 1  PIB trimestriel en volume chaîné (référence 2005)
             -> constant levels + real growth_yoy (quarterly and annual)
  Tableau 2  PIB trimestriel à prix courants
             -> current levels. Its rate columns are DEFLATOR variations, which
                this schema has no measure for (a `deflator` is an index), so
                they are not collected.
  Tableau 3  PIB trimestriel et contribution à la croissance
             -> contributions to real GDP growth (percentage points). Its level
                columns repeat Tableau 2 and are checked equal, not re-emitted.

Periods come from the table's own header ("T2_2024" ... "T4_2025",
"Année_2024/ Année_2023"), never from the file name. Each note republishes the
last seven quarters, revised: the newest note wins.

PUBLISHED AS IS: the chained-volume "PIB Pétrole" + "PIB hors Pétrole" do not
add to "PIB" (chain-linked volumes are not additive), and Tableau 3's annual
"Total VA" contribution (1,6 for 2025) differs from PIB's (3,4). Nothing is
recomputed. Branch labels are INS's own CNT nomenclature (no ISIC named).

CROSS-CHECK: PIB T4_2025 current 2 072,3, chained volume 1 200,3; real growth
T4_2025 5,3%, 2025 annual 3,4%; extraction des hydrocarbures current T4_2025
490,3.
"""
from __future__ import annotations

import re

import pandas as pd
import pdfplumber

_OUT_COLS = ["approach", "category", "category_group", "series_code", "geography",
             "period", "frequency", "price_basis", "seasonal_adjustment",
             "measure", "value", "unit", "base_period"]
_CAP = re.compile(r"^Tableau\s*([123])\s*:\s*PIB trimestriel", re.M)
_NUM = r"-?\d+(?:,\d+)?"
_ROW = re.compile(rf"^(\D+?)\s+((?:{_NUM}\s+){{14}}{_NUM})$")
_AGG = {"PIB", "PIB Pétrole", "PIB hors Pétrole"}


def _f(t: str) -> float:
    return float(t.replace(",", "."))


def _table(text: str):
    head = text[:1200]
    quarters = [f"{y}-Q{q}" for q, y in re.findall(r"T([1-4])_(\d{4})", head)]
    years = re.findall(r"Année_(\d{4})/", head)
    if len(quarters) != 13 or len(years) < 2:
        raise ValueError(f"CNT: header gives {quarters} / {years}")
    levels, growth = quarters[:7], quarters[7:]
    annual = years[-2:] if len(years) == 2 else [years[0], years[2]]
    rows = {}
    for ln in text.splitlines():
        m = _ROW.match(ln.strip())
        if m:
            rows[m.group(1).strip()] = [_f(v) for v in m.group(2).split()]
    return levels, growth, annual, rows


def parse(pdf_path: str) -> pd.DataFrame:
    tables = {}
    with pdfplumber.open(pdf_path) as pdf:
        for page in pdf.pages:
            t = page.extract_text() or ""
            m = _CAP.search(t)
            if m and "....." not in t[m.start():m.start() + 200]:
                tables[m.group(1)] = _table(t[m.start():])
    if set(tables) != {"1", "2", "3"}:
        raise ValueError(f"CNT: tables found {sorted(tables)}")
    for n, (_, _, _, rows) in tables.items():
        if len(rows) < 20 or "PIB" not in rows:
            raise ValueError(f"CNT Tableau {n}: only {len(rows)} rows")
    if {k: v[:7] for k, v in tables["2"][3].items()} != \
            {k: v[:7] for k, v in tables["3"][3].items()}:
        raise ValueError("CNT: Tableau 3 levels no longer repeat Tableau 2")

    out = []

    def emit(label, period, freq, basis, measure, value, unit, base, code):
        out.append({
            "approach": "aggregate" if label in _AGG else "production",
            "category": label, "category_group": "", "series_code": code,
            "geography": "National", "period": period, "frequency": freq,
            "price_basis": basis, "seasonal_adjustment": "nsa"
            if freq == "quarterly" else "not_applicable",
            "measure": measure, "value": value, "unit": unit,
            "base_period": base})

    base = "chained volume, reference 2005"
    lv, gr, an, rows = tables["1"]
    for lab, v in rows.items():
        for p, x in zip(lv, v[:7]):
            emit(lab, p, "quarterly", "constant", "level", x, "XAF billion",
                 base, "INS CNT T1")
        for p, x in zip(gr, v[7:13]):
            emit(lab, p, "quarterly", "constant", "growth_yoy", x, "percent",
                 "", "INS CNT T1")
        for p, x in zip(an, v[13:15]):
            emit(lab, p, "annual", "constant", "growth_yoy", x, "percent",
                 "", "INS CNT T1")
    lv, gr, an, rows = tables["2"]
    for lab, v in rows.items():
        for p, x in zip(lv, v[:7]):
            emit(lab, p, "quarterly", "current", "level", x, "XAF billion",
                 "", "INS CNT T2")
    lv, gr, an, rows = tables["3"]
    for lab, v in rows.items():
        for p, x in zip(gr, v[7:13]):
            emit(lab, p, "quarterly", "constant", "contribution", x,
                 "percentage points", "", "INS CNT T3")
        for p, x in zip(an, v[13:15]):
            emit(lab, p, "annual", "constant", "contribution", x,
                 "percentage points", "", "INS CNT T3")
    return pd.DataFrame.from_records(out)[_OUT_COLS]
