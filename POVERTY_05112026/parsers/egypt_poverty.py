"""Egypt -- monetary poverty (CAPMAS), from CAPMAS's own statistical products.

CAPMAS publishes no stand-alone poverty table in its HIECS volumes (the
2019/20 "poverty indicators" attachment is page images; the 2010/11 volume
prints its poverty figures as charts whose values are not in the text layer),
but two of its CATALOGUE products tabulate the national-line poverty rate:

1. "National Statistical Report on Monitoring the 2030 SDG Indicators in
   Egypt" (CAPMAS publication 147, 2023 edition), indicator 1.2.1:
   Tableau 2 -- P0 for 2015, 2017/18 and 2019/20; Tableau 3 -- by sex of the
   person; Tableau 4 -- by six age groups. Source line under each table:
   CAPMAS, HIECS 2019/2020. The Arabic text layer is in visual (reversed)
   order but the NUMBERS keep the header's column order (2019/20 | 2017/18 |
   2015), confirmed by the 2019 edition (32,5 / 27,8) and by the report's own
   indicator summary (29,7% in 2019/20). Tableau 1 ($2.15 PPP) is sourced to
   the World Bank database and is NOT collected (aggregator).
2. "Egypt in Figures" (publication 167), the bilingual "Poverty Rate in
   Egypt's Regions" table: 2015 (2019 edition), 2017/18 (2020 edition),
   2019/20 (2024 edition) -- urban governorates, urban / rural Lower Egypt,
   urban / rural Upper Egypt, total. Its trend chart (1999/2000-2019/20) is
   NOT read: the chart's value labels reach the text layer sorted by height,
   so which value belongs to which year cannot be read from it.

Line: CAPMAS national (upper) poverty line = food + non-food components.
Periods are the survey's first year (2017/18 -> 2017, 2019/20 -> 2019).
"""
from __future__ import annotations

import os
import re

import pandas as pd

from . import _common as C

_BASE = dict(welfare_aggregate="consumption", unit_of_analysis="person", frequency="ad_hoc",
             line_type="national", line_level="overall",
             line_name="Seuil national de pauvreté (CAPMAS, HIECS)")
LAYOUT = {"survey": "HIECS", **_BASE, "period_patterns": [r"(20\d\d)"], "tables": []}
LAYOUT_EIF = dict(LAYOUT)

_ROUND = {"2015": ("HIECS 2015", "2015", "2015"), "2017/2018": ("HIECS 2017/18", "2017", "2017/18"),
          "2019/2020": ("HIECS 2019/20", "2019", "2019/20")}


def _row(rnd, value, **a):
    survey, period, ref = _ROUND[rnd]
    return C.row(metric="headcount", value=value, unit="percent", survey=survey, period=period,
                 reference_period=ref, **{**_BASE, **a})


def parse(path: str, extras: list[str] | None = None) -> pd.DataFrame:
    """SDG report 2023 (primary); Egypt in Figures editions as extras."""
    import pdfplumber
    with pdfplumber.open(path) as pdf:
        t20 = pdf.pages[19].extract_text() or ""
        t21 = pdf.pages[20].extract_text() or ""
    cols = ["2019/2020", "2017/2018", "2015"]        # left-to-right in the text layer
    out = []
    m = re.search(r"^(\d+\.\d)\s+(\d+\.\d)\s+(\d+\.\d)\s+ي ?نطولا رقفلا طخ نود", t20, re.M)
    if not m:
        raise ValueError(f"{path}: Tableau 2 (national P0) not found on p. 20")
    nat = [float(x) for x in m.groups()]
    for c, v in zip(cols, nat):
        out.append(_row(c, v))
    for lab, sex, word in (("Hommes (ذكور)", "male", "روكذ"), ("Femmes (إناث)", "female", "ثانإ")):
        m = re.search(rf"^(\d+\.\d)\s+(\d+\.\d)\s+(\d+\.\d)\s+{word}$", t20, re.M)
        if not m:
            raise ValueError(f"{path}: Tableau 3 row {lab} not found")
        for c, v in zip(cols, m.groups()):
            out.append(_row(c, float(v), topic="sex", characteristic=lab, sex=sex))
    ages = [("19 - 0", "0-19"), ("29 – 20", "20-29"), ("39 – 30", "30-39"), ("49 – 40", "40-49"),
            ("59 – 50", "50-59"), ("+ 60", "60+")]
    for printed, band in ages:
        m = re.search(rf"^(\d+\.\d+)\s+(\d+\.\d)\s+(\d+\.\d)\s+{re.escape(printed)}$", t21, re.M)
        if not m:
            raise ValueError(f"{path}: Tableau 4 row {band} not found")
        for c, v in zip(cols, m.groups()):
            out.append(_row(c, float(v), topic="age", characteristic=band, age_group=band))
    if nat != [29.7, 32.5, 27.8]:
        raise ValueError(f"{path}: national P0 {nat} -- column order changed?")
    for ex in extras or []:
        out += _eif(ex)
    return pd.DataFrame(out)


_REG = {"Urban governorates": dict(geography="Urban governorates"),
        "Lower Urban": dict(geography="Lower Egypt", topic="locality", characteristic="Lower Urban",
                            locality="urban", locality_label="Lower Urban"),
        "Lower Rural": dict(geography="Lower Egypt", topic="locality", characteristic="Lower Rural",
                            locality="rural", locality_label="Lower Rural"),
        "Upper Urban": dict(geography="Upper Egypt", topic="locality", characteristic="Upper Urban",
                            locality="urban", locality_label="Upper Urban"),
        "Upper Rural": dict(geography="Upper Egypt", topic="locality", characteristic="Upper Rural",
                            locality="rural", locality_label="Upper Rural")}


def _eif(path: str) -> list[dict]:
    """'Poverty Rate in Egypt's Regions <round>' from one Egypt in Figures edition."""
    import pdfplumber
    with pdfplumber.open(path) as pdf:
        page = next(((p.extract_text() or "") for p in pdf.pages
                     if "Poverty Rate in Egypt's Regions" in (p.extract_text() or "")), None)
    if page is None:
        raise ValueError(f"{path}: no 'Poverty Rate in Egypt's Regions' table")
    rnd = re.search(r"Poverty Rate in Egypt's Regions (?:in )?(2015|2017/2018|2019/2020)", page).group(1)
    out = []
    for lab, a in _REG.items():
        m = re.search(rf"^{lab}\s+(\d+(?:\.\d+)?)\s", page, re.M)
        if not m:
            raise ValueError(f"{path}: row {lab} missing")
        out.append(_row(rnd, float(m.group(1)), **a))
    # the table's Total must equal the SDG report's national rate for the round
    tot = float(re.search(r"^Total\s+(\d+(?:\.\d+)?)\s", page, re.M).group(1))
    if tot != {"2015": 27.8, "2017/2018": 32.5, "2019/2020": 29.7}[rnd]:
        raise ValueError(f"{path}: Total {tot} disagrees with the national rate for {rnd}")
    return out
