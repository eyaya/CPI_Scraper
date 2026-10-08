"""Ghana Report — MPI table layout and parser.

One module per country, as everywhere else in this repo. The layout is
declarative and read by `mpi_tables.make_parser`; the comments beside it
record the report's actual column order and the cross-check values used to
prove the layout still holds.
"""
from __future__ import annotations

from .mpi_tables import make_parser

# =========================================================================
# GHANA (report edition) -- GSS, "Ghana's Multidimensional Poverty Index"
# (2020), from GLSS7 2016/2017.
#
# THIS IS A DIFFERENT MEASURE FROM THE PxWeb TABLE already collected. Ghana has
# three MPI products and they are not one series:
#   - the StatsBank PHC 2021 table (parser `ghana_pxweb_mpi`, census-based);
#   - this 2020 report, 3 dimensions / 12 indicators / k = 33%, from GLSS7;
#   - a quarterly AHIES/QLFS series, 4 dimensions / 13 indicators / k = 33.3%,
#     which is NOT hosted on a GSS domain (see PENDING.md).
# The methodology changed between the 2020 report and the quarterly series, so
# they must never be chained.
#
# Note 3 dimensions and k=33% make this LOOK like the global MPI, but it uses
# 12 indicators, not 10 -- it is a national measure and is tagged as one.
#
# READ AGAINST THE PRINTED PAGES on 2026-10-07 (the file is the Wayback id_
# capture of GSS's own copy; see the descriptor). The first layout, written
# from notes, matched "^Incidence" -- but Table 3.1 prints the H row as
#     k-value=33% Headcount ratio (H, %) 45.6 43.7 47.5
# so it never matched, and Table 3.5's H row supplied "H = 71.0" (the male
# POPULATION SHARE) with "bounds" 47.7 / 45.4 (male H and its lower bound).
# Well-formed, in range, wrong. Taking TRAILING numbers and anchoring on
# "Headcount ratio" fixes it, as for Seychelles, which has the same shape.
#
# THE NATIONAL ROW IS PRINTED THREE TIMES AND NOT IDENTICALLY:
#     Table 3.1   M0 0.236 (0.224-0.2485)
#     Table 3.2   M0 0.236 (0.220-0.246)
#     Table 3.3   M0 0.240 (0.220-0.250)
# The national figures are taken from Table 3.1, the headline table; the
# "National" rows of 3.2 and 3.3 are not read (they would share its merge key).
#
# CROSS-CHECK: MPI 0.236 (0.224-0.2485); H 45.6 (43.7-47.5); A 51.7 (51-52.5);
# vulnerable 31.0; severe 21.4; rural H 64.6; Savannah M0 0.403; Northern H
# 80.8; male-headed M0 0.251, female-headed 0.199.
# =========================================================================

# Tables 3.2-3.4: [population share] | M0 + CI | H + CI | A + CI.
_GROUP_COLS = [
    {"metric": "index_M0"}, {"metric": "index_M0_ci_low", "unit": "index"},
    {"metric": "index_M0_ci_high", "unit": "index"},
    {"metric": "incidence_H"}, {"metric": "incidence_H_ci_low"},
    {"metric": "incidence_H_ci_high"},
    {"metric": "intensity_A"}, {"metric": "intensity_A_ci_low"},
    {"metric": "intensity_A_ci_high"},
]
_SHARE_THEN_GROUP = [{"skip": True}] + _GROUP_COLS


def _sex_cols(metric: str, lo: str, hi: str, unit: str | None = None,
              share: bool = False) -> list[dict]:
    u = {"unit": unit} if unit else {}
    cols = []
    for sex in ("male", "female"):
        if share:
            cols.append({"skip": True})          # population share of each sex
        cols += [{"metric": metric, "sex": sex, "characteristic": sex.title(), **u},
                 {"metric": lo, "sex": sex, "characteristic": sex.title(), **u},
                 {"metric": hi, "sex": sex, "characteristic": sex.title(), **u}]
    return cols


