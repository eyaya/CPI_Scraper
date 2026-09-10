"""Burkina Faso — MPI table layout and parser.

One module per country, as everywhere else in this repo. The layout is
declarative and read by `mpi_tables.make_parser`; the comments beside it
record the report's actual column order and the cross-check values used to
prove the layout still holds.
"""
from __future__ import annotations

from .mpi_tables import make_parser

# =========================================================================
# BURKINA FASO -- INSD, "La pauvreté multidimensionnelle au niveau local en
# 2019" (RGPH 2019).
#
# REWRITTEN against the downloaded PDF. There is exactly ONE table of results
# in the report and it is province-level; there is no national row, no
# urban/rural split and no sex breakdown -- the profile section is charts only.
# Each row is printed as REGION then PROVINCE then the three metrics:
#
#   Centre            Kadiogo   10,11  44,01  0,04
#   Boucle Du Mouhoun Mouhoun   37,75  45,95  0,17
#
# so a row spec anchored on the province name would never match. The 45 rows
# are picked up by `row_scan`, whose label regex takes the LAST word before the
# numbers -- every Burkinabè province name is a single word, and the region
# prefix is discarded. `expect_rows: 40` is the guard: if INSD reformats the
# table, the scan fails loudly instead of shipping a handful of rows.
#
# The index is printed to only two decimals (0,04 for Kadiogo), which is the
# published precision and is not padded here.
#
# CROSS-CHECK (verbatim):
#   Kadiogo 10,11 | 44,01 | 0,04     Houet    20,62 | 44,47 | 0,09
#   Tapoa   66,22 | 47,57 | 0,32     Yagha    63,35 | 46,92 | 0,30
#   Zondoma 60,68 | 47,26 | 0,29     Soum     46,14 | 45,19 | 0,21
#   Communes range from Ouagadougou 8,37% to Botou 78,32% incidence (text only).
# =========================================================================
LAYOUT = {
    "mpi_type": "national",
    "measure_name": "IPM local (Burkina Faso)",
    "survey": "RGPH 2019 (5e Recensement Général de la Population et de l'Habitation)",
    "k_cutoff": 38, "n_dimensions": 5, "n_indicators": 21,
    "unit_of_analysis": "person", "frequency": "ad_hoc", "decimal": ",",
    "period": "2019", "reference_period": "RGPH 2019",
    "tables": [{
        "page_contains": ["indice de", "pauvreté multi"],
        "exact_numbers": True,
        "columns": [
            {"metric": "incidence_H"},
            {"metric": "intensity_A"},
            {"metric": "index_M0"},
        ],
        "row_scan": {
            # The province is the last word before the first number; the
            # administrative region printed ahead of it is dropped.
            "label": r"^.*\s([A-Za-zÀ-ÿ'’\-]{3,})\s+(?=\d)",
            "label_ok": r"^[A-Za-zÀ-ÿ][A-Za-zÀ-ÿ'’\-]+$",
            "expect_rows": 40,
        },
    }],
}


parse = make_parser(LAYOUT)
