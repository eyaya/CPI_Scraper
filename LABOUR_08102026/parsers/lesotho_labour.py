"""Lesotho — BOS Labour Force Survey 2024 and 2019.

BOS's site renders its publication list client-side from a JavaScript array in
publications.htm; every file is a ZIP holding one PDF under
/Bos_Reports/Copy%20of%20Demography/. Three documents are read, each through
`pdf_tables_labour` in word-position mode (labels wrap above and below their
numbers throughout):

* 2024 LFS REPORT -- Table 4.3 occupation by sex, 4.4 by settlement type;
  4.7 industry by sex, 4.8 by settlement type; 4.23 status in employment on
  ICSE-18-A by sex; and the "Total (N)" row of Table 4.14, which is the count
  of the employed in each ICSE-93 status.
* 2019 LFS REPORT -- Table 4.5 industry by sex and Table 4.7 occupation by sex,
  counts and percentages.
* 2019 LFS STATISTICAL TABLES -- Table 4.5 status in employment by sex and
  Table 10.8 formal / informal sector by sex, counts.

SCHEMES: both reports name ISCO-08 and ISIC Rev.4 beside their tables (2024
pp. 55, 58; 2019 "Occupation refers to ... (ISCO-08)", "ISIC Rev. 4"). The
2024 status tables are headed ICSE-93 and ICSE-18-A. The 2019 status table
names no scheme, so `National` there.

SETTLEMENT TYPE is Urban / Peri-Urban / Rural. Peri-urban is its own stratum,
filed as locality `other` with the label kept.

WHAT IS LEFT, AND WHY:
* "Sector" tables (2019 report 4.10, 2024 report 4.11): their totals are the
  EMPLOYEES (213 413 + 183 345 = 396 758 in 2019), not the employed -- shares
  of a different population under the same topic. Not collected.
* Table 4.14's percentage blocks are ROW percentages (the sex split within a
  status); only its count row is taken.
* The "Total (N)" rows of the occupation/industry tables are employment
  LEVELS by sex or settlement -- `unemployment`'s territory.
* The Total column of Tables 4.4 / 4.8 repeats Tables 4.3 / 4.7.
* The 2019 statistical tables' occupation/industry-by-status cross-tabs (4.13,
  4.14): their row totals wrap onto separate lines; the report's by-sex tables
  carry the same distributions cleanly.

PUBLISHED INCONSISTENCIES, KEPT: 2019 industry "Not Stated" total prints
2,043 while its sex cells (927 + 1,107) and the other tables give 2,034; the
statistical tables count 393,367 employees (Table 4.5) against 393,650 in the
occupation cross-tab. 2024 settlement totals for occupation and industry
differ from the by-sex tables by a tenth of a point (rounding).

CROSS-CHECK: 2024 elementary occupations 42.4% (female 47.3); households as
employers 16.2% (female 30.5); permanent employees 27.4%; employees 399,423
of 549,722. 2019 manufacturing female 44,988 (18.3%); elementary occupations
175,870; informal sector 413,922 of 521,445.
"""
from __future__ import annotations

import os
import zipfile

import pandas as pd

from .pdf_tables_labour import make_parser

_LONG = {"label": r"^([A-Za-z][^\d]{2,170}?)\s+(?=[\d(-])"}
_PCT = {"measure": "share", "unit": "percent"}
_N = {"measure": "count", "unit": "persons"}
_SETTLE = [
    {"locality": "urban", "locality_label": "Urban", **_PCT},
    {"locality": "other", "locality_label": "Peri-Urban", **_PCT},
    {"locality": "rural", "locality_label": "Rural", **_PCT},
    {"skip": True},                     # = the by-sex table's Total column
]
_BY_SEX_PCT = [{"sex": "male", **_PCT}, {"sex": "female", **_PCT},
               {"sex": "total", **_PCT}]
_TOTALS = {"label_map": {"Total (%)": "Total"}}

