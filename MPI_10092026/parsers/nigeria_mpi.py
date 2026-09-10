"""Nigeria — MPI table layout and parser.

One module per country, as everywhere else in this repo. The layout is
declarative and read by `mpi_tables.make_parser`; the comments beside it
record the report's actual column order and the cross-check values used to
prove the layout still holds.
"""
from __future__ import annotations

from ._vocab import COLS_M0_H_A, _URBAN, _RURAL, _NATIONAL
from .mpi_tables import make_parser

# =========================================================================
# NIGERIA -- NBS, "Nigeria Multidimensional Poverty Index (2022)". The largest
# MPI exercise in Africa: 4 dimensions, 15 indicators, and disaggregation down
# to 109 senatorial districts.
#
# k = 25% -- "more than a quarter of weighted indicators", not the global 33.3%.
#
# COLUMN ORDER -- the INDEX leads, and two columns follow the three measures:
#
#     Area      MPI    Incidence  Intensity  Population   Number of poor
#                      (H, %)     (A, %)     share (%)    people (million)
#     National  0.257  62.9       40.9       100.0        132.92
#
# The layout carried a standing warning that it had never been checked against
# the printed table, and it was wrong: it declared `H | A | M0` and took the
# TRAILING three numbers, so M0 read 132.92 -- the count of poor Nigerians, in
# millions. Only the impossible index caught it; the H/A swap would have
# shipped silently. Now verified against the report, page by page.
#
# The population share is skipped (a share of Nigeria's population, not an MPI
# measure). SO IS THE COUNT OF POOR PEOPLE: it is printed in MILLIONS, and the
# schema's `population_poor` is a count of persons. Writing 132.92 there would
# be off by six orders of magnitude, and multiplying it up would be this
# collector computing a figure the NSO did not print.
#
# CROSS-CHECK: National 0.257 / 62.9 / 40.9; Rural 0.302 / 72.0 / 41.9;
# Urban 0.155 / 42.0 / 36.9; North East and North West both 0.324; South West
# 0.151 (least poor zone); with PLWDs 0.302 / 71.4 / 42.3; children 0-17
# 0.282 / 67.5 / 41.8 against adults 18+ 0.235 / 58.7 / 40.0.
#
# DEFERRED, and deliberately:
#   * BY STATE -- the report presents the 36 States and the FCT as Figure 8
#     and Map 1, charts with no printed table. The numbers exist only in the
#     appendix contribution tables.
#   * BY SENATORIAL DISTRICT -- Table 6 prints only the TEN POOREST, and even
#     there one label wraps mid-row ('Jigawa North / East') with its incidence
#     stranded on the caption line. The full 109 are in Appendix D, whose row
#     labels are hyphen-broken across lines ('Ad- / amawa'), which needs
#     glyph geometry rather than line matching.
#   * THE GLOBAL-MPI COMPARISON LINE the report quotes (H 46.4%, MPI 0.254 for
#     2018) appears in running prose, not in a table, so there is no row to
#     read. It is noted here because it is the only instance found across all
#     54 countries of an NSO republishing OPHI's global MPI, and if a future
#     edition tabulates it, it must be tagged `mpi_type: global`.
# =========================================================================

# MPI | H | A | population share (skipped) | number of poor, millions (skipped)
_COLS = COLS_M0_H_A + [{"skip": True}, {"skip": True}]

_ZONES = ["North Central", "North East", "North West",
          "South East", "South South", "South West"]

LAYOUT = {
    "mpi_type": "national",
    "measure_name": "Nigeria MPI",
    "survey": "MPIS 2021/2022 (Multidimensional Poverty Index Survey)",
    "k_cutoff": 25, "n_dimensions": 4, "n_indicators": 15,
    "unit_of_analysis": "person", "frequency": "ad_hoc", "decimal": ".",
    "period": "2022", "reference_period": "MPIS 2021/2022",
    "tables": [
        # Table 4 -- by area. The only table carrying the national row, which
        # the other three repeat identically; they leave it to this one.
        {
            "page_contains": ["table 4: multidimensional poverty by area"],
            "exact_numbers": True,
            "columns": _COLS,
            "rows": [
                {"match": r"^National\b", **_NATIONAL},
                {"match": r"^Rural\b", **_RURAL},
                {"match": r"^Urban\b", **_URBAN},
            ],
        },
        # Table 5 -- by zone. Zones are geographic groupings the NBS reports in
        # their own right, so they are carried by `geography`, exactly as the
        # regions of every other country here are.
        {
            "page_contains": ["table 5: multidimensional poverty by zone"],
            "exact_numbers": True,
            "columns": _COLS,
            "rows": [{"match": r"^%s\s+(?=[\d.])" % z, "geography": z}
                     for z in _ZONES],
        },
        # Table 7 -- by whether the household includes a person living with a
        # disability.
        {
            "page_contains": ["table 7: multidimensional poverty by disability"],
            "exact_numbers": True,
            "columns": _COLS,
            "rows": [
                {"match": r"^No PLWDs\b", "topic": "disability",
                 "characteristic": "No person living with a disability"},
                {"match": r"^With PLWDs\b", "topic": "disability",
                 "characteristic": "At least one person living with a disability"},
            ],
        },
        # Table 11 -- children against adults. The labels use an EN DASH
        # ('0–17'); the pattern accepts either dash so a font change cannot
        # drop the row.
        {
            "page_contains": ["table 11: multidimensional poverty by age group"],
            # THE AGE LABELS ARE NUMBERS. '0-17 0.282 67.5 41.8 47.2 67.28'
            # holds seven numbers, not five, so `exact_numbers` rejected both
            # rows outright and the age split was dropped without a value ever
            # being mis-assigned -- a silent gap rather than a wrong figure.
            # `leading_run` reads only what follows the matched label.
            "leading_run": True,
            "exact_numbers": True,
            "columns": _COLS,
            "rows": [
                {"match": r"^0[-–]17\b", "topic": "age", "age_group": "0-17",
                 "characteristic": "0-17"},
                {"match": r"^18\+", "topic": "age", "age_group": "18+",
                 "characteristic": "18+"},
            ],
        },
    ],
}


parse = make_parser(LAYOUT)
