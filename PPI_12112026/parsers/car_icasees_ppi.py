"""Central African Republic -- ICASEES "Indice de prix de la production
industrielle (IPPI), année de base 2017", the calculation workbook ICASEES
publishes (zip -> IPPI-annee-de-Base-2017.xlsx), MONTHLY January 2017 ..
December 2020, NAEMA rév.1 / NOPEMA rév.1.

Sheets read (index = the cell values as stored, base: 2017 annual average = 100):
  "Indice global"        ENSEMBLE
  "Indices div regroup"  9 grouped divisions (10-12 agro-alimentaires ... 36 eau)
  "Indices divisions"    13 NAEMA divisions (10, 11, 12, 16, 18, 20, 21, 24, 25,
                         31, 35, 36); 35 and 36 repeat the grouped division of
                         the same code and label -- taken once.
NOT READ:
  * the quarterly columns ICASEES places after each year ("T1-19" ...): they
    contradict the months beside them (the global sheet's "T1-20" is 95,848,
    its Jan-Mar 2020 months 94,09 / 94,12 / 94,19) and the type-d'industrie
    sheet labels its 2020 quarters "T1-19 .. T4-19";
  * "Indices type ind": its one row is labelled "10-33 INDUSTRIES
    MANUFACTURIÈRES", weight 10000, but its values ARE the ENSEMBLE (which
    covers 10-36) -- a mislabelled copy;
  * products, gammes, classes, groupes (below the division);
  * "Indice moyen annuel 2017" (100, the base).
TAKEN SINCE 2026-11-08: the Pondérations, per ten thousand as stored
(ENSEMBLE 10000), unit per_ten_thousand, period 2017 (the base year).
"""
from __future__ import annotations

import datetime as dt

import openpyxl
import pandas as pd

from . import _common as C

INDEX_NAME = "Indice de prix de la production industrielle (IPPI)"
BASE = "2017=100"


def _sheet(ws, label_col: int, code_col: int | None, weights: list | None = None):
    rows = list(ws.iter_rows(values_only=True))
    hi = next(i for i, r in enumerate(rows) if any(isinstance(v, dt.datetime) for v in r))
    months = {j: v for j, v in enumerate(rows[hi]) if isinstance(v, dt.datetime)}
    # The weight sits right of the label, under a "Pondération..." header.
    wcol = label_col + 1
    if not str(rows[hi][wcol] or "").startswith("Pond"):
        raise ValueError(f"{ws.title}: no 'Pondération' column beside the labels")
    out = []
    for r in rows[hi + 1:]:
        lab = r[label_col]
        if lab is None or str(lab).strip() == "":
            continue
        code = "" if code_col is None or r[code_col] is None else str(r[code_col]).strip()
        w = C.to_number(r[wcol])
        if weights is not None and w is not None:
            weights.append((str(lab).strip(), code, w))
        for j, m in months.items():
            v = C.to_number(r[j])
            if v is not None:
                out.append((str(lab).strip(), code, f"{m.year}-{m.month:02d}", v))
    return out


def parse(path: str) -> pd.DataFrame:
    if path.lower().endswith(".zip"):
        import os
        import zipfile
        d = os.path.join(os.path.dirname(path), os.path.splitext(os.path.basename(path))[0])
        with zipfile.ZipFile(path) as z:
            name = next(n for n in z.namelist() if n.lower().endswith(".xlsx"))
            z.extract(name, d)
        path = os.path.join(d, name)
    wb = openpyxl.load_workbook(path, data_only=True, read_only=True)
    wts: list = []
    got = _sheet(wb["Indice global"], 0, None, wts)
    got += _sheet(wb["Indices div regroup"], 2, 1, wts)
    seen = {(lab, code) for lab, code, _, _ in got}
    dw: list = []
    got += [g for g in _sheet(wb["Indices divisions"], 2, 1, dw) if (g[0], g[1]) not in seen]
    wts += [x for x in dw if (x[0], x[1]) not in seen]
    wb.close()
    recs = [C.row(index_name=INDEX_NAME, industry=lab, industry_code_nso=code, period=p,
                  frequency="monthly", measure="index", value=v, base_period=BASE)
            for lab, code, p, v in got]
    # Weights per ten thousand as stored (ENSEMBLE 10000), filed under the base year.
    recs += [C.row(index_name=INDEX_NAME, industry=lab, industry_code_nso=code, period="2017",
                   frequency="annual", measure="weight", value=w, unit="per_ten_thousand",
                   base_period=BASE) for lab, code, w in wts]
    df = pd.DataFrame(recs)
    if df.duplicated(["industry", "period", "measure"]).any():
        raise ValueError("a label repeats across levels with different codes")
    return df
