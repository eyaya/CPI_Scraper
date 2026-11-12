"""Rwanda -- NISR "PPI time series" workbook (monthly, December 2010 onward).

Three index sheets, each "Index ID | ISIC rev. 4 Description | Weights | one
column per month" (dates in row 3, read as dates; NISR stamps some months on
the 2nd, "2026-07-02" -- the month is what counts):
  PPI_ALLRwanda -> index_variant output ("Rwanda" = all products, weights per mille)
  PPI_Local     -> domestic_market ("Local Index")
  PPI_Export    -> export ("Exports")
The other sheets ("Public_Tables_...") are 2013-14 release templates, left
unread. The workbook prints no base period, so base_period stays blank.
Index IDs are NISR's own ("RC10" = manufacture of food products).
"""
from __future__ import annotations

import datetime as dt

import pandas as pd

from . import _common as C

_SHEETS = {"PPI_ALLRWANDA": ("output", "Producer Price Index (PPI), all products"),
           "PPI_LOCAL": ("domestic_market", "Producer Price Index (PPI), local products"),
           "PPI_EXPORT": ("export", "Producer Price Index (PPI), export products")}
_TOTAL = {"rwanda", "local index", "exports"}


def parse(path: str) -> pd.DataFrame:
    book = pd.read_excel(path, sheet_name=None, header=None)
    out = []
    for name, df in book.items():
        spec = _SHEETS.get(name.strip().upper())
        if not spec:
            continue
        variant, index_name = spec
        hdr = next(i for i in range(len(df)) if sum(isinstance(v, (dt.datetime, pd.Timestamp))
                                                    for v in df.iloc[i].tolist()) >= 12)
        cols = {j: f"{v.year}-{v.month:02d}" for j, v in enumerate(df.iloc[hdr].tolist())
                if isinstance(v, (dt.datetime, pd.Timestamp))}
        if len(set(cols.values())) != len(cols):
            raise ValueError(f"{path} {name}: two columns fall in one month")
        for i in range(hdr + 1, len(df)):
            code, label, w = df.iat[i, 0], df.iat[i, 1], df.iat[i, 2]
            if not isinstance(label, str) or not label.strip():
                continue
            label = " ".join(label.split())
            ind = "All industries" if label.lower() in _TOTAL else label
            code = str(code).strip() if isinstance(code, str) else ""
            last = None
            for j, p in cols.items():
                v = C.to_number(df.iat[i, j])
                if v is None or v != v:
                    continue
                last = p
                out.append(C.row(index_name=index_name, index_variant=variant, industry=ind,
                                 industry_code_nso=code, period=p, frequency="monthly",
                                 measure="index", value=v))
            wv = C.to_number(w)
            if wv is not None and wv == wv and last:
                out.append(C.row(index_name=index_name, index_variant=variant, industry=ind,
                                 industry_code_nso=code, period=max(cols.values()),
                                 frequency="monthly", measure="weight", value=wv, unit="per_mille"))
    if len(out) < 500:
        raise ValueError(f"{path}: only {len(out)} values")
    return pd.DataFrame(out)
