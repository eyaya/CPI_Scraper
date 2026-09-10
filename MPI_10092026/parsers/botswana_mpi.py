"""Botswana — MPI table layout and parser.

One module per country, as everywhere else in this repo. The layout is
declarative and read by `mpi_tables.make_parser`; the comments beside it
record the report's actual column order and the cross-check values used to
prove the layout still holds.
"""
from __future__ import annotations

from ._vocab import _RURAL, _NATIONAL
from .mpi_tables import make_parser

# =========================================================================
# BOTSWANA -- Statistics Botswana, "Pilot National Multidimensional Poverty
# Index Report 2021" (BMTHS 2015/16).
#
# REWRITTEN against the downloaded PDF. The first version of this layout had
# the table transposed; it is not. Table 3.4.1 is the ordinary shape, rows are
# strata and columns are metrics -- but with a standard-error column wedged
# between incidence and intensity, and vulnerable/severe/population-share
# after the index:
#
#   Strata | Incidence | Standard Errors | Intensity | MPI | Vulnerable | Severe | Population Share
#   National  20.84%      0.94%            51.09      0.106   15.94%      3.39%    100%
#
# Botswana wraps its labels FORWARD -- "Kweneng" then a line reading "East" --
# and five Central districts plus both Kweneng, both Ngwaketse, both Ngamiland
# and both Kgalagadi rows are otherwise indistinguishable. `join_wrapped_labels`
# folds the trailing word back before matching.
#
# *** THIS REPORT ALSO CARRIES A GLOBAL MPI. *** Appendix 5 prints, for all 26
# districts and the nation, three side-by-side series: monetary poverty, the
# 2020 GLOBAL MPI (credited to Alkire, Kanagaratnam and Suppa), and the pilot
# national MPI. The global column is harvested as `mpi_type: global`, which is
# what makes it the richest global-MPI republication by any African NSO in this
# package -- 27 rows against Nigeria's single comparison line. The monetary
# column is not an MPI and is skipped; the national column is skipped here
# because Table 3.4.3 already supplies it with its full metric set.
#
# CROSS-CHECK (verbatim):
#   National       20.84 | 51.09 | 0.106 | vulnerable 15.94 | severe 3.39
#   Cities/Towns    5.34 | 47.64 | 0.025      Urban Villages 14.05 | 49.98 | 0.070
#   Rural Areas    37.48 | 51.85 | 0.194
#   Ngamiland West 60.82 | 53.75 | 0.327   Kweneng West 50.34 | 55.89 | 0.281
#   Gaborone        2.57 | 44.14 | 0.011   Orapa 0 | 0 | 0
#   Appendix 5 global MPI: National 17.20 | Kweneng West 45.90 | Gaborone 1.30
# =========================================================================
_BW_COLS = [
    {"metric": "incidence_H"},
    {"skip": True},                                   # standard error
    {"metric": "intensity_A"},
    {"metric": "index_M0"},
    {"metric": "vulnerable"},
    {"metric": "severe_poverty"},
    {"skip": True},                                   # population share
]
# The district table repeats those seven and adds a share-of-the-poor column.
_BW_DISTRICT_COLS = _BW_COLS + [{"skip": True}]

_BW_GLOBAL = {
    "mpi_type": "global",
    "measure_name": "Global MPI 2020 (Alkire, Kanagaratnam & Suppa)",
    "survey": "Global MPI 2020, as republished by Statistics Botswana",
    "k_cutoff": 33.3, "n_dimensions": 3, "n_indicators": 10,
    "metric": "incidence_H",
}

LAYOUT = {
    "mpi_type": "national",
    "measure_name": "Botswana Pilot National MPI",
    "survey": "BMTHS 2015/16 (Botswana Multi-Topic Household Survey)",
    "k_cutoff": 40, "n_dimensions": 4, "n_indicators": 15,
    "unit_of_analysis": "person", "frequency": "ad_hoc", "decimal": ".",
    "period": "2016", "reference_period": "BMTHS 2015/16",
    "tables": [
        {   # Table 3.4.1 -- by strata
            "page_contains": ["multidimensional poverty by strata"],
            "join_wrapped_labels": True,
            "exact_numbers": True,
            "columns": _BW_COLS,
            "rows": [
                {"match": r"^Cities/Towns", "locality": "urban",
                 "locality_label": "Cities/Towns", "topic": "locality"},
                {"match": r"^Urban Villages", "locality": "other",
                 "locality_label": "Urban Villages", "topic": "locality"},
                {"match": r"^Rural Areas", **_RURAL,
                 "locality_label": "Rural Areas"},
                {"match": r"^National\b", **_NATIONAL},
            ],
        },
        {   # Table 3.4.3 -- by district
            "page_contains": ["multidimensional poverty by district"],
            "join_wrapped_labels": True,
            "exact_numbers": True,
            "columns": _BW_DISTRICT_COLS,
            "row_scan": {
                "label": r"^([A-Za-z][A-Za-z'’\-\. ]{2,40}?)\s+(?=[\d])",
                "expect_rows": 24,
                # The national line here duplicates Table 3.4.1 exactly.
                "exclude_labels": ["National"],
                "label_map": {"Francis- town": "Francistown",
                              "Central Mahalapy": "Central Mahalapye"},
            },
        },
        {   # Appendix 5 -- monetary | GLOBAL MPI | national, incidence only
            "page_contains": ["appendix 5"],
            "join_wrapped_labels": True,
            "exact_numbers": True,
            "columns": [
                {"skip": True},                       # monetary poverty
                {**_BW_GLOBAL},                       # the global MPI
                {"skip": True},                       # national MPI, from 3.4.3
            ],
            "row_scan": {
                "label": r"^([A-Za-z][A-Za-z'’\-\. ]{2,40}?)\s+(?=[\d])",
                "expect_rows": 24,
                "label_map": {"National": "Total country"},
            },
        },
    ],
}


parse = make_parser(LAYOUT)
