"""ZimStat — Zimbabwe 2022 census population projections by age & sex (Tier-3 PDF).

Parser for the "2022 Population Projection Report" appendix (Table 3.4), which
tabulates the national population by single year of age and sex for each projection
year 2022-2042. The layout has quirks:

* most years come in pairs, two blocks side by side, and each pair spans two pages;
* the year-header line ("2030 2031") may sit under a table-caption line;
* the final year (2042) stands alone as a single block (four numbers per row).

We emit one tidy row per (age, sex, year) as a projected population. National
(series_type = projection); Both = total.
"""
from __future__ import annotations
import re
import pdfplumber
import pandas as pd

_YEARS2_RE = re.compile(r"^\s*((?:19|20)\d{2})\s+((?:19|20)\d{2})\s*$")
_YEARS1_RE = re.compile(r"^\s*((?:19|20)\d{2})\s*$")
_HDR_RE = re.compile(r"Age\s+Male\s+Female\s+Total", re.I)
_ROW2_RE = re.compile(
    r"^\s*(\d{1,3}\+?)\s+([\d,]+)\s+([\d,]+)\s+([\d,]+)\s+"
    r"(\d{1,3}\+?)\s+([\d,]+)\s+([\d,]+)\s+([\d,]+)\s*$")
_ROW1_RE = re.compile(
    r"^\s*(\d{1,3}\+?)\s+([\d,]+)\s+([\d,]+)\s+([\d,]+)\s*$")


def _emit(out, age, year, m, f, t):
    for sex, v in (("male", m), ("female", f), ("total", t)):
        out.append({
            "series_type": "projection", "sex": sex, "age_group": age.strip(),
            "geography": "Total country", "period": year, "frequency": "annual",
            "measure": "count", "value": float(v.replace(",", "")),
            "unit": "persons", "series_code": "ZW_PROJ_2022",
        })


def parse(local_path: str) -> pd.DataFrame:
    out = []
    with pdfplumber.open(local_path) as pdf:
        for page in pdf.pages:
            lines = [ln for ln in (page.extract_text() or "").splitlines() if ln.strip()]
            if not any(_HDR_RE.search(ln) for ln in lines[:4]):
                continue
            # the year-header sits in the first few lines (possibly under a caption)
            y1 = y2 = None
            for ln in lines[:3]:
                m2 = _YEARS2_RE.match(ln)
                m1 = _YEARS1_RE.match(ln)
                if m2:
                    y1, y2 = m2.group(1), m2.group(2)
                    break
                if m1:
                    y1 = m1.group(1)
                    break
            if y1 is None:
                continue
            for ln in lines:
                if y2 is not None:
                    rm = _ROW2_RE.match(ln)
                    if rm:
                        _emit(out, rm.group(1), y1, rm.group(2), rm.group(3), rm.group(4))
                        _emit(out, rm.group(5), y2, rm.group(6), rm.group(7), rm.group(8))
                else:
                    rm = _ROW1_RE.match(ln)
                    if rm:
                        _emit(out, rm.group(1), y1, rm.group(2), rm.group(3), rm.group(4))
    df = pd.DataFrame(out)
    if df.empty:
        raise ValueError("zimstat_population: no projection rows parsed")
    return df.drop_duplicates(["age_group", "sex", "period"])
