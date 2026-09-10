"""NBS Seychelles — mid-year Estimated Resident Population by age & sex (Tier-3 PDF).

Parser for the "Revised Mid-<year> Estimated Resident Population (ERP)" report,
Table 3a ("MID <year> ALL ESTIMATED RESIDENT POPULATION"). The table lists
single-year ages 0-94 and 95+ with Males/Females/Total, laid out in three
side-by-side column-blocks (ages 0-34 | 35-69 | 70-95+), interleaved with 5-year
subtotal rows (skipped here) and a final TOTAL row. We emit the single-year ages
and the national total (series_type = estimate).
"""
from __future__ import annotations
import re
import pdfplumber
import pandas as pd

_AGE_RE = re.compile(r"^(?:\d{1,2}|95\+)$")       # single-year age or 95+ (skip ranges)
_NUM_RE = re.compile(r"^\d[\d,]*$")


def _num(tok):
    return int(tok.replace(",", ""))


def parse(local_path: str) -> pd.DataFrame:
    lines = None
    year = "2026"
    with pdfplumber.open(local_path) as pdf:
        for p in pdf.pages:
            txt = p.extract_text() or ""
            up = txt.upper()
            if "ALL ESTIMATED RESIDENT POPULATION" in up and "TABLE 3A" in up:
                lines = txt.splitlines()
                m = re.search(r"MID[- ](\d{4})", up)
                if m:
                    year = m.group(1)
                break
    if lines is None:
        raise ValueError("nbs_seychelles_population: Table 3a not found")

    cells, national = {}, None
    for ln in lines:
        toks = ln.split()
        # national total row
        mt = re.search(r"TOTAL\s+([\d,]+)\s+([\d,]+)", ln, re.I)
        if mt:
            national = (_num(mt.group(1)), _num(mt.group(2)))
        i = 0
        while i < len(toks) - 3:
            if _AGE_RE.match(toks[i]) and all(_NUM_RE.match(toks[i + j]) for j in (1, 2, 3)):
                age = toks[i]
                cells[age] = (_num(toks[i + 1]), _num(toks[i + 2]), _num(toks[i + 3]))
                i += 4
            else:
                i += 1

    if not cells:
        raise ValueError("nbs_seychelles_population: no age rows parsed")

    # verify single-year ages reconcile to the national total
    sm = sum(v[0] for v in cells.values())
    sf = sum(v[1] for v in cells.values())
    if national and (abs(sm - national[0]) > 20 or abs(sf - national[1]) > 20):
        raise ValueError(
            f"nbs_seychelles_population: age sum (M{sm}/F{sf}) != TOTAL {national}")

    out = []

    def emit(age, male, female, total):
        for sex, v in (("male", male), ("female", female), ("total", total)):
            out.append({
                "series_type": "estimate", "sex": sex, "age_group": age,
                "geography": "Total country", "period": year, "frequency": "annual",
                "measure": "count", "value": float(v), "unit": "persons",
                "series_code": "SC_ERP_ALLRES_T3A",
            })

    for age, (m, f, t) in cells.items():
        if abs(m + f - t) <= 2:
            emit(age, m, f, t)
    if national:
        emit("Total", national[0], national[1], national[0] + national[1])

    return pd.DataFrame(out)
