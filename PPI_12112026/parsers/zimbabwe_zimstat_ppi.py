"""Zimbabwe -- ZimStat monthly Producer Price Index (PPI, industry) and Producer
Price Index for Agriculture (PPIA), Excel releases.

ZimStat compiles each index in three currency versions, each its own series:
  USD       prices in US dollars        (PPI January 2023=100, PPIA Apr 2023=100)
  ZWG       prices in Zimbabwe Gold     (April 2024=100, from the ZWG's launch)
  Weighted  the two combined by currency share (April 2024=100)
`index_name` names the index and the version ("USD Producer Price Index",
"Producer Price Index for Agriculture, ZWG"); base_period is as printed.

Each workbook carries the WHOLE history of its version, so the latest release
of each is read:
  detail sheet ("PPI 2" / "PPIA_2"): one row per industry (ISIC-style labels,
      no codes), its weight, and one column per month since the base month.
      -> index (monthly) and weight (filed as the base year, frequency annual).
  summary sheet ("PPI 1" / "PPIA_1"): section indices by month, annual
      averages, and the ALL ITEMS rate of change on the previous month and on
      a year earlier. -> All items inflation_mom / inflation_yoy, and the
      annual-average All items index (frequency annual). The summary's section
      columns repeat the detail sheet's section rows under other names
      ("Food stuffs" / "MANUFACTURE OF FOOD PRODUCTS") and are not read twice.
"All Item Index" / "All  ITEMS" is filed as "All items". A label printed twice
with identical values (a division and its only class, "Manufacture of tobacco
products") is read once; twice with DIFFERENT values (a group and a narrower
class, "Spinning, weaving and finishing of textiles") both are kept, the later
one as "<label> [repeat 2]".
"""
from __future__ import annotations

import datetime as dt
import os
import re

import pandas as pd

from . import _common as C

_ALL = re.compile(r"^all\s+items?(\s+weighted)?(\s+index)?$", re.I)


def _version(path: str) -> str:
    n = os.path.basename(path).upper()
    for v in ("USD", "ZWG", "WEIGHTED"):
        if f"_{v}_" in n or f" _{v}_" in n:
            return "Weighted" if v == "WEIGHTED" else v
    raise ValueError(f"no currency version in {path}")


def _period(h) -> str | None:
    if isinstance(h, (dt.datetime, pd.Timestamp)):
        return f"{h.year:04d}-{h.month:02d}"
    return C.month_period(str(h)) if isinstance(h, str) else None


def _label(x) -> str:
    s = re.sub(r"\s+", " ", str(x)).strip()
    return "All items" if _ALL.match(s) else s


def parse(path: str, extras: list[str] | None = None) -> pd.DataFrame:
    out = []
    for p in [path] + list(extras or []):
        out += _workbook(p)
    df = pd.DataFrame(out)
    dup = df.duplicated(["index_name", "industry", "frequency", "measure", "period"]).sum()
    if dup:
        raise ValueError(f"{dup} duplicate rows -- an industry label repeats")
    return df


