"""Gambia — GBoS Gambia Labour Force Survey (GLFS) findings reports.

Three reports, four survey rounds, all read by `pdf_tables_labour`:

* GLFS 2026 (Q1) findings report -- PRIMARY. Table 4.1 (ISIC Rev.4 sections)
  and Table 4.2 (ISCO-08 major groups by sex), each printing BOTH GLFS 2025
  (Q1) and GLFS 2026 (Q1) side by side, so one report carries two rounds. The
  columns are dated from the table's own header, never by position.
* GLFS 2022-23 report (GBoS files it as "GLFS 2023 (Q1)"). Table 5.1 status in
  employment (ICSE-1993, the report's own label) by sex and residence; Table
  5.2 branch of economic activity; Table 5.3 occupation by sex, counts and
  percentages.
* GLFS 2018 report. Table 5.8 industry by sex, Table 5.9 by area (column
  percentages), Table 5.11 status in employment by sex (counts, TRANSPOSED --
  categories across the columns, the sex down the rows). WORKING-AGE BASE IS
  15-64 in 2018 ("Employed Population Age 15-64 Years"), 15+ from 2022-23.

SCHEMES ARE NAMED, so they are recorded: ISIC Rev.4 and ISCO-08 in every
report; ICSE-93 in 2022-23 (Table 5.1's header) and 2018 (section 5.4 cites
ICSE-1993 for the categories of Table 5.11).

WHAT IS LEFT:
* The 2025 and 2026 status (ICSE-18), institutional-sector and broad-sector
  FIGURES: images, with no values in the text layer.
* Table 5.2 (2022-23)'s informal / formal count columns -- industry crossed
  with formality, which one category column cannot hold -- and its last two
  rows: "Activities of extraterritorial organisations and bodies" and Total
  reach the text layer interleaved ("191 0. 0" / "*70 *121 563,395 100 .0" /
  "Total 447,487 115,908"), so which figure is whose cannot be read. The
  nineteen other branches are clean.
* 2018 Tables 5.4 / 5.5 (occupation by sex / area) are ROW percentages -- the
  sex split within an occupation -- which this indicator does not collect.
  Table 5.12 (status by area) puts the stratum label BELOW its numbers.
  Table 5.9's Total column repeats Table 5.8's and is taken once.
* Figure 5.2 (2022-23 sector of employment): chart labels "1.5 / 8.9 / 89.6"
  beside a legend "Household / Public / Private" whose order is not the
  values' order -- matching them would be a guess.

SMALL-SAMPLE MARKERS are GBoS's: "*" = fewer than 25 unweighted cases, "( )"
= 25-49. The figures are published and are collected; the markers are not
carried (the schema has no flag column), so a user should read 2022-23's
thin cells -- mining, utilities, real estate, armed forces -- with care.

CROSS-CHECK: 2026 Q1 wholesale and retail trade 25.6%, construction 13.8%,
agriculture 17.8%; service and sales workers 33.7% (female 52.1%). 2025 Q1
trade 30.6%. 2022-23: employees 34.6% (male 46.8, female 20.9); trade 147,887
(26.2%); total employed 563,395; managers 12,317. 2018: other service
activities 26.4%; employees 209,472 of 431,168.
"""
from __future__ import annotations

import os

import pandas as pd

from .pdf_tables_labour import make_parser

# Labels run long: rejoined, "Activities of households as employers;
# undifferentiated goods- and services-producing activities of households for
# own-use" is 120 characters, past the engine's default 80, and the row was
# silently skipped. "*" is GBoS's small-sample marker and starts a number.
_LONG_LABEL = {"label": r"^([A-Za-z][^\d]{2,160}?)\s+(?=[\d(-])"}
_STAR_LABEL = {"label": r"^([A-Za-z][^\d*]{2,160}?)\s+(?=[\d(*])",
               "label_ok": r"^[A-Z]"}

# WRAPPED LABELS, and why the layouts read WORD POSITIONS. GBoS wraps long
# categories both ways round -- the head above the numbers
# ("Skilled Agricultural, Forestry and Fishery" / "Workers" / figures) and the
# tail below them ("Human health and social work 2,471 ..." / "activities").
# The line rejoiner kept only "Workers" and "Assemblers" as occupations.
# `text_mode: words` assigns each fragment by geometry instead.

