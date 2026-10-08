"""Liberia — LISGIS Labour Force Survey 2016-17 (LBR-LFS), main report.

REACHED THROUGH LISGIS'S NEW SITE. lisgis.gov.lr was rebuilt as a single-page
application over a JSON API; the old placeholder that blocked `unemployment`
is gone. `/api/survey-report-grid` lists every survey report with a direct
`downloadUrl`, and the LFS 2016/2017 main report sits at
/uploads/surveys/lfs-2016-2017.pdf.

The report follows the ILO LFS template (the same chapter 5 as Gambia's
2022-23 report), and five of its tables are read by `pdf_tables_labour` in
word-position mode (labels wrap above and below their numbers):

* Table 5.1  status in employment (ICSE-1993, printed in the header) by sex,
             counts and percentages;
* Table 5.2  branch of economic activity, "ISIC Rev 4" sections with their
             letters as printed ("A - Agriculture, forestry and fishing");
* Table 5.3  occupation (ISCO-08) by sex, percentages;
* Table 5.4  employed by type of production unit -- formal sector / informal
             sector / household, counts and percent -> `formality`. READ
             SEPARATELY: see `_table_5_4` for why geometry cannot read it;
* Table 5.5  persons with informal / formal jobs by sex and residence, counts
             and percentages -> `formality`.

A DATA-QUALITY FLAG THE REPORT RAISES ITSELF: "Not elsewhere classified" is
43.5% of employment by industry and 24.1% by occupation ("unusually high and
raises concerns about the quality of the data collected"). Those shares are
published and are collected; anyone comparing Liberia's sector structure with
another country's needs to know that almost half of employment has no branch.

WHAT IS LEFT: section U prints "N/A" (no value); Table 5.2 prints no Total
row. Figure 5.2 (public / private 28.8 / 71.2) is a pie whose labels are not
reliably tied to its values in the text layer. Tables 5.6 onward are hours and
underemployment.

PERIOD 2017, reference "2016-2017" -- as the `unemployment` layout for this
same report dates it.

CROSS-CHECK: employed 538,902 (male 317,698 / female 221,204); employees
161,633 (30.0%); agriculture 25.3%; skilled agricultural workers 28.5%;
informal jobs 467,318 (86.7%); informal-sector production units 231,092.
"""
from __future__ import annotations

import re

import pandas as pd
import pdfplumber

from . import _common as C
from .pdf_tables_labour import make_parser

_N = {"measure": "count", "unit": "persons"}
_P = {"measure": "share", "unit": "percent"}
_LONG = {"label": r"^([A-Za-z][^\d]{2,170}?)\s+(?=[\d(-])"}