LAYOUT = {
    "mpi_type": "national",
    "measure_name": "Ghana MPI (GLSS7/MICS)",
    "survey": "GLSS7 2016/2017 with MICS 2011 and 2017/2018",
    "k_cutoff": 33, "n_dimensions": 3, "n_indicators": 12,
    "unit_of_analysis": "person", "frequency": "ad_hoc", "decimal": ".",
    "period": "2017", "reference_period": "GLSS7 2016/2017",
    "tables": [
        {   # Table 3.1 -- national, rows are metrics, `Value | CI low | CI high`
            "page_contains": ["table 3.1: incidence, intensity"],
            "take": "trailing",
            "columns": [{}, {"metric": "intensity_A_ci_low"},
                        {"metric": "intensity_A_ci_high"}],
            "rows": [
                {"match": r"^MPI\b", "metric": "index_M0",
                 "columns": [{"metric": "index_M0"},
                             {"metric": "index_M0_ci_low", "unit": "index"},
                             {"metric": "index_M0_ci_high", "unit": "index"}]},
                {"match": r"Headcount\s*ratio\s*\(H", "metric": "incidence_H",
                 "columns": [{"metric": "incidence_H"},
                             {"metric": "incidence_H_ci_low"},
                             {"metric": "incidence_H_ci_high"}]},
                {"match": r"^Intensity\s*\(A", "metric": "intensity_A"},
                # The vulnerability and severe-poverty rows carry intervals the
                # vocabulary has no bound metric for; only the estimate is kept.
                {"match": r"vulnerable to poverty", "metric": "vulnerable",
                 "columns": [{"metric": "vulnerable"}, {"skip": True},
                             {"skip": True}]},
                {"match": r"severe poverty", "metric": "severe_poverty",
                 "columns": [{"metric": "severe_poverty"}, {"skip": True},
                             {"skip": True}]},
            ],
        },
        {   # Table 3.2 -- rural / urban ("National" row read from Table 3.1)
            "page_contains": ["table 3.2: multidimensional poverty by rural/urban"],
            "take": "trailing",
            "columns": _SHARE_THEN_GROUP,
            "defaults": {"topic": "locality"},
            "rows": [
                {"match": r"^Rural\b", "locality": "rural",
                 "locality_label": "Rural", "characteristic": "Rural"},
                {"match": r"^Urban\b", "locality": "urban",
                 "locality_label": "Urban", "characteristic": "Urban"},
            ],
        },
        {   # Table 3.3 -- ecological zones: strata, not administrative areas
            "page_contains": ["table 3.3: multidimensional poverty by ecological"],
            "take": "trailing",
            "columns": _SHARE_THEN_GROUP,
            "defaults": {"topic": "locality", "locality": "other"},
            "rows": [
                {"match": r"^Coastal\b", "locality_label": "Coastal zone",
                 "characteristic": "Coastal zone"},
                {"match": r"^Forest\b", "locality_label": "Forest zone",
                 "characteristic": "Forest zone"},
                {"match": r"^Savannah\b", "locality_label": "Savannah zone",
                 "characteristic": "Savannah zone"},
            ],
        },
        {   # Table 3.4 -- the ten (pre-2019) administrative regions
            "page_contains": ["table 3.4: regional distribution"],
            "columns": _GROUP_COLS,
            "row_scan": {"expect_rows": 10},
        },
        {   # Table 3.5 -- TRANSPOSED: rows are metrics, columns male | female
            # household heads, each `[pop. share] value CI-low CI-high`; only
            # the H row prints the population shares.
            "page_contains": ["table 3.5: multidimensional poverty by gender"],
            "defaults": {"topic": "sex_of_head"},
            # The engine wants table-level columns; every row below brings its
            # own, since the H row alone carries the population shares.
            "columns": _sex_cols("index_M0", "index_M0_ci_low",
                                 "index_M0_ci_high", unit="index"),
            "rows": [
                {"match": r"^MPI\b",
                 "columns": _sex_cols("index_M0", "index_M0_ci_low",
                                      "index_M0_ci_high", unit="index")},
                {"match": r"^Incidence\s*\(H\)",
                 "columns": _sex_cols("incidence_H", "incidence_H_ci_low",
                                      "incidence_H_ci_high", share=True)},
                {"match": r"^Intensity\s*\(A\)",
                 "columns": _sex_cols("intensity_A", "intensity_A_ci_low",
                                      "intensity_A_ci_high")},
            ],
        },
    ],
}


parse = make_parser(LAYOUT)