def _workbook(path: str) -> list[dict]:
    sheets = pd.read_excel(path, sheet_name=None, header=None)
    names = {k.strip(): k for k in sheets}
    agri = any(k.startswith("PPIA") for k in names)
    summ = sheets[names["PPIA_1" if agri else "PPI 1"]]
    det = sheets[names["PPIA_2" if agri else "PPI 2"]]
    title = next(str(v) for v in summ.iloc[:3, 0] if isinstance(v, str) and "100" in v)
    base = re.search(r"\((.+?=\s*100)\)", title).group(1).strip()
    ver = _version(path)
    name = (f"Producer Price Index for Agriculture, {ver}" if agri
            else f"{ver} Producer Price Index")
    # The same index in three currency bases: each its own series (currency_basis).
    basis = "USD" if "USD" in name else "ZWG" if "ZWG" in name else "mixed" if "Weighted" in name else ""
    kw = dict(index_name=name, index_variant="agriculture" if agri else "output", base_period=base,
              currency_basis=basis)
    rows = []

    # detail: header row = the one holding "Weights"; months to its right
    hr = next(i for i in range(6) if any(str(v).strip() == "Weights" for v in det.iloc[i]))
    wcol = next(j for j, v in enumerate(det.iloc[hr]) if str(v).strip() == "Weights")
    mrow = hr if any(_period(v) for v in det.iloc[hr]) else hr + 1
    months = {j: _period(v) for j, v in enumerate(det.iloc[mrow]) if j > wcol and _period(v)}
    if len(months) < 3:
        raise ValueError(f"{path}: no month columns in the detail sheet")
    by = re.search(r"(?:19|20)\d\d", base).group(0)
    seen = {}
    for _, r in det.iloc[mrow + 1:].iterrows():
        if pd.isna(r[0]) or not str(r[0]).strip():
            continue
        ind = _label(r[0])
        vals = [None if pd.isna(r[j]) else round(float(r[j]), 6) for j in [wcol] + list(months)]
        if ind in seen:
            # A division and its only class share a label (and every value):
            # "Manufacture of tobacco products" twice. The repeat adds nothing.
            if seen[ind] == vals:
                continue
            # Same label, different weight and values (a group and a narrower
            # class: "Spinning, weaving and finishing of textiles" 0.73 / 0.36):
            # both are kept, the later one tagged by its printed order.
            k = 2
            while f"{ind} [repeat {k}]" in seen:
                k += 1
            ind = f"{ind} [repeat {k}]"
        seen[ind] = vals
        w = None if pd.isna(r[wcol]) else C.to_number(r[wcol])
        if w is not None:
            rows.append(C.row(**kw, industry=ind, period=by, frequency="annual", measure="weight",
                              value=w, unit="percent", series_code="weight (as printed beside the index)"))
        for j, per in months.items():
            v = None if pd.isna(r[j]) else C.to_number(r[j])
            if v is not None and v != 0:
                rows.append(C.row(**kw, industry=ind, period=per, frequency="monthly",
                                  measure="index", value=v))
    if "All items" not in seen:
        raise ValueError(f"{path}: no All items row in the detail sheet")

    # summary: All items annual averages and rates of change
    hdr = next(i for i in range(6) if any(_ALL.match(str(v).strip()) for v in summ.iloc[i]))
    cols = {j: str(v).strip().lower() for j, v in enumerate(summ.iloc[hdr]) if isinstance(v, str)}
    jall = next(j for j, v in cols.items() if _ALL.match(v))
    jmom = next((j for j, v in cols.items() if "month" in v), None)
    jyoy = next((j for j, v in cols.items() if "annual" in v), None)
    year, in_months = None, False
    for _, r in summ.iloc[hdr + 1:].iterrows():
        y, m = r[0], r[1]
        if "weight" in f"{y} {m}".lower():
            continue
        if isinstance(y, (int, float)) and not pd.isna(y) and 1990 < y < 2100:
            year = int(y)
        if pd.isna(m) or not str(m).strip():
            if year and not in_months and not pd.isna(r[jall]):     # annual-average block
                rows.append(C.row(**kw, industry="All items", period=str(year), frequency="annual",
                                  measure="index", value=float(r[jall]),
                                  series_code="annual average"))
            if year and pd.isna(r[jall]):
                in_months = True if rows and year else in_months
            continue
        in_months = True
        per = C.month_period(f"{str(m).strip()} {year}")
        if not per:
            continue
        for j, meas in ((jmom, "inflation_mom"), (jyoy, "inflation_yoy")):
            if j is None:
                continue
            v = None if pd.isna(r[j]) else C.to_number(r[j])
            if v is not None:
                rows.append(C.row(**kw, industry="All items", period=per, frequency="monthly",
                                  measure=meas, value=v))
    return rows
