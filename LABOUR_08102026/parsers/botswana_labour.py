"""Botswana — Statistics Botswana QMTS Labour Force Module, employment composition.

One module per country, read by `pdf_tables_labour.make_parser`. The report is
the one `unemployment` collects; this layout opens only the composition tables.

NOTHING IS CLASSIFIED UNDER AN INTERNATIONAL SCHEME BY THE REPORT'S OWN WORDS,
so nothing is tagged as one:

* OCCUPATION is BOSCO, the Botswana Standard Classification of Occupations
  ("jobs classified according to major groups of BOSCO"). National.
* INDUSTRY has twenty-one groups whose names follow ISIC Rev.4's sections, but
  the report never names the scheme it used. National, not ISIC Rev.4 --
  tagging an unstated scheme would be inference presented as publication.
* SECTOR / EMPLOYER CATEGORY and STATUS IN EMPLOYMENT are Botswana's own
  groupings (Ipelegeng, piece jobs, "as an employee for someone else"). National.

SEVERAL TABLES SHARE A PAGE WITH THE SAME ROW LABELS (1.5a counts above 1.5b
percentages, both nine columns wide), which is why every table is located by
its `caption`, never by page.

CITIZENSHIP IS NOT A SCHEMA DIMENSION. Tables 1.5a/1.5b and M9 split Citizens /
Non-citizens / All employed; only the All-employed columns are taken. The
citizen split is published but has no column to live in.

TREND TABLES ARE DATED FROM THEIR OWN HEADERS. 1.5b (second of that number --
the report prints two tables called "1.5b"), 1.6b and 1.7b carry earlier
quarters beside the current one. Each earlier column takes its period from the
header line; the CURRENT quarter's column is skipped because 1.5a, 1.6a and
1.7a already publish it with the sex split.

A PRINTED ERROR, NOT COLLECTED: in Table 1.6b the Q4 2022 percentage column is
a copy of Q4 2021's, identical in every row (Central Government 18.2, Private
Sector 37.4 ...), while the Q4 2022 COUNTS differ and give 16.7% and 35.9%.
Those percentages are skipped; the counts are kept. Q4 2021's percentages do
reconcile with its counts and are kept.

LABELS ARE KEPT AS PRINTED EVEN WHERE THE REPORT IS INCONSISTENT WITH ITSELF:
the occupation residual is "Other" in 1.5a and "Other Specialized
Professionals" in 1.5b; "Finance and Insurance" in 1.7a is "Finance and
Insurance Activities" in 1.7b.

FORMALITY -- FOUR TOTALS ON FOUR DIFFERENT UNIVERSES, which do not add up to
total employment and must not be made to:
* informal SECTOR employment (ISE1, 173,583) excludes people employed by
  households;
* informal EMPLOYMENT (IE1, 257,289) was asked of employees/wage earners only,
  "not the self-employed";
* formal SECTOR employment (1.11a, 504,738) and formal employment (1.21,
  384,515) are the corresponding formal counts.
The cross-tabs of each by industry/occupation are not taken: the schema has one
category per row, and formality x industry needs two.

CROSS-CHECK (Q1 2024): employed 754,146 (M 371,638 / F 382,509); elementary
occupations 233,519 = 31.0%; public administration 153,044 = 20.3%; private
sector 277,775 = 36.8%; employees for someone else 573,531 = 76.1%; informal
sector employment 173,583; informal employment 257,289.
"""
from __future__ import annotations

from .pdf_tables_labour import make_parser

_SKIP = {"skip": True}


def _n(sex: str, **kw) -> dict:
    return {"sex": sex, "measure": "count", "unit": "persons", **kw}


def _p(sex: str, **kw) -> dict:
    return {"sex": sex, "measure": "share", "unit": "percent", **kw}


_MFT_N = [_n("male"), _n("female"), _n("total")]
_MFT_P = [_p("male"), _p("female"), _p("total")]
_CITIZEN_SKIP = [_SKIP] * 6          # Citizens M/F/T, Non-citizens M/F/T
_QUARTER = r"Q[1-4]\s*20\d{2}"


def _trend(n_periods: int, skip_share: tuple[int, ...] = ()) -> list[dict]:
    """Counts | % per earlier quarter; the last (current) quarter is skipped."""
    cols = []
    for i in range(n_periods - 1):
        cols.append(_n("total", period_index=i))
        cols.append(_SKIP if i in skip_share else _p("total", period_index=i))
    return cols + [_SKIP, _SKIP]


# The formality tables are read for their published Total row only.
_TOTAL_ONLY = {"label": r"^(Total)\s+(?=\d)", "expect_rows": 1}


