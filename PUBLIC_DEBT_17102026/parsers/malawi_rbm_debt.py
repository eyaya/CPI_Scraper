"""Malawi -- Reserve Bank of Malawi, Statistics > Economic Data > External
Debt: "Central Government External Debt" workbook.

PUBLISHER: Reserve Bank of Malawi. COVERAGE: central government EXTERNAL debt
only, as the file's title states -- domestic debt is not in this file.

One sheet, "In Millions of Malawi Kwacha", one row per year from 1984:
Total External Debt, Multilateral Debt, Bilateral Debt, Commercial Debt (all
stocks -> measure `stock`, unit "MWK million"), then Debt Service and Interest
Payment -- FLOWS, which this schema has no measure for, so they are not
collected.

As published: kwacha values carry the 1994 and later devaluations, and the
2006 fall (373 219.6 -> 67 541.5) is HIPC/MDRI debt relief, not an error;
values from 2009 carry float residue (179757.87652) and are kept as stored.
Commercial debt prints 0 in 2014-15 (kept: a published zero). Every year is
checked: multilateral + bilateral + commercial = total, to MWK 1 million.

CROSS-CHECK: 1984 total 980.6 (multilateral 637.3); 2005 373 219.63;
2006 67 541.52; 2023 5 887 049.29 (multilateral 4 990 902.16).
"""
from __future__ import annotations

import re

import openpyxl
import pandas as pd

_UNIT = "MWK million"
_STOCKS = ["Total External Debt", "Multilateral Debt", "Bilateral Debt",
           "Commercial Debt"]


def parse(path: str, extras=None) -> pd.DataFrame:
    ws = openpyxl.load_workbook(path, data_only=True).worksheets[0]
    rows = [list(r) for r in ws.iter_rows(values_only=True)]
    if not any("Millions of Malawi Kwacha" in str(c) for c in rows[0] if c):
        raise ValueError(f"RBM: unit line changed: {rows[0]!r}")
    hdr_i = next(i for i, r in enumerate(rows) if r and str(r[0]).strip().upper() == "YEAR")
    hdr = [str(c).strip() if c is not None else "" for c in rows[hdr_i]]
    idx = {name: hdr.index(name) for name in _STOCKS}
    out = []
    for r in rows[hdr_i + 1:]:
        y = str(r[0]).strip() if r[0] is not None else ""
        if not re.fullmatch(r"\d{4}", y):
            continue
        vals = {n: float(r[i]) for n, i in idx.items() if r[i] not in (None, "")}
        if len(vals) != len(_STOCKS):
            raise ValueError(f"RBM {y}: missing stock cells {set(_STOCKS) - set(vals)}")
        parts = vals["Multilateral Debt"] + vals["Bilateral Debt"] + vals["Commercial Debt"]
        if abs(parts - vals["Total External Debt"]) > 1.0:
            raise ValueError(f"RBM {y}: components {parts} != total "
                             f"{vals['Total External Debt']}")
        for n, v in vals.items():
            out.append({"component": n, "period": y, "frequency": "annual",
                        "measure": "stock", "value": v, "unit": _UNIT,
                        "series_code": "RBM ext debt"})
    if len(out) < 4 * 30:
        raise ValueError(f"RBM: only {len(out) // 4} years read")
    return pd.DataFrame(out)
