"""Egypt — MPI table layout and parser.

One module per country, as everywhere else in this repo. The layout is
declarative and read by `mpi_tables.make_parser`; the comments beside it
record the report's actual column order and the cross-check values used to
prove the layout still holds.
"""
from __future__ import annotations

from ._vocab import COLS_M0_H_A, _URBAN, _RURAL, _NATIONAL
from .mpi_tables import make_parser

# =========================================================================
# EGYPT -- CAPMAS (co-publisher with ESCWA and the ministries),
# "Multidimensional poverty in Egypt: An in-depth analysis".
#
# COLUMN ORDER IS `MPI | H (%) | A (%) | Population share (%)` -- the index
# FIRST, unlike almost every other report here. The population-share column is
# skipped as a weight, not a poverty metric.
#
# SEVEN DIMENSIONS, the most of any national MPI collected: Education, Health,
# Housing, Services, Employment, Social Protection, Food Security. k = 2/7 = 29%.
#
# CAPMAS is a co-author rather than the lead publisher, and the file sits on the
# censusinfo NADA host rather than the main SPA -- both recorded in the
# descriptor so the provenance is never overstated.
#
# CROSS-CHECK: National 0.077 / 21.2 / 36.5; Urban 0.042 / 11.9 / 35.1;
# Rural 0.103 / 28.0 / 36.9; Male-headed 0.079 / 21.8 / 36.5;
# Female-headed 0.064 / 17.7 / 36.4. National CIs: H 20.2-22.3; A 36.2-36.8;
# MPI 0.073-0.082. Dimension contributions: Services 19.3%, Employment 18.9%.
# =========================================================================
LAYOUT = {
    "mpi_type": "national",
    "measure_name": "Egypt National MPI",
    "survey": "HIECS 2021/2022 (Household Income, Expenditure and Consumption Survey)",
    "k_cutoff": 29, "n_dimensions": 7, "n_indicators": 19,
    "unit_of_analysis": "person", "frequency": "ad_hoc", "decimal": ".",
    "period": "2022", "reference_period": "HIECS 2021/2022",
    "tables": [{
        "page_contains": ["mpi"],
        "take": "leading",
        "columns": COLS_M0_H_A + [{"skip": True}],   # population share
        "rows": [
            {"match": r"^National\b|^Total\b|^Egypt\b", **_NATIONAL},
            {"match": r"^Urban\b", **_URBAN},
            {"match": r"^Rural\b", **_RURAL},
            {"match": r"^Male[- ]headed", "sex": "male", "topic": "sex_of_head",
             "characteristic": "Male-headed"},
            {"match": r"^Female[- ]headed", "sex": "female", "topic": "sex_of_head",
             "characteristic": "Female-headed"},
        ],
    }],
}


parse = make_parser(LAYOUT)
