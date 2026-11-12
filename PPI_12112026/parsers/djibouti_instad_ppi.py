"""Djibouti -- INSTAD "Bulletin de l'Indice des Prix à la Production Industrielle (IPPI)".

Quarterly, base year 2022 ("L'IPPI a pour année de base 2022"), NAEMA rev1
branches, published on instad.dj (category "IPPI" of its Express backend;
the file sits in INSTAD's Firebase Storage bucket, as for the CPI).
Tableau 1 "Indice des prix de production de l'industrie par branche
d'activités": one row per branch, the index for every quarter since T1-22,
then three % changes headed "T4-24/T3-24" (q/q), "T4-24/T4-23" (y/y) and
"2024/2023" (change of the annual average). The header names the columns,
so each is read from its own header; a label wrapped over two lines
("Travaux d'impression et de reproduction" / numbers / "d'enregistrements")
is rejoined.
"""
from __future__ import annotations

import re

import pandas as pd
import pdfplumber

from . import _common as C

INDEX_NAME = "Indice des Prix à la Production Industrielle (IPPI)"
_Q = re.compile(r"^T([1-4])-(\d{2})$")
_NUM = r"-?\d+,\d+"
_ROW = re.compile(r"^(.*?)\s*((?:" + _NUM + r"\s+)*" + _NUM + r")\s*$")


def parse(path: str) -> pd.DataFrame:
    with pdfplumber.open(path) as pdf:
        lines = [ln for pg in pdf.pages for ln in (pg.extract_text() or "").split("\n")]
    text = "\n".join(lines)
    if not re.search(r"ann[ée]e de base 2022", text):
        raise ValueError(f"{path}: base year 2022 not stated")
    hdr = next(i for i, ln in enumerate(lines) if ln.strip().startswith("Libellé") and "T1-" in ln)
    toks = lines[hdr].split()[1:]
    quarters = [t for t in toks if _Q.match(t)]
    periods = [f"20{_Q.match(t).group(2)}-Q{_Q.match(t).group(1)}" for t in quarters]
    n = len(periods)
    # "T4-24/ T4-24/ 2024/" over "T3-24 T4-23 2023": q/q, y/y, annual average.
    last = periods[-1]
    out, pending = [], []
    for ln in lines[hdr + 2:]:
        s = ln.strip()
        if s.startswith("Source"):
            break
        m = _ROW.match(s)
        nums = m.group(2).split() if m and m.group(2) else []
        if len(nums) == n + 3:
            label = " ".join(pending + [m.group(1)]).strip()
            pending = []
            vals = [C.to_number(v, decimal=",") for v in nums]
            out.append([label, vals])
        elif out and not nums and s[:1].islower() or (out and not nums and s.startswith(("d'", "d’"))):
            out[-1][0] = f"{out[-1][0]} {s}"
        elif not nums:
            pending.append(s)
    rows = []
    for label, vals in out:
        label = re.sub(r"\s+", " ", label)
        for p, v in zip(periods, vals[:n]):
            rows.append(C.row(index_name=INDEX_NAME, industry=label, period=p, frequency="quarterly",
                              measure="index", value=v, base_period="2022=100"))
        for meas, v in zip(("inflation_qoq", "inflation_yoy"), vals[n:n + 2]):
            rows.append(C.row(index_name=INDEX_NAME, industry=label, period=last, frequency="quarterly",
                              measure=meas, value=v))
        rows.append(C.row(index_name=INDEX_NAME, industry=label, period=last[:4], frequency="annual",
                          measure="inflation_avg", value=vals[n + 2]))
    if len(out) < 10:
        raise ValueError(f"{path}: only {len(out)} rows")
    return pd.DataFrame(rows)


# A % change carries the base of its index (set from this output; see _base_carry).
from ._base_carry import carry_base  # noqa: E402
parse = carry_base(parse)