# --------------------------------------------------------------- 2026 (Q1)
_PERIOD_HDR = r"GLFS\s+20\d\d\s*\(Q[1-4]\)"
_PMAP = {"GLFS 2025 (Q1)": "2025 Q1", "GLFS 2026 (Q1)": "2026 Q1"}

LAYOUT_2026 = {
    "text_mode": "words",
    "survey": "Gambia Labour Force Survey (GLFS)",
    "frequency": "ad_hoc",
    "working_age_base": "15+",
    "period": "2026-Q1",
    "reference_period": "GLFS 2026 (Q1)",
    "tables": [
        {
            "caption": r"^Table 4\.1: Share of employment by branch",
            "topic": "industry", "classification": "ISIC Rev.4",
            "period_header": _PERIOD_HDR, "period_count": 2,
            "period_map": _PMAP,
            "columns": [
                {"measure": "share", "unit": "percent", "period_index": 0},
                {"measure": "share", "unit": "percent", "period_index": 1},
            ],
            "series_code": "GLFS T4.1",
            # 21 ISIC sections + Total.
            "row_scan": {**_LONG_LABEL, "expect_rows": 22},
        },
        {
            "caption": r"^Table 4\.2: Occupation \(ISCO",
            "topic": "occupation", "classification": "ISCO-08",
            "period_header": _PERIOD_HDR, "period_count": 2,
            "period_map": _PMAP,
            "columns": [
                {"sex": "male", "measure": "share", "unit": "percent", "period_index": 0},
                {"sex": "female", "measure": "share", "unit": "percent", "period_index": 0},
                {"sex": "total", "measure": "share", "unit": "percent", "period_index": 0},
                {"sex": "male", "measure": "share", "unit": "percent", "period_index": 1},
                {"sex": "female", "measure": "share", "unit": "percent", "period_index": 1},
                {"sex": "total", "measure": "share", "unit": "percent", "period_index": 1},
            ],
            "series_code": "GLFS T4.2",
            # 10 ISCO major groups + Total.
            "row_scan": {"expect_rows": 11},
        },
    ],
}

# ----------------------------------------------------------------- 2022-23
_T52_COLS = [{"skip": True}, {"skip": True},
             {"measure": "count", "unit": "persons"},
             {"measure": "share", "unit": "percent"}]

LAYOUT_2023 = {
    "text_mode": "words",
    "survey": "Gambia Labour Force Survey (GLFS) 2022-23",
    "frequency": "ad_hoc",
    "working_age_base": "15+",
    "period": "2023-Q1",
    "reference_period": "GLFS 2022-23",
    "tables": [
        {
            "caption": r"^Table 5\. ?1: Status in employment",
            "topic": "employment_status", "classification": "ICSE-93",
            "columns": [
                {"sex": "male", "measure": "share", "unit": "percent"},
                {"sex": "female", "measure": "share", "unit": "percent"},
                {"locality": "urban", "locality_label": "Urban",
                 "measure": "share", "unit": "percent"},
                {"locality": "rural", "locality_label": "Rural",
                 "measure": "share", "unit": "percent"},
                {"measure": "share", "unit": "percent"},
            ],
            "series_code": "GLFS22-23 T5.1",
            "row_scan": {"expect_rows": 6},
        },
        {
            # First page of Table 5.2: six branches.
            "caption": r"^Table 5\. ?2: Employed persons by branch",
            "topic": "industry", "classification": "ISIC Rev.4",
            "columns": _T52_COLS,
            "series_code": "GLFS22-23 T5.2",
            "row_scan": {**_STAR_LABEL, "expect_rows": 6},
        },
        {
            # Its continuation page carries no caption; it is the page whose
            # table ends in the small-sample note. Ends before Table 5.3's
            # prose. The last two rows are interleaved and fail the
            # four-number test (see the module note).
            "page_contains": ["Accommodation and food service",
                              "Figures in parentheses are based on 25-49"],
            "page_excludes": ["Table 5. 2: Employed persons by branch"],
            "end": r"^Note:",
            "topic": "industry", "classification": "ISIC Rev.4",
            "columns": _T52_COLS,
            "series_code": "GLFS22-23 T5.2",
            # The word "employers" completing this label is printed on the
            # next line, where geometry hands it to the interleaved row below.
            "label_map": {"Activities of households as":
                          "Activities of households as employers"},
            "row_scan": {**_STAR_LABEL, "expect_rows": 13},
        },
        {
            "caption": r"^Table 5\. ?3: Employed persons by occupation",
            "topic": "occupation", "classification": "ISCO-08",
            "columns": [
                {"sex": "male", "measure": "count", "unit": "persons"},
                {"sex": "male", "measure": "share", "unit": "percent"},
                {"sex": "female", "measure": "count", "unit": "persons"},
                {"sex": "female", "measure": "share", "unit": "percent"},
                {"sex": "total", "measure": "count", "unit": "persons"},
                {"sex": "total", "measure": "share", "unit": "percent"},
            ],
            "series_code": "GLFS22-23 T5.3",
            "row_scan": {**_STAR_LABEL, "expect_rows": 11},
        },
    ],
}

