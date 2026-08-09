"""Parser for the SNBS Somalia GDP CSVs (expenditure approach, annual).

Somalia's NBS publishes national accounts as tidy CSVs on its WordPress media
library (the same host as the CPI source). Somalia is a dollarised economy, so
GDP is reported in US dollars. We read four tables together (current-price levels
primary; real levels, growth rates and shares as extras), each shaped
'Expenditure items,<year>,<year>,…' with one component per row:

  GDP-Current-Prices  -> level, current   (million USD)
  GDP-Real-Table      -> level, constant  (million USD; base year not stated in
                         the file, left blank rather than guessed)
  GDP-Growth-Rate     -> growth_yoy (%)
  GDP-Shares          -> share (%)

Rows 'GDP at purchasers' prices', 'Gross national expenditure/income/disposable
income' are aggregates; 'GDP per capita, US Dollars' is a per-capita measure (unit
USD). Verified: 2025 GDP at purchasers' prices = 13,234.49 = HFC 16,307.09 + govt
1,162.47 + GFCF 2,960.34 + exports 2,688.76 - imports 9,884.17. Nothing derived.
"""
from __future__ import annotations
import csv
import os
import re
import pandas as pd

_OUT_COLS = ["approach", "category", "category_group", "series_code", "geography",
             "period", "frequency", "price_basis", "seasonal_adjustment",
             "measure", "value", "unit", "base_period"]


def _spec(filename: str):
    n = filename.lower()
    if "current" in n:
        return ("level", "current", "million USD")
    if "real" in n:
        return ("level", "constant", "million USD")
    if "growth" in n:
        return ("growth_yoy", "constant", "percent")
    if "share" in n:
        return ("share", "current", "percent")
    return None


def _read_csv(path, rows):
    spec = _spec(os.path.basename(path))
    if spec is None:
        return
    measure, basis, unit = spec
    with open(path, encoding="utf-8-sig", errors="replace", newline="") as f:
        reader = list(csv.reader(f))
    if not reader:
        return
    header = reader[0]
    years = [(i, h.strip()) for i, h in enumerate(header)
             if re.fullmatch(r"20\d\d", h.strip())]
    for row in reader[1:]:
        if not row or not row[0].strip():
            continue
        label = re.sub(r"\s+", " ", row[0]).strip()
        low = label.lower()
        row_measure, row_unit, row_basis = measure, unit, basis
        if "per capita" in low:
            row_measure, row_unit = "per_capita", "USD"
        approach = "aggregate" if ("gdp" in low or "gross national" in low) else "expenditure"
        for i, year in years:
            if i >= len(row):
                continue
            cell = row[i].strip().replace(",", "")
            if cell in ("", "-", "..", "n/a"):
                continue
            try:
                v = float(cell)
            except ValueError:
                continue
            rows.append({
                "approach": approach, "category": label, "category_group": "",
                "series_code": "", "geography": "National", "period": year,
                "frequency": "annual", "price_basis": row_basis,
                "seasonal_adjustment": "nsa", "measure": row_measure,
                "value": v, "unit": row_unit, "base_period": "",
            })


def parse(pdf_path: str, extras: list[str] | None = None) -> pd.DataFrame:
    rows = []
    _read_csv(pdf_path, rows)
    for ex in (extras or []):
        _read_csv(ex, rows)
    if not rows:
        raise ValueError("no GDP rows parsed from SNBS Somalia CSVs")
    return pd.DataFrame.from_records(rows)[_OUT_COLS].drop_duplicates(
        ["approach", "category", "period", "measure", "price_basis"])
