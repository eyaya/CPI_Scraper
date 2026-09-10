"""Seychelles — MPI table layout and parser.

One module per country, as everywhere else in this repo. The layout is
declarative and read by `mpi_tables.make_parser`; the comments beside it
record the report's actual column order and the cross-check values used to
prove the layout still holds.
"""
from __future__ import annotations

from .mpi_tables import make_parser

# =========================================================================
# SEYCHELLES -- NBS, "Multidimensional Poverty Index Report 2019".
#
# ROWS ARE METRICS, columns are `Index Value | CI lower | CI upper` -- one of
# only three measures here with published confidence intervals, and the only one
# whose headline table is shaped this way.
#
# k = 25%, the joint-lowest cutoff collected (with Nigeria). A parser that
# hard-coded the global 33.3% would mislabel every Seychellois row.
#
# The indicator set is the furthest from the global MPI of any here: Crime,
# Obesity, Substance use/abuse and Teenage pregnancy have no global analogue.
#
# CROSS-CHECK: MPI 0.040 [0.030, 0.049]; H 11.88 [9.23, 14.53];
# A 33.26 [31.07, 35.45].
# =========================================================================
LAYOUT = {
    "mpi_type": "national",
    "measure_name": "Seychelles MPI",
    "survey": "Quarterly Labour Force Survey, Q3 2019",
    "k_cutoff": 25, "n_dimensions": 4, "n_indicators": 14,
    "unit_of_analysis": "person", "frequency": "ad_hoc", "decimal": ".",
    "period": "2019", "reference_period": "LFS Q3 2019",
    "tables": [{
        "page_contains": ["poverty cut-off"],
        "take": "trailing",
        # EACH ROW'S BOUNDS NAME THE ESTIMATE THEY BRACKET. These were a bare
        # `confidence_low`/`confidence_high` pair, which is indistinguishable
        # across the three rows once written -- same metric, same geography,
        # same period -- so `merge_keys` treated all three lower bounds as one
        # row and the second run of this country collapsed nine rows to five,
        # leaving the two survivors unattributable. See schema.METRICS.
        "columns": [{}, {"metric": "intensity_A_ci_low"},
                    {"metric": "intensity_A_ci_high"}],
        "rows": [
            {"match": r"^MPI\b", "metric": "index_M0",
             "columns": [{"metric": "index_M0"},
                         {"metric": "index_M0_ci_low", "unit": "index"},
                         {"metric": "index_M0_ci_high", "unit": "index"}]},
            # The H row also carries the table's merged 'Poverty cut-off (k)'
            # cell, so the line reads
            #     k-value = 25% Headcount ratio (H, %) 11.88 9.23 14.53
            # and an ^H-anchored pattern never matches it. Missing this dropped
            # the headline incidence entirely while H's own confidence bounds
            # were still emitted -- a gap no total check could catch, since
            # M0 and A were both present and consistent.
            {"match": r"^(?:k-?value[^%]*%\s*)?(?:Headcount\s*ratio\s*\(H|H\s*\(%\)|Incidence\b)",
             "metric": "incidence_H",
             "columns": [{"metric": "incidence_H"},
                         {"metric": "incidence_H_ci_low"},
                         {"metric": "incidence_H_ci_high"}]},
            {"match": r"^A\s*\(%\)|^Intensity\b", "metric": "intensity_A"},
        ],
    }],
}


parse = make_parser(LAYOUT)
