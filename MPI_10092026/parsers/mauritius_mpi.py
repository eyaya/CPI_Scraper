"""Mauritius — MPI table layout and parser.

One module per country, as everywhere else in this repo. The layout is
declarative and read by `mpi_tables.make_parser`; the comments beside it
record the report's actual column order and the cross-check values used to
prove the layout still holds.
"""
from __future__ import annotations

from ._vocab import _NATIONAL
from .mpi_tables import make_parser

# =========================================================================
# MAURITIUS -- Statistics Mauritius, "National Multidimensional Poverty Index,
# 2022" (Housing and Population Census 2022). Published July 2026, the newest
# national MPI in Africa.
#
# REWRITTEN against the downloaded PDF. Table 2 leads with the INDEX, not the
# incidence:
#
#                            MPI    Headcount Ratio   Intensity of Poverty
#   Republic of Mauritius   0.041        10.8%              37.9%
#
# The earlier layout assumed H | A | M0 and captured only part of it.
#
# Annex Table A1 gives the same three metrics for all 166 administrative areas
# -- 160 municipal wards and village council areas on the Island of Mauritius
# plus the six regions of Rodrigues -- each row prefixed with a four-digit
# geographical code and two population counts:
#
#   1910 Albion VCA  7,462  601  8.1  37.9  0.031
#
# That is a genuine 166-row table, so it is scanned rather than enumerated,
# with the code and the two counts skipped. `expect_rows: 140` is the guard
# against a silent collapse.
#
# The poverty cutoff is stated in the report as 30% of total weighted
# deprivations, and each of the 15 indicators carries weight 1/15.
#
# CROSS-CHECK (verbatim):
#   Republic of Mauritius  MPI 0.041 | H 10.8% | A 37.9%
#   Island of Mauritius    MPI 0.038 | H 10.2% | A 37.5%
#   Island of Rodrigues    MPI 0.120 | H 29.2% | A 41.2%
#   Albion VCA MPI 0.031; Bambous VCA 0.080; Baie du Cap VCA 0.091
#   Range across areas: 0.006 (Quatre Bornes Ward 2) to 0.225 (Le Morne VCA)
# =========================================================================
_MU_COLS = [
    {"metric": "index_M0"},
    {"metric": "incidence_H"},
    {"metric": "intensity_A"},
]

LAYOUT = {
    "mpi_type": "national",
    "measure_name": "Mauritius National MPI",
    "survey": "Housing and Population Census 2022",
    "k_cutoff": 30, "n_dimensions": 5, "n_indicators": 15,
    "unit_of_analysis": "person", "frequency": "ad_hoc", "decimal": ".",
    "period": "2022", "reference_period": "Census 2022",
    "tables": [
        {   # Table 2 -- by island
            "page_contains": ["national mpi results by island"],
            "exact_numbers": True,
            "columns": _MU_COLS,
            "rows": [
                {"match": r"^Republic of Mauritius\b", **_NATIONAL},
                {"match": r"^Island of Mauritius\b",
                 "geography": "Island of Mauritius"},
                {"match": r"^Island of Rodrigues\b",
                 "geography": "Island of Rodrigues"},
            ],
        },
        {   # Table A1 -- the 166 administrative areas
            # The caption "166 administrative areas" is printed once, but the
            # table runs over seven pages; the column header repeats on each,
            # so the header is what selects them.
            "page_contains": ["municipal wards/village council"],
            "exact_numbers": True,
            "columns": [
                {"skip": True},                       # resident population
                {"skip": True},                       # persons in MPI poverty
                {"metric": "incidence_H"},
                {"metric": "intensity_A"},
                {"metric": "index_M0"},
            ],
            "row_scan": {
                # The four-digit geographical code and any "Ward N" suffix are
                # part of the LABEL, not the data, so both sit inside the match
                # and only what follows is parsed as numbers.
                "label": (r"^\d{4}\s+([A-Za-zÀ-ÿ][A-Za-zÀ-ÿ'’\-\./ ]{2,55}?"
                          r"(?:\s+Ward\s+\d+)?)\s+(?=[\d,]{2,})"),
                "label_ok": r"^[A-Za-zÀ-ÿ][A-Za-zÀ-ÿ'’\-\./ ]+(?: Ward \d+)?$",
                "expect_rows": 160,
            },
        },
    ],
}


parse = make_parser(LAYOUT)