LAYOUT = {
    "survey": "Quarterly Multi-Topic Survey (QMTS) Labour Force Module",
    "frequency": "quarterly",
    # The employed tables total 754,146, which is the 15+ population's
    # employment; the report publishes an 18+ base beside it for some rates.
    "working_age_base": "15+",
    "decimal": ".",
    "period_patterns": [r"QMTS,?\s*(Q[1-4]\s*20\d{2})"],
    "tables": [
        # --- occupation (BOSCO) ------------------------------------------
        {
            "caption": r"Table 1\.5a:\s*Currently Employed by Occupation",
            "topic": "occupation", "classification": "National",
            "columns": _CITIZEN_SKIP + _MFT_N,
            "dash_placeholder": True, "series_code": "QMTS T1.5a",
            "row_scan": {"expect_rows": 11},
        },
        {
            "caption": r"Table 1\.5b:\s*Percentage of Currently Employed by Occupation",
            "topic": "occupation", "classification": "National",
            "columns": _CITIZEN_SKIP + _MFT_P,
            "dash_placeholder": True, "series_code": "QMTS T1.5b",
            "row_scan": {"expect_rows": 11},
        },
        {
            "caption": r"Table 1\.5b:\s*Currently Employed by Occupation & Sex QMTS",
            "topic": "occupation", "classification": "National",
            "period_header": _QUARTER, "period_count": 5,
            "columns": _trend(5),
            "dash_placeholder": True, "series_code": "QMTS T1.5b-trend",
            "row_scan": {"expect_rows": 11},
        },
        # --- sector / employer category ------------------------------------
        {
            "caption": r"Table 1\.6a:",
            "topic": "sector", "classification": "National",
            "columns": _MFT_N + _MFT_P + [_SKIP, _SKIP],   # Q3 2023 is in 1.6b
            "dash_placeholder": True, "series_code": "QMTS T1.6a",
            "row_scan": {"expect_rows": 11},
        },
        {
            "caption": r"Table 1\.6b:",
            "topic": "sector", "classification": "National",
            "period_header": _QUARTER, "period_count": 5,
            # Q4 2022's % column (index 2) is a printed copy of Q4 2021's.
            "columns": _trend(5, skip_share=(2,)),
            "dash_placeholder": True, "series_code": "QMTS T1.6b-trend",
            "row_scan": {"expect_rows": 11},
        },
        # --- industry -----------------------------------------------------
        {
            "caption": r"Table 1\.7a:",
            "topic": "industry", "classification": "National",
            "columns": _MFT_N + _MFT_P,
            "dash_placeholder": True, "series_code": "QMTS T1.7a",
            "row_scan": {"expect_rows": 22},
        },
        {
            "caption": r"Table 1\.7b:",
            "topic": "industry", "classification": "National",
            "period_header": _QUARTER, "period_count": 4,
            "columns": _trend(4),
            "dash_placeholder": True, "series_code": "QMTS T1.7b-trend",
            "row_scan": {"expect_rows": 22},
        },
        # --- status in employment, three sex blocks ------------------------
        {
            "caption": r"Table M9:",
            "topic": "employment_status", "classification": "National",
            # Citizens | Non-citizens | Total employed, as counts then as %.
            "columns": [_SKIP, _SKIP, _n("total"), _SKIP, _SKIP, _p("total")],
            "blocks": [
                {"match": r"^Total\s+(?=[A-Za-z])", "set": {"sex": "total"}, "name": "total"},
                {"match": r"^Male\s+(?=[A-Za-z])", "set": {"sex": "male"}, "name": "male"},
                {"match": r"^Female\s+(?=[A-Za-z])", "set": {"sex": "female"}, "name": "female"},
            ],
            "dash_placeholder": True, "series_code": "QMTS TM9",
            "row_scan": {"expect_rows": 18},
        },
        # --- formality: the published totals of each universe --------------
        {
            "caption": r"Table ISE1:",
            "topic": "formality", "classification": "Not applicable",
            "columns": _MFT_N + [_SKIP, _SKIP],
            "label_map": {"Total": "Informal sector employment"},
            "dash_placeholder": True, "series_code": "QMTS TISE1",
            "row_scan": _TOTAL_ONLY,
        },
        {
            "caption": r"Table IE1:",
            "topic": "formality", "classification": "Not applicable",
            "columns": _MFT_N + [_SKIP],
            "label_map": {"Total": "Informal employment"},
            "dash_placeholder": True, "series_code": "QMTS TIE1",
            "row_scan": _TOTAL_ONLY,
        },
        {
            "caption": r"Table 1\.11a:",
            "topic": "formality", "classification": "Not applicable",
            "columns": _CITIZEN_SKIP + _MFT_N + [_SKIP],
            "label_map": {"Total": "Formal sector employment"},
            "dash_placeholder": True, "series_code": "QMTS T1.11a",
            "row_scan": _TOTAL_ONLY,
        },
        {
            "caption": r"Table 1\.21:",
            "topic": "formality", "classification": "Not applicable",
            "columns": _MFT_N + [_SKIP] * 6,
            "label_map": {"Total": "Formal employment"},
            "dash_placeholder": True, "series_code": "QMTS T1.21",
            "row_scan": _TOTAL_ONLY,
        },
    ],
}


# EVERY TABLE HERE ENDS ON ITS OWN "Total" ROW, and what follows is commentary
# rather than the next caption -- commentary that quotes the table's figures:
#
#     "Public administration employment increased from 144,200 persons (18.3
#      percent) in Q3 2023 to 153,044 persons (20.3 percent) in Q1 2024"
#
# That sentence carries exactly six numbers and scanned as a perfectly shaped
# industry row, giving Table 1.7a a 23rd "category" and a 153,044 percent.
# Closing each region on its Total row is what keeps prose out of the data.
# M9 is excluded: each of its three sex blocks carries a Total row of its own.
for _table in LAYOUT["tables"]:
    if _table["series_code"] != "QMTS TM9":
        _table["end_after"] = r"^Total\s+[\d(-]"


parse = make_parser(LAYOUT)
