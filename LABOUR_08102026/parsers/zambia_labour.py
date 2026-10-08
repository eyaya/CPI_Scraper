"""Zambia — ZamStats Labour Force Survey, employment composition.

One module per country, as everywhere else in this repo. The layout is
declarative and read by `pdf_tables_labour.make_parser`.

ZAMBIA STATES ITS OWN CLASSIFICATION, which is unusual and worth honouring
precisely. Section 5.4 of the report says the country classified employed
persons on ICSE-93 "until 2023" and now reports on ICSE-18, of which it uses
the AUTHORITY hierarchy:

    "While both classifications are important, ICSE-18-A will be utilized in
     the current reporting ... which categorizes workers into 10 groups"

So these rows are tagged `ICSE-18-A`, not a bare `ICSE-18`. The distinction is
the source's own and collapsing it would discard information ZamStats went out
of its way to state -- and it also marks a METHODOLOGY BREAK against any
Zambian status series before 2024.

TABLE 5.2 WRAPS ITS LABELS THREE DIFFERENT WAYS on one page, which is why the
engine's `join_wrapped_labels` does the work rather than the patterns:

    Employers in corporations 60,762 1.5 43,048 1.8 17,714 1.1   <- one line
    Employers in household market                                <- head
    34,196 0.9 23,589 1.0 10,607 0.7                             <- values
    enterprises                                                  <- tail
    Own account workers in household                             <- head
    market enterprises without 1,739,620 43.8 966,389 39.9 ...    <- values AND label
    employees                                                    <- tail

SIX NUMERIC COLUMNS: a count and a percentage for each of Total, Male and
Female. Both are published, so both are kept -- the percentage as a `share`,
not recomputed from the counts.

A DASH IS NOT A ZERO. "Dependent contractors 0 - 0 - 0 -" prints the count as
zero and the percentage as a dash. `to_number` returns None for the dash, so
the row's number count is three rather than six and the row is skipped rather
than shifted. That is the correct outcome here: ZamStats is saying the share is
not defined, and inventing a 0.0 would be a figure it did not publish.

CROSS-CHECK (2024): total employed 3,972,883 (male 2,425,055 / female
1,547,828); own-account workers in household market enterprises without
employees 1,739,620 = 43.8%, the largest group, with 39.9% of males and 50.0%
of females; fixed-term employees 895,290 = 22.5%; employers in corporations
60,762 = 1.5%.
"""
from __future__ import annotations

from .pdf_tables_labour import make_parser

# Total | Male | Female, each printed as a count and then a percentage.
_N_PCT_BY_SEX = [
    {"sex": "total", "measure": "count", "unit": "persons"},
    {"sex": "total", "measure": "share", "unit": "percent"},
    {"sex": "male", "measure": "count", "unit": "persons"},
    {"sex": "male", "measure": "share", "unit": "percent"},
    {"sex": "female", "measure": "count", "unit": "persons"},
    {"sex": "female", "measure": "share", "unit": "percent"},
]

LAYOUT = {
    "survey": "Labour Force Survey 2024",
    "frequency": "annual",
    # ZamStats surveys the population aged 15 and over.
    "working_age_base": "15+",
    "decimal": ".",
    "period": "2024",
    "reference_period": "LFS 2024",
    "tables": [
        {
            "page_contains": ["employed persons by status in employment"],
            "page_excludes": ["list of tables"],
            "topic": "employment_status",
            "classification": "ICSE-18-A",
            "columns": _N_PCT_BY_SEX,
            "series_code": "LFS2024 T5.2",
            "row_scan": {
                # Ten ICSE-18-A groups plus the table's own Total row. The
                # guard is set at 8 rather than 11 because "Dependent
                # contractors" prints its percentages as dashes and is
                # legitimately skipped — see the module note.
                "expect_rows": 8,
            },
        },
    ],
}


parse = make_parser(LAYOUT)
