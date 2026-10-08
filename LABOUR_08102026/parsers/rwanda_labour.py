"""Rwanda — NISR annual Labour Force Survey report, employment composition.

One module per country, read by `pdf_tables_labour.make_parser`. The report is
the one `unemployment` collects; this layout opens only Chapter 4's tables.

SEVEN YEARS IN EVERY TREND TABLE (2019-2025), each column dated from the
table's own header. NISR revises earlier years, so every run re-collects the
whole back-series and the merge lets the newest report win.

STATUS IN EMPLOYMENT ON BOTH STANDARDS, as the report says it deliberately
produces them. NISR "adopted ICSE-18 ... starting in February 2025" and keeps
ICSE-93 "to allow readers understanding the effect of dependent contractor
category on the former distribution":
* Table 4.1 -- the ICSE-93 series (employee, employer, own account worker,
  member of cooperative, contributing family worker), thousands, 2019-2025;
* Table 4.2 -- ICSE-18 for 2025 by sex and urban/rural, persons and %.
The report says ICSE-18 without naming a hierarchy, so the rows say ICSE-18.

INDUSTRY is "ISIC High level" in the table header; its sections include
Information and communication and Activities of households as employers, which
exist only in ISIC Rev.4. Tagged ISIC Rev.4.

OCCUPATION: the report never names the scheme. The nine group names are
ISCO-08's, but that is inference, so the rows say National.

UNITS: Tables 4.1, 4.3 and 4.5 are in THOUSANDS ("(,000)") and are emitted as
thousand_persons, not multiplied out. The "% change 2024-2025" column is
derived and is not taken.

A PUBLISHED INCONSISTENCY, KEPT AS PRINTED: total employment for 2020 is 2,661
thousand in Table 4.1 and 4.3 but 3,461 thousand in Table 4.5. Both are what
NISR prints; they sit under different topics and do not collide.

WORKING-AGE BASE IS 16+ ("persons aged 16 years and above").

FORMALITY (Table 4.7): years run DOWN the rows, so the row label is the period
and each column names its category. "Don't know" is a published category and
is kept. Table 4.8 is not taken: several of its cells are blank in the text
layer (2020 and 2023 rows carry 8 values for 9 columns) and there is no way to
tell which cell is missing.

CROSS-CHECK (2025): employed 4,772,705 (M 2,556,943 / F 2,215,761);
ICSE-18 employees 2,825,271 = 59.2%; dependent contractors 410,228 = 8.6%;
ICSE-93 employees 3,093 thousand; agriculture 39.1% of employment;
informal employment 91.2% (M 89.8 / F 92.8).
"""
from __future__ import annotations

from .pdf_tables_labour import make_parser

_SKIP = {"skip": True}
_YEAR = r"\b(?:19|20)\d{2}\b"


def _k(i: int) -> dict:
    return {"sex": "total", "measure": "count", "unit": "thousand_persons",
            "period_index": i}


def _pct(i: int) -> dict:
    return {"sex": "total", "measure": "share", "unit": "percent", "period_index": i}


_SEVEN_K = [_k(i) for i in range(7)] + [_SKIP]      # + "% change" column
_SEVEN_PCT = [_pct(i) for i in range(7)]

_SEX_AREA = [
    {"sex": "total"}, {"sex": "male"}, {"sex": "female"},
    {"sex": "total", "locality": "urban", "locality_label": "Urban"},
    {"sex": "total", "locality": "rural", "locality_label": "Rural"},
]
_ICSE18_COLS = ([{**c, "measure": "count", "unit": "persons"} for c in _SEX_AREA]
                + [{**c, "measure": "share", "unit": "percent"} for c in _SEX_AREA])

_FORMALITY_COLS = [
    {"sex": sex, "measure": "share", "unit": "percent", "characteristic": cat}
    for sex in ("male", "female", "total")
    for cat in ("Formal employment", "Informal employment", "Don’t know")
]


def _trend(caption: str, topic: str, classification: str, columns: list,
           expect: int, code: str) -> dict:
    return {
        "caption": caption, "topic": topic, "classification": classification,
        "period_header": _YEAR, "period_count": 7,
        "columns": columns, "series_code": code,
        "row_scan": {"expect_rows": expect},
    }


LAYOUT = {
    "survey": "Labour Force Survey (LFS)",
    "frequency": "annual",
    "working_age_base": "16+",
    "decimal": ".",
    "period_patterns": [r"Labour Force Survey (20\d{2})"],
    "tables": [
        _trend(r"Table 4\.\s*1\s*:", "employment_status", "ICSE-93",
               _SEVEN_K, 6, "LFS T4.1"),
        {
            "caption": r"Table 4\.\s*2\s*:",
            "topic": "employment_status", "classification": "ICSE-18",
            "columns": _ICSE18_COLS, "series_code": "LFS T4.2",
            "row_scan": {"expect_rows": 6},
        },
        _trend(r"Table 4\.\s*3\s*:", "occupation", "National",
               _SEVEN_K, 10, "LFS T4.3"),
        _trend(r"Table 4\.\s*4\s*:", "industry", "ISIC Rev.4",
               _SEVEN_PCT, 21, "LFS T4.4"),
        _trend(r"Table 4\.\s*5\s*:", "industry", "ISIC Rev.4",
               _SEVEN_K, 22, "LFS T4.5"),
        {
            "caption": r"Table 4\.\s*7\s*:",
            "topic": "formality", "classification": "Not applicable",
            "columns": _FORMALITY_COLS, "series_code": "LFS T4.7",
            "label_is_period": True,
            # The header's last line runs straight into the first data row, and
            # folding "wrapped labels" would glue it onto 2019.
            "join_wrapped_labels": False,
            "row_scan": {"label": r"^((?:19|20)\d{2})\s+(?=\d)",
                         "label_ok": r"^\d", "expect_rows": 7},
        },
    ],
}


parse = make_parser(LAYOUT)