LAYOUT = {
    "survey": "Liberia Labour Force Survey (LBR-LFS) 2016-17",
    "frequency": "ad_hoc", "working_age_base": "15+",
    "period": "2017", "reference_period": "2016-2017",
    "text_mode": "words",
    "tables": [
        {"caption": r"^Table 5\.1: Status in employment at main job",
         "topic": "employment_status", "classification": "ICSE-93",
         "columns": [{"sex": "male", **_N}, {"sex": "female", **_N},
                     {"sex": "total", **_N}, {"sex": "male", **_P},
                     {"sex": "female", **_P}, {"sex": "total", **_P}],
         "series_code": "LBR-LFS T5.1",
         "row_scan": {**_LONG, "expect_rows": 6}},
        {"caption": r"^Table 5\.2: Employed persons by branch of economic activity",
         "topic": "industry", "classification": "ISIC Rev.4",
         "columns": [_P], "series_code": "LBR-LFS T5.2",
         # Section T wraps, and its tail line ("s ervices-producing ... own
         # use") is handed to no row by geometry; the full label is printed
         # across the two lines and is restored here, with the text layer's
         # stray space in "s ervices" closed up.
         "label_map": {
             "T - Activities of households as employers; undifferentiated goods- and":
             "T - Activities of households as employers; undifferentiated "
             "goods- and services-producing activities of households for own use"},
         # 21 lettered sections + X; U prints N/A and is skipped. The column
         # header "(ISIC Rev 4)" otherwise scans as a category worth 4.
         "row_scan": {**_LONG, "expect_rows": 21,
                      "exclude_labels": ["Branch of economic activity"]}},
        {"caption": r"^Table 5\.3: Percentage distribution of employed persons by occupation",
         "topic": "occupation", "classification": "ISCO-08",
         "columns": [{"sex": "male", **_P}, {"sex": "female", **_P},
                     {"sex": "total", **_P}],
         "series_code": "LBR-LFS T5.3",
         "row_scan": {**_LONG, "expect_rows": 12}},
        {"caption": r"^Table 5\.5: Persons in formal/informal employment",
         "topic": "formality", "classification": "Not applicable",
         "columns": [{"sex": "male", **_N}, {"sex": "female", **_N},
                     {"locality": "urban", "locality_label": "Urban", **_N},
                     {"locality": "rural", "locality_label": "Rural", **_N},
                     _N,
                     {"sex": "male", **_P}, {"sex": "female", **_P},
                     {"locality": "urban", "locality_label": "Urban", **_P},
                     {"locality": "rural", "locality_label": "Rural", **_P},
                     _P],
         "series_code": "LBR-LFS T5.5",
         "row_scan": {"expect_rows": 3}},
    ],
}

_engine = make_parser(LAYOUT)

# TABLE 5.4 PRINTS EACH LABEL *BELOW* ITS NUMBERS, and word geometry shifts
# every label down one row -- it paired "Informal sector" with the HOUSEHOLD
# figures (125,666 / 23.3). Well-formed and wrong. The plain text layer keeps
# the true order (numbers line, then its label), so this one table is read
# from it directly, and must add up: the three units sum to the Total.
# The caption also opens a line in the list of tables, followed by dot leaders.
_T54 = re.compile(r"^Table 5\.4: Distribution of classification of production units"
                  r"(?![^\n]*\.{4})", re.M)


def _table_5_4(path: str) -> list[dict]:
    with pdfplumber.open(path) as pdf:
        text = next(t for t in (p.extract_text() or "" for p in pdf.pages)
                    if _T54.search(t))
    lines = text[_T54.search(text).start():].splitlines()
    pairs, pending = [], None
    for ln in lines[1:]:
        s = ln.strip()
        m = re.fullmatch(r"([\d,]+)\s+([\d.]+)", s)
        if m:
            pending = (float(m.group(1).replace(",", "")), float(m.group(2)))
        elif pending and re.fullmatch(r"[A-Z][a-z]+(?: [a-z]+)*", s):
            pairs.append((s, *pending))
            pending = None
            if s == "Total":
                break
    labels = [p[0] for p in pairs]
    if labels != ["Formal sector", "Informal sector", "Household", "Total"]:
        raise ValueError(f"LBR-LFS T5.4: read {labels}")
    if sum(p[1] for p in pairs[:3]) != pairs[3][1]:
        raise ValueError("LBR-LFS T5.4: units do not sum to the Total")
    out = []
    # The Total row (538,902 / 100.0) is the same employed total Table 5.5
    # prints under the same topic; emitting both would duplicate a merge key.
    for lab, n, pct in pairs[:3]:
        for val, meas, unit in ((n, "count", "persons"), (pct, "share", "percent")):
            out.append(C.row(topic="formality", characteristic=lab,
                             classification="Not applicable", value=val,
                             survey=LAYOUT["survey"], period=LAYOUT["period"],
                             reference_period=LAYOUT["reference_period"],
                             frequency=LAYOUT["frequency"], measure=meas,
                             unit=unit, working_age_base="15+",
                             series_code="LBR-LFS T5.4"))
    return out


def parse(path: str) -> pd.DataFrame:
    return pd.concat([_engine(path), pd.DataFrame(_table_5_4(path))],
                     ignore_index=True)
