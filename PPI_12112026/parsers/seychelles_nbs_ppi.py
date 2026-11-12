"""Seychelles -- NBS Producer Price Index for Manufacturing (PPIM).

The PPIM was first published in February 2015 (quarterly bulletin, then
monthly), with January 2013 as the index reference period (2013 = 100); it has
not been rebased. It covers 13-14 ISIC Rev.4 four-digit classes of manufacturing
plus electricity and water supply.

parse_timeseries  "Timeseries PPI-IPI" workbook (sheet PPI): rows = ISIC classes +
    TOTAL, columns = months January 2013 onward (header cells are dates displayed
    "mmm-yy"); below TOTAL, "M on M change" and "Y on Y change" rows stored as
    fractions with a percent display format (0.0% / 0.00%) -- read as the
    percentage displayed (-0.0215 shown "-2.2%" -> -2.2). The "SEASONALLY
    ADJUSTED SERIES" TOTAL is not collected (the schema has no adjustment flag;
    it would share the unadjusted total's ID). The IPI sheet is a volume index,
    not a price index, and is not collected.
parse_bulletin    the monthly bulletin PDF: Table 1 (total: monthly index, m/m %,
    y/y %, and at each quarter's last month the quarterly index and q/q %) and
    Table 2 (index by ISIC class, last 13 months).

Values are rounded to the displayed decimals (index "0.0").

CROSS-CHECK (verbatim, August 2026 bulletin): total August 2026 100.7, July 96.2,
m/m 4.8%, y/y -7.5%; Q2 2026 quarterly index 98.6, q/q -2.4%; fish processing
August 2026 98.1.
"""
from __future__ import annotations

import datetime as dt
import re

import pandas as pd

from . import _common as C

NAME = "Producer Price Index for Manufacturing (PPIM)"
BASE = "2013=100"


def _dec(fmt: str):
    f = (fmt or "").split(";")[0]
    m = re.search(r"0\.(0+)", f)
    return len(m.group(1)) if m else (0 if "0" in f else None)


def parse_timeseries(path: str) -> pd.DataFrame:
    import openpyxl
    wb = openpyxl.load_workbook(path, data_only=True)
    ws = wb["PPI"]
    rows_x = list(ws.iter_rows())
    hi = next(i for i, r in enumerate(rows_x) if any(isinstance(c.value, dt.datetime) for c in r))
    months = {j: f"{c.value.year}-{c.value.month:02d}" for j, c in enumerate(rows_x[hi])
              if isinstance(c.value, dt.datetime)}
    seq = list(months.values())
    if len(set(seq)) != len(seq):
        raise ValueError("repeated month in the header")
    out, total_seen = [], False
    for r in rows_x[hi + 1:]:
        label = str(r[0].value or "").strip()
        if not label:
            continue
        if label.upper().startswith("SEASONALLY ADJUSTED"):
            break
        meas = {"m on m change": "inflation_mom", "y on y change": "inflation_yoy"}.get(label.lower())
        if meas is None and total_seen:
            continue
        for j, per in months.items():
            c = r[j] if j < len(r) else None
            if c is None or not isinstance(c.value, (int, float)):
                continue
            n = _dec(c.number_format)
            if meas:
                if "%" not in c.number_format:
                    raise ValueError(f"{label}: change cell without a percent format ({c.number_format})")
                v = round(c.value * 100, n if n is not None else 2)
                out.append(C.row(index_name=NAME, industry="TOTAL", period=per, frequency="monthly",
                                 measure=meas, value=v))
            else:
                v = round(float(c.value), n if n is not None else 1)
                out.append(C.row(index_name=NAME, industry=label, period=per, frequency="monthly",
                                 measure="index", value=v, base_period=BASE))
        if label.upper() == "TOTAL":
            total_seen = True
    wb.close()
    if len(out) < 2000:
        raise ValueError(f"only {len(out)} rows from {path}")
    return pd.DataFrame(out)


_MON = {m: i for i, m in enumerate(["jan", "feb", "mar", "apr", "may", "jun", "jul", "aug",
                                     "sep", "oct", "nov", "dec"], 1)}
_NUM = r"-?\d+(?:\.\d+)?"


def parse_bulletin(path: str) -> pd.DataFrame:
    import pdfplumber
    with pdfplumber.open(path) as pdf:
        text = "\n".join(pg.extract_text() or "" for pg in pdf.pages)
    out = []
    # Table 1 -- the total.
    t1 = text[text.index("Table 1: Producer Price Index"):text.index("Notes:")]
    year = None
    for line in t1.splitlines():
        line = line.strip()
        if re.fullmatch(r"(19|20)\d{2}", line):
            year = int(line)
            continue
        m = re.fullmatch(rf"([A-Z][a-z]{{2}})\s+({_NUM})\s+({_NUM})%\s+({_NUM})%(?:\s+({_NUM})\s+({_NUM})%)?", line)
        if not (m and year and m.group(1).lower() in _MON):
            continue
        mo = _MON[m.group(1).lower()]
        per = f"{year}-{mo:02d}"
        out += [C.row(index_name=NAME, industry="TOTAL", period=per, frequency="monthly",
                      measure="index", value=float(m.group(2)), base_period=BASE),
                C.row(index_name=NAME, industry="TOTAL", period=per, frequency="monthly",
                      measure="inflation_mom", value=float(m.group(3))),
                C.row(index_name=NAME, industry="TOTAL", period=per, frequency="monthly",
                      measure="inflation_yoy", value=float(m.group(4)))]
        if m.group(5):
            if mo % 3:
                raise ValueError(f"quarterly figures on a non-quarter-end month: {line}")
            q = f"{year}-Q{mo // 3}"
            out += [C.row(index_name=NAME, industry="TOTAL", period=q, frequency="quarterly",
                          measure="index", value=float(m.group(5)), base_period=BASE),
                    C.row(index_name=NAME, industry="TOTAL", period=q, frequency="quarterly",
                          measure="inflation_qoq", value=float(m.group(6)))]
    # Table 2 -- by ISIC class, last 13 months.
    t2 = text[text.index("Table 2: Producer Price Index by Manufacturing Sector"):]
    hdr = re.search(r"((?:[A-Z][a-z]{2}-\d{2}\s*){13})", t2)
    months = [C.month_period(x) for x in hdr.group(1).split()]
    n2 = 0
    for line in t2[hdr.end():].splitlines():
        m = re.fullmatch(rf"(.*?[A-Z.)]) ((?:{_NUM} ){{12}}{_NUM})", line.strip())
        if not m:
            if line.startswith("Source"):
                break
            continue
        vals = [float(x) for x in m.group(2).split()]
        for per, v in zip(months, vals):
            out.append(C.row(index_name=NAME, industry=m.group(1).strip(), period=per,
                             frequency="monthly", measure="index", value=v, base_period=BASE))
        n2 += 1
    if n2 < 10:
        raise ValueError(f"Table 2: only {n2} rows")
    # Table 1 and Table 2 both print the TOTAL index; keep one, they must agree.
    seen, res = {}, []
    for r in out:
        k = (r["industry"], r["period"], r["frequency"], r["measure"])
        if k in seen:
            if seen[k] != r["value"]:
                raise ValueError(f"Table 1 and Table 2 disagree on {k}: {seen[k]} vs {r['value']}")
            continue
        seen[k] = r["value"]
        res.append(r)
    return pd.DataFrame(res)


# A % change carries the base of its index (set from this output; see _base_carry).
from ._base_carry import carry_base  # noqa: E402
parse_bulletin = carry_base(parse_bulletin)
parse_timeseries = carry_base(parse_timeseries)