LAYOUT_2024 = {
    "survey": "Lesotho Labour Force Survey 2024",
    "frequency": "ad_hoc", "working_age_base": "15+",
    "period": "2024", "reference_period": "LFS 2024",
    "text_mode": "words",
    # TABLE 4.23'S GROUP HEADINGS ARE NOT LABEL FRAGMENTS. ICSE-18-A groups its
    # twelve categories under five headings printed on lines of their own;
    # geometry folded them into the category below, producing "Employers
    # Employers in corporations" and, worse, "Dependent contractors Dependent
    # contractors Employees" -- a heading attached to the WRONG group. A line
    # that is exactly a heading is a barrier.
    "barrier_pattern": r"^(?:Employers|Independent workers without employees|"
                       r"Dependent contractors|Employees|Contributing family workers)$",
    "tables": [
        {"caption": r"^Table 4\.3: Percentage Distribution of Employed Population \(15\+ Years\) by Occupation and Sex",
         "topic": "occupation", "classification": "ISCO-08",
         "columns": _BY_SEX_PCT, "series_code": "LFS2024 T4.3", **_TOTALS,
         "row_scan": {**_LONG, "expect_rows": 11, "exclude_labels": ["Total (N)"]}},
        {"caption": r"^Table 4\.4: Percentage Distribution of Employed Population \(15\+ Years\) by Occupation and",
         "topic": "occupation", "classification": "ISCO-08",
         "columns": _SETTLE, "series_code": "LFS2024 T4.4", **_TOTALS,
         "row_scan": {**_LONG, "expect_rows": 11, "exclude_labels": ["Total (N)"]}},
        {"caption": r"^Table 4\.7: Percentage Distribution of Employed Population \(15\+ Years\) by Industry and Sex",
         "topic": "industry", "classification": "ISIC Rev.4",
         "columns": _BY_SEX_PCT, "series_code": "LFS2024 T4.7", **_TOTALS,
         "row_scan": {**_LONG, "expect_rows": 22, "exclude_labels": ["Total (N)"]}},
        {"caption": r"^Table 4\.8: Percentage Distribution Employed Population \(15\+ Years\) by Industry and Settlement",
         "topic": "industry", "classification": "ISIC Rev.4",
         "columns": _SETTLE, "series_code": "LFS2024 T4.8", **_TOTALS,
         "row_scan": {**_LONG, "expect_rows": 22, "exclude_labels": ["Total (N)"]}},
        {"caption": r"^Table 4\.23: Percentage Distribution of Employed Population by Status in",
         "topic": "employment_status", "classification": "ICSE-18-A",
         "columns": _BY_SEX_PCT, "series_code": "LFS2024 T4.23", **_TOTALS,
         # 12 ICSE-18-A categories + Total; the five group headings carry no
         # numbers and are not rows.
         "row_scan": {**_LONG, "expect_rows": 13}},
        {"caption": r"^Table 4\.14: Percentage Distribution of Employed population \(15\+ years\) by",
         "topic": "employment_status", "classification": "ICSE-93",
         # ONLY the count row. It is printed three times (under each block)
         # with identical values; the first is taken.
         "columns": [{"characteristic": "Employee", **_N},
                     {"characteristic": "Employers", **_N},
                     {"characteristic": "Own-account workers", **_N},
                     {"characteristic": "Members of producers' cooperatives", **_N},
                     {"characteristic": "Contributing family workers", **_N},
                     {"characteristic": "Total", **_N}],
         "series_code": "LFS2024 T4.14 counts",
         "row_scan": {"label": r"^(Total \(N\))\s+", "label_ok": r"^Total",
                      "expect_rows": 1}},
    ],
}

_N_PCT_SEX_TOTAL = [{"sex": "male", **_N}, {"sex": "male", **_PCT},
                    {"sex": "female", **_N}, {"sex": "female", **_PCT},
                    {"sex": "total", **_N}]

LAYOUT_2019_REPORT = {
    "survey": "Lesotho Labour Force Survey 2019",
    "frequency": "ad_hoc", "working_age_base": "15+",
    "period": "2019", "reference_period": "LFS 2019",
    "text_mode": "words",
    "tables": [
        {"caption": r"^Table 4\.5: Number and Percentage Distribution of Employed Population \(15\+ Years\) by Industry",
         "topic": "industry", "classification": "ISIC Rev.4",
         "columns": _N_PCT_SEX_TOTAL, "series_code": "LFS2019 R4.5",
         # 21 ISIC sections + Not Stated + Total.
         "row_scan": {**_LONG, "expect_rows": 23}},
        {"caption": r"^Table 4\.7: Number and Percentage Distribution of Employed Population \(15\+ Years\) by Occupation",
         "topic": "occupation", "classification": "ISCO-08",
         "columns": _N_PCT_SEX_TOTAL, "series_code": "LFS2019 R4.7",
         "row_scan": {**_LONG, "expect_rows": 11}},
    ],
}

_BY_SEX_N = [{"sex": "male", **_N}, {"sex": "female", **_N},
             {"sex": "total", **_N}]

LAYOUT_2019_TABLES = {
    "survey": "Lesotho Labour Force Survey 2019",
    "frequency": "ad_hoc", "working_age_base": "15+",
    "period": "2019", "reference_period": "LFS 2019",
    "text_mode": "words",
    # Table 10.8 prints its stub heading on a line of its own, directly above
    # the first category.
    "barrier_pattern": r"^Formal/Informal sector$",
    "tables": [
        {"caption": r"^Table 4\.5: Distribution of Employed Population Aged 15\+ Years by Status in Employment and Sex",
         "topic": "employment_status", "classification": "National",
         "columns": _BY_SEX_N, "series_code": "LFS2019 T4.5",
         "row_scan": {"expect_rows": 7}},
        {"caption": r"^Table 10\.8: Distribution of Employed Population by Formal/Informal sector",
         "topic": "formality", "classification": "Not applicable",
         "columns": _BY_SEX_N, "series_code": "LFS2019 T10.8",
         "end": r"^Table 10\.9",
         "row_scan": {"expect_rows": 3}},
    ],
}

_BY_NAME = {"2024_labour_force_survey_report": make_parser(LAYOUT_2024),
            "2019_lesotho_lfs_report": make_parser(LAYOUT_2019_REPORT),
            "2019_lesotho_lfs_tables": make_parser(LAYOUT_2019_TABLES)}


def _pdf(path: str) -> str:
    """BOS ships every report as a ZIP holding one PDF; extract it beside the
    archive (both are retained) and return the PDF's path."""
    if not path.lower().endswith(".zip"):
        return path
    with zipfile.ZipFile(path) as z:
        pdfs = [m for m in z.namelist() if m.lower().endswith(".pdf")]
        if len(pdfs) != 1:
            raise ValueError(f"{path}: expected one PDF, found {pdfs}")
        z.extract(pdfs[0], os.path.dirname(path))
        return os.path.join(os.path.dirname(path), pdfs[0])


def parse(local_path: str, extras: list[str] | None = None) -> pd.DataFrame:
    frames = []
    for path in [local_path] + list(extras or []):
        pdf = _pdf(path)
        stem = os.path.splitext(os.path.basename(pdf))[0].lower()
        if stem not in _BY_NAME:
            raise ValueError(f"{stem}: not a Lesotho LFS document this parser knows")
        frames.append(_BY_NAME[stem](pdf))
    return pd.concat(frames, ignore_index=True)
