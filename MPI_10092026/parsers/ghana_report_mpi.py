"""Ghana Report — MPI table layout and parser.

One module per country, as everywhere else in this repo. The layout is
declarative and read by `mpi_tables.make_parser`; the comments beside it
record the report's actual column order and the cross-check values used to
prove the layout still holds.
"""
from __future__ import annotations

from .mpi_tables import make_parser

# =========================================================================
# GHANA (report edition) -- GSS, "Ghana's Multidimensional Poverty Index".
# Columns `Value | 95% CI lower | 95% CI upper`, rows are the metrics.
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
# CROSS-CHECK: MPI 0.236 (0.224-0.248); H 45.6 (43.7-47.5); A 51.7 (51.0-52.5).
# =========================================================================
LAYOUT = {
    "mpi_type": "national",
    "measure_name": "Ghana MPI (GLSS7/MICS)",
    "survey": "GLSS7 2016/2017 with MICS 2011 and 2017/2018",
    "k_cutoff": 33, "n_dimensions": 3, "n_indicators": 12,
    "unit_of_analysis": "person", "frequency": "ad_hoc", "decimal": ".",
    "period": "2017", "reference_period": "GLSS7 2016/2017",
    "tables": [{
        "page_contains": ["confidence"],
        "take": "leading",
        # Bounds name the estimate they bracket -- see schema.METRICS and the
        # note in seychelles_mpi.py, which has the same three-row shape.
        "columns": [{}, {"metric": "intensity_A_ci_low"},
                    {"metric": "intensity_A_ci_high"}],
        "rows": [
            {"match": r"^MPI\b", "metric": "index_M0",
             "columns": [{"metric": "index_M0"},
                         {"metric": "index_M0_ci_low", "unit": "index"},
                         {"metric": "index_M0_ci_high", "unit": "index"}]},
            {"match": r"^Incidence\b", "metric": "incidence_H",
             "columns": [{"metric": "incidence_H"},
                         {"metric": "incidence_H_ci_low"},
                         {"metric": "incidence_H_ci_high"}]},
            {"match": r"^Intensity\b", "metric": "intensity_A"},
        ],
    }],
}


parse = make_parser(LAYOUT)
