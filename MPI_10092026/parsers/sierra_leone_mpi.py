"""Sierra Leone — MPI table layout and parser.

One module per country, as everywhere else in this repo. The layout is
declarative and read by `mpi_tables.make_parser`; the comments beside it
record the report's actual column order and the cross-check values used to
prove the layout still holds.
"""
from __future__ import annotations

from ._vocab import _URBAN, _RURAL, _NATIONAL
from .mpi_tables import make_parser

# =========================================================================
# SIERRA LEONE -- Stats SL, "Sierra Leone Multidimensional Poverty Index 2019".
#
# Five dimensions, with Housing and Energy split out as their own -- distinctive.
#
# THE 2023 UPDATE IS NOT COLLECTABLE: it exists only on UNDP and OPHI, both
# aggregators. The newest NSO-hosted Sierra Leone MPI is this 2019 edition.
#
# EVERY ESTIMATE IS PUBLISHED WITH A 95% CONFIDENCE INTERVAL, which is why the
# rows are so wide. Table 3 prints ten numbers per row:
#
#     Area  | Pop.share | MPI  value lo    hi   | H  value lo   hi   | A value lo   hi
#     Rural |   55.7    | 0.520 0.507 0.534     | 86.3 84.5 88.1     | 60.3 59.8 60.8
#
# The layout previously declared just TWO columns, `incidence | MPI`, taking
# the trailing two numbers of whatever line matched. Against a ten-number row
# that reads A's confidence bounds as H and M0 -- and because it also selected
# pages by the bare word 'incidence', the rows it matched were the DISTRICT
# table in the appendix rather than Table 3 at all. Northern/Southern/Eastern
# are not row labels anywhere in this report; the districts are grouped as
# EAST/NORTH/SOUTH/WEST, and only in the contributions table.
#
# TABLES A7 AND A8 SHARE A PAGE and both list every district. They are told
# apart by `exact_numbers`: A7 carries a population count AND a share (eleven
# numbers), A8 only a share (ten). Without that the first 'Bo' on the page
# would answer for both.
#
# WRAPPED LABELS: 'Western Urban' and 'Western Rural' print their second word
# on the following line, so `join_wrapped_labels` folds it back -- otherwise
# both rows read as plain 'Western' and the second silently overwrites the first.
#
# CROSS-CHECK: national 64.8 / 57.9 / 0.375 [0.363, 0.386]; Rural 86.3 / 60.3 /
# 0.520; Urban 37.6 / 50.9 / 0.191. Districts: Pujehun 87.2 / 62.4 / 0.544
# (the poorest), Western Urban 28.5 / 48.9 / 0.140 (the least poor),
# Koinadugu 86.5 / 60.3 / 0.521.
#
# DEFERRED, and deliberately: Tables A9-A12 (youth, 36-64, 65+, male-headed by
# district) pair up two-to-a-page with IDENTICAL row labels and identical
# number counts, so nothing in the line itself says which table a 'Bo' belongs
# to. Reading them needs page-region geometry rather than line matching, and
# guessing would silently file one age group's values under another.
# =========================================================================

# Districts as printed in Table A7. 'Western Urban'/'Western Rural' are the two
# halves of the Western Area and are listed first in the report's own order.
_DISTRICTS = ["Western Urban", "Western Rural", "Bo", "Kenema", "Kailahun",
              "Kono", "Kambia", "Bombali", "Port Loko", "Koinadugu",
              "Moyamba", "Tonkolili", "Bonthe", "Pujehun"]

# MPI | its CI | H | its CI | A | its CI -- the report's order in every table.
_COLS_WITH_CI = [
    {"metric": "index_M0"},
    {"metric": "index_M0_ci_low", "unit": "index"},
    {"metric": "index_M0_ci_high", "unit": "index"},
    {"metric": "incidence_H"},
    {"metric": "incidence_H_ci_low"},
    {"metric": "incidence_H_ci_high"},
    {"metric": "intensity_A"},
    {"metric": "intensity_A_ci_low"},
    {"metric": "intensity_A_ci_high"},
]

LAYOUT = {
    "mpi_type": "national",
    "measure_name": "Sierra Leone MPI",
    "survey": "MICS 2017 (Multiple Indicator Cluster Survey)",
    "k_cutoff": 40, "n_dimensions": 5, "n_indicators": 14,
    "unit_of_analysis": "person", "frequency": "ad_hoc", "decimal": ".",
    "period": "2017", "reference_period": "MICS 2017",
    "tables": [
        # Table 3 -- national, rural and urban. Leading column is the
        # population share, which this schema does not model.
        {
            "page_contains": ["table 3: multidimensional poverty by rural/urban"],
            "exact_numbers": True,
            "columns": [{"skip": True}] + _COLS_WITH_CI,
            "rows": [
                {"match": r"^National\b", **_NATIONAL},
                {"match": r"^Rural\b", **_RURAL},
                {"match": r"^Urban\b", **_URBAN},
            ],
        },
        # Table A7 -- the same measures by district. Two leading columns here:
        # a population count (in hundreds) and a share.
        {
            "page_contains": ["table a7: mpi by district"],
            "join_wrapped_labels": True,
            "exact_numbers": True,
            "columns": [{"skip": True}, {"skip": True}] + _COLS_WITH_CI,
            "rows": [
                {"match": r"^%s\s+(?=[\d(])" % d.replace(" ", r"\s+"),
                 "geography": d}
                for d in _DISTRICTS
            ],
        },
    ],
}


parse = make_parser(LAYOUT)
