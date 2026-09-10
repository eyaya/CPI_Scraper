"""Mali — MPI table layout and parser.

One module per country, as everywhere else in this repo. The layout is
declarative and read by `mpi_tables.make_parser`; the comments beside it
record the report's actual column order and the cross-check values used to
prove the layout still holds.
"""
from __future__ import annotations

from ._vocab import _URBAN, _RURAL, _NATIONAL
from .mpi_tables import make_parser

# =========================================================================
# MALI -- INSTAT, "Indice de Pauvreté Multidimensionnelle au Mali" (EMOP 2023).
#
# REWRITTEN against the downloaded PDF. The first version of this layout
# assumed four columns, `Population % | IPM | H | A`. The report actually
# prints TEN numbers per row, because every metric carries a 95% confidence
# interval:
#
#   Part de la population | IPM valeur | IPM CI lo | IPM CI hi
#                         | H valeur   | H CI lo   | H CI hi
#                         | A valeur   | A CI lo   | A CI hi
#
#   Rural  76,3  0,379 0,361 0,396  54,4 52,0 56,8  69,5 69,2 69,9
#
# Reading only the leading four numbers took `IPM CI lo` as H and `IPM CI hi`
# as A, which is why the run failed the M0 range check. The interval bounds
# are skipped rather than stored: the schema's <metric>_ci_low/high metrics
# attach to a row, and a row here is one metric, so there is nowhere to put
# three intervals without inventing a convention.
#
# "Autres villes urbaines" wraps around its own numbers, hence
# `join_wrapped_labels`.
#
# CROSS-CHECK (verbatim from the PDF):
#   National 100,0 | 0,323 (0,310-0,337) | 46,6 (44,7-48,5) | 69,4 (69,0-69,7)
#   Urbain    23,7 | 0,146 | 21,4 | 67,9      Rural 76,3 | 0,379 | 54,4 | 69,5
#   Bamako    12,1 | 0,083 | 12,6 | 65,8      Ménaka 1,1 | 0,767 | 93,4 | 82,1
#   Mopti     13,9 | 0,491 | 69,9 | 70,1
# =========================================================================
# value | CI low | CI high, three times over: IPM, then H, then A.
_ML_COLS = [
    {"skip": True},                                   # part de la population
    {"metric": "index_M0"}, {"skip": True}, {"skip": True},
    {"metric": "incidence_H"}, {"skip": True}, {"skip": True},
    {"metric": "intensity_A"}, {"skip": True}, {"skip": True},
]

LAYOUT = {
    "mpi_type": "national",
    "measure_name": "IPM-Mali",
    "survey": "EMOP 2023 (Enquête Modulaire et Permanente auprès des Ménages)",
    "k_cutoff": 60, "n_dimensions": 5, "n_indicators": 19,
    "unit_of_analysis": "person", "frequency": "ad_hoc", "decimal": ",",
    "period": "2023", "reference_period": "2023",
    "tables": [
        {   # Milieu de résidence
            "page_contains": ["milieu de résidence"],
            "join_wrapped_labels": True,
            "exact_numbers": True,
            "columns": _ML_COLS,
            "rows": [
                {"match": r"^Urbain\b", **_URBAN, "locality_label": "Urbain"},
                {"match": r"^Bamako\b", "geography": "Bamako",
                 "locality": "urban", "locality_label": "Bamako",
                 "topic": "locality"},
                {"match": r"^Autres villes", "locality": "other",
                 "locality_label": "Autres villes urbaines",
                 "topic": "locality"},
                {"match": r"^Rural\b", **_RURAL, "locality_label": "Rural"},
                {"match": r"^National\b", **_NATIONAL},
            ],
        },
        {   # Régions
            "page_contains": ["ménaka"],
            "exact_numbers": True,
            "columns": _ML_COLS,
            "rows": [
                {"match": r"^Kayes\b", "geography": "Kayes"},
                {"match": r"^Koulikoro\b", "geography": "Koulikoro"},
                {"match": r"^Sikasso\b", "geography": "Sikasso"},
                {"match": r"^S[ée]gou\b", "geography": "Ségou"},
                {"match": r"^Mopti\b", "geography": "Mopti"},
                {"match": r"^Tombouctou\b", "geography": "Tombouctou"},
                {"match": r"^Gao\b", "geography": "Gao"},
                {"match": r"^Kidal\b", "geography": "Kidal"},
                {"match": r"^Taoudenn?i\b", "geography": "Taoudenni"},
                {"match": r"^M[ée]naka\b", "geography": "Ménaka"},
                {"match": r"^Bamako\b", "geography": "Bamako"},
                # The region table's own "Mali" line repeats the milieu
                # table's National row exactly, so it is not captured twice.
            ],
        },
    ],
}


parse = make_parser(LAYOUT)
