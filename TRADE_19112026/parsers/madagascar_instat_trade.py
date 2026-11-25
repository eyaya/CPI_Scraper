"""Parser for INSTAT Madagascar "Tableau de Bord de l'Economie" (TBE) workbook.

Sheets "Sortieexport" (Tableau 32, exports FOB) and "Sortieimport" (Tableau 33,
imports CAF): monthly values in millions of ariary for the last 24 months, total
and the TBE's own product lines (vanille, crevette, café, girofle, produits
miniers, zones franches / riz, sucre, énergie, équipement, ciment ...).
Columns are located from the header row's labels; the "Cumul jan-<mois>"
year-to-date rows and the variation row are not read. Note the month dates are
stored as mid-month Excel dates (2024-04-15): only year and month are used.
"""
from __future__ import annotations

import datetime as dt
import re

import openpyxl
import pandas as pd

from ._common import row

_SHEETS = {"sortieexport": ("export", "fob"), "sortieimport": ("import", "cif")}


def parse(path: str, extras: list[str] | None = None) -> pd.DataFrame:
    from ..schema import KEY
    frames = []
    for p in dict.fromkeys([*(extras or []), path]):
        wb = openpyxl.load_workbook(p, read_only=True, data_only=True)
        out = []
        try:
            for name in wb.sheetnames:
                spec = _SHEETS.get(name.strip().lower())
                if not spec:
                    continue
                flow, basis = spec
                rows = [list(r) for r in wb[name].iter_rows(values_only=True)]
                title = next((str(c) for r in rows[:3] for c in r if c), "")
                if "millions d'ariary" not in title.lower():
                    continue
                hi = next(i for i, r in enumerate(rows) if any(str(c or "").strip().lower().startswith("total en valeur") for c in r))
                cols = [(j, str(c).strip()) for j, c in enumerate(rows[hi]) if c and str(c).strip()]
                for r in rows[hi + 1:]:
                    d = next((c for c in r[:3] if isinstance(c, dt.datetime)), None)
                    if d is None:
                        continue
                    per = f"{d.year}-{d.month:02d}"
                    for j, lab in cols:
                        v = r[j] if j < len(r) else None
                        if not isinstance(v, (int, float)):
                            continue
                        com = None if lab.lower().startswith("total") else lab
                        out.append(row(tradeflow=flow, period=per, frequency="monthly", value=v, unit="MGA",
                                       unit_multiplier=1e6, commodity=com,
                                       commodity_classification="national" if com else "",
                                       price_basis=basis, series_code=name.strip()))
        finally:
            wb.close()
        if out:
            df = pd.DataFrame(out)
            frames.append((df["period"].max(), df))
    frames.sort(key=lambda t: t[0])
    df = pd.concat([f for _, f in frames], ignore_index=True)
    return df.drop_duplicates(KEY, keep="last").reset_index(drop=True)