# -------------------------------------------------------------------- 2018
LAYOUT_2018 = {
    "text_mode": "words",
    "survey": "Gambia Labour Force Survey (GLFS) 2018",
    "frequency": "ad_hoc",
    "working_age_base": "15-64",
    "period": "2018",
    "reference_period": "GLFS 2018",
    "tables": [
        {
            "caption": r"^Table 5\.8: Employed Population Age 15-64 Years by Industry and Sex",
            "topic": "industry", "classification": "ISIC Rev.4",
            "columns": [
                {"sex": "male", "measure": "share", "unit": "percent"},
                {"sex": "female", "measure": "share", "unit": "percent"},
                {"measure": "share", "unit": "percent"},
            ],
            "series_code": "GLFS2018 T5.8",
            # 21 ISIC sections + Not stated; no Total row is printed.
            "row_scan": {**_LONG_LABEL, "expect_rows": 22},
        },
        {
            "caption": r"^Table 5\.9: Employed Population Age 15-64 Years by Industry and Area",
            "topic": "industry", "classification": "ISIC Rev.4",
            "columns": [
                {"locality": "urban", "locality_label": "Urban",
                 "measure": "share", "unit": "percent"},
                {"locality": "rural", "locality_label": "Rural",
                 "measure": "share", "unit": "percent"},
                {"skip": True},          # = Table 5.8's Total column
            ],
            "series_code": "GLFS2018 T5.9",
            "row_scan": {**_LONG_LABEL, "expect_rows": 22},
        },
        {
            "caption": r"^Table 5\.11: Employed Persons Age 15-64 Years by Status in Employment and Sex",
            "topic": "employment_status", "classification": "ICSE-93",
            "label_is_sex": True,
            "columns": [
                {"characteristic": "Employees", "measure": "count", "unit": "persons"},
                {"characteristic": "Employers", "measure": "count", "unit": "persons"},
                {"characteristic": "Own-account workers", "measure": "count", "unit": "persons"},
                {"characteristic": "Total", "measure": "count", "unit": "persons"},
            ],
            "series_code": "GLFS2018 T5.11",
            "row_scan": {"expect_rows": 3},
        },
    ],
}

_BY_NAME = {"2026": make_parser(LAYOUT_2026),
            "2022_23": make_parser(LAYOUT_2023),
            "2018": make_parser(LAYOUT_2018)}


def parse(local_path: str, extras: list[str] | None = None) -> pd.DataFrame:
    frames = []
    for path in [local_path] + list(extras or []):
        name = os.path.basename(path).lower()
        key = next((k for k in _BY_NAME if f"glfs_{k}" in name), None)
        if key is None:
            raise ValueError(f"{name}: not a GLFS report this parser knows "
                             f"(expected gambia_glfs_<2026|2022_23|2018>.pdf)")
        frames.append(_BY_NAME[key](path))
    return pd.concat(frames, ignore_index=True)
