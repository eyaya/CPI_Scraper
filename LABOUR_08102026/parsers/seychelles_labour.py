"""Seychelles — NBS Labour Force Survey bulletin, employment composition.

One module per country, read by `pdf_tables_labour.make_parser`. The bulletin is
the one `unemployment` collects; this layout opens only Tables 7-10.

NBS NAMES EVERY SCHEME IT USES, and each is recorded exactly:

    7A        status in employment, ICSE-93
    7B1/7B2   status in employment, ICSE-18 by type of AUTHORITY  -> ICSE-18-A
    7C1/7C2   status in employment, ICSE-18 by type of ECONOMIC RISK -> ICSE-18-R
    8A        occupation, ISCO-08
    9         industry, ISIC Rev.4 (section letters A-U, plus X)

So the same people in the same quarter appear under three status
classifications. They are not duplicates; `classification` is in the merge key.

TWO QUARTERS PER TABLE, same quarter a year apart ("Q1 2025 & Q1 2026"). Both
columns are published and both are taken, each dated from the table's own
header, so a re-run of next year's bulletin revises the earlier quarter rather
than duplicating it.

ALL VALUES ARE COLUMN PERCENTAGES. There are no counts in these tables.

ROW-PERCENTAGE TABLES ARE NOT TAKEN. 8B and 9B give the sex split WITHIN each
occupation / industry ("Managers: 53.7% male"). That is a different quantity
from 8A's share of employed men who are managers, but it would carry the same
topic, category, sex and measure -- and the merge would let one overwrite the
other. Collecting the wrong one silently is worse than not collecting it.

THE AGGREGATED ICSE-18 TABLES (7B1, 7C1) repeat "Workers not classifiable by
status" and "Total" from their disaggregated tables, with different rounding
(0.0 against 0.1). Only their aggregate groups are taken from them, so each
key is written once.

LETTER-SPACED DIGITS. The text layer of 7B2, 7C2, 8A and 9 reads "7 5.4 9 1.0
8 3.2" for 75.4 91.0 83.2 and "4 .9" for 4.9. Every value in these tables has
one decimal, which is what makes `split_digit_repair` safe to switch on here.

CROSS-CHECK (Q1 2026, Male / Female / Both): ICSE-93 employees 77.4 / 90.7 /
84.4; ICSE-18-A dependent contractors 4.7 / 0.8 / 2.7; ISCO-08 service and
sales workers 15.6 / 33.1 / 24.7; ISIC Q human health 2.9 / 17.5 / 10.5;
informal employment 13.7 / 4.0 / 8.6.
"""
from __future__ import annotations

from .pdf_tables_labour import make_parser

# Male | Female | Both sexes, for each of the two quarters in the header.
_TWO_QUARTERS = [
    {"sex": sex, "measure": "share", "unit": "percent", "period_index": p}
    for p in (0, 1) for sex in ("male", "female", "total")
]
# The default label pattern stops at "(" so "(ICSE 93)" style headers are not
# read as data; these tables have parentheses INSIDE category names ("Independent
# workers without employees (Own-account workers)"), so a label ends only where a
# number or a free-standing dash begins.
_LABEL = r"^([A-Za-z][^\d]{2,120}?)\s+(?=\d|[-–](?:\s|$))"
_CODED_LABEL = r"^((?:[0-9X]|[A-Z]) - [^\d]{2,120}?|Total)\s+(?=\d|[-–](?:\s|$))"


def _table(caption: str, topic: str, classification: str, expect: int,
           code: str, **extra) -> dict:
    scan = {"label": extra.pop("label", _LABEL), "expect_rows": expect}
    if "exclude" in extra:
        scan["exclude_labels"] = extra.pop("exclude")
    if extra.pop("coded", False):
        scan["label"] = _CODED_LABEL
        scan["label_ok"] = r"."
    return {
        "caption": caption, "topic": topic, "classification": classification,
        "columns": _TWO_QUARTERS,
        "period_header": r"Q[1-4]\s*20\d{2}", "period_count": 2,
        "dash_placeholder": True, "series_code": code, "row_scan": scan,
        **extra,
    }


_AGG_REPEATS = ["Workers not classifiable by status", "Total"]

LAYOUT = {
    "survey": "Labour Force Survey",
    "frequency": "quarterly",
    "working_age_base": "15+",
    "decimal": ".",
    # Every column is dated from its table header; this is the bulletin's own
    # current quarter, used only if a table ever lacks one.
    "period_patterns": [r"Q[1-4]\s*20\d{2}\s*&\s*(Q[1-4]\s*20\d{2})"],
    "tables": [
        _table(r"Table 7A:", "employment_status", "ICSE-93", 6, "LFS T7A"),
        _table(r"Table 7B1:", "employment_status", "ICSE-18-A", 2, "LFS T7B1",
               exclude=_AGG_REPEATS),
        _table(r"Table 7B2:", "employment_status", "ICSE-18-A", 7, "LFS T7B2",
               split_digit_repair=True),
        _table(r"Table 7C1:", "employment_status", "ICSE-18-R", 2, "LFS T7C1",
               exclude=_AGG_REPEATS),
        _table(r"Table 7C2:", "employment_status", "ICSE-18-R", 7, "LFS T7C2",
               split_digit_repair=True),
        _table(r"Table 8A:", "occupation", "ISCO-08", 12, "LFS T8A",
               coded=True, split_digit_repair=True),
        _table(r"Table 9:", "industry", "ISIC Rev.4", 23, "LFS T9",
               coded=True, split_digit_repair=True),
        # Unit of production: informal sector / formal sector / households.
        _table(r"Table 10A:", "formality", "Not applicable", 4, "LFS T10A"),
        # Nature of the main job: informal / formal employment. Its "Total"
        # (100.0) would collide with 10A's on the merge key.
        _table(r"Table 10B:", "formality", "Not applicable", 2, "LFS T10B",
               exclude=["Total"]),
    ],
}


parse = make_parser(LAYOUT)
