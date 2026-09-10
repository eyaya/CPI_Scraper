"""Somalia — MPI table layout and parser.

One module per country, as everywhere else in this repo. The layout is
declarative and read by `mpi_tables.make_parser`; the comments beside it
record the report's actual column order and the cross-check values used to
prove the layout still holds.
"""
from __future__ import annotations

from ._vocab import COLS_H_A_M0, _URBAN, _RURAL, _NATIONAL
from .mpi_tables import make_parser

# =========================================================================
# SOMALIA -- SNBS/MoLSA, "Multidimensional Poverty Index (MPI) For Somalia
# Report 2024". Columns `Incidence | Intensity | MPI`.
#
# THE NOMADIC STRATUM IS FIRST-CLASS. Somalia reports urban / rural / NOMADIC,
# and the nomadic population is neither urban nor rural -- it maps to locality
# 'other' with its own label rather than being folded into rural.
#
# Middle Juba was not sampled; its absence is a coverage gap in the source.
#
# CROSS-CHECK: National 67.0 / 54.3 / 0.363 (H 95% CI 63.9-70.0);
# Urban 61.7 / 54.3 / 0.335; Rural 74.3 / 57.2 / 0.425;
# Nomadic 81.5 / 48.5 / 0.395; Bakool 97.4 / 68.7 / 0.669;
# Awdal 46.2 / 50.3 / 0.232.
# =========================================================================
LAYOUT = {
    "mpi_type": "national",
    "measure_name": "Somalia MPI",
    "survey": "SIHBS 2022 (Somalia Integrated Household Budget Survey)",
    "k_cutoff": 35, "n_dimensions": 5, "n_indicators": 13,
    "unit_of_analysis": "person", "frequency": "ad_hoc", "decimal": ".",
    "period": "2022", "reference_period": "SIHBS 2022",
    "tables": [{
        "page_contains": ["intensity"],
        "take": "trailing",
        "columns": COLS_H_A_M0,
        "rows": [
            {"match": r"^National\b|^Somalia\b", **_NATIONAL},
            {"match": r"^Urban\b", **_URBAN},
            {"match": r"^Rural\b", **_RURAL},
            {"match": r"^Nomadic\b", "locality": "other",
             "locality_label": "Nomadic", "topic": "locality",
             "characteristic": "Nomadic"},
            {"match": r"^Awdal\b", "geography": "Awdal"},
            {"match": r"^Bakool\b", "geography": "Bakool"},
            {"match": r"^Banadir\b", "geography": "Banadir"},
            {"match": r"^Bari\b", "geography": "Bari"},
            {"match": r"^Bay\b", "geography": "Bay"},
            {"match": r"^Galgaduud\b", "geography": "Galgaduud"},
            {"match": r"^Gedo\b", "geography": "Gedo"},
            {"match": r"^Hiraan\b", "geography": "Hiraan"},
            {"match": r"^Lower Juba\b", "geography": "Lower Juba"},
            {"match": r"^Lower Shabelle\b", "geography": "Lower Shabelle"},
            {"match": r"^Middle Shabelle\b", "geography": "Middle Shabelle"},
            {"match": r"^Mudug\b", "geography": "Mudug"},
            {"match": r"^Nugaal\b", "geography": "Nugaal"},
            {"match": r"^Sanaag\b", "geography": "Sanaag"},
            {"match": r"^Sool\b", "geography": "Sool"},
            {"match": r"^Togdheer\b", "geography": "Togdheer"},
            {"match": r"^Woqooyi Galbeed\b", "geography": "Woqooyi Galbeed"},
        ],
    }],
}


parse = make_parser(LAYOUT)
