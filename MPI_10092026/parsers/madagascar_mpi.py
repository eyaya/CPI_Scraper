"""Madagascar — MPI table layout and parser.

One module per country, as everywhere else in this repo. The layout is
declarative and read by `mpi_tables.make_parser`; the comments beside it
record the report's actual column order and the cross-check values used to
prove the layout still holds.
"""
from __future__ import annotations

from ._vocab import COLS_H_A_M0, _URBAN, _RURAL, _NATIONAL
from .mpi_tables import make_parser

# =========================================================================
# MADAGASCAR -- INSTAT, "Snapshot IPM" (MICS6 2018). A three-page infographic,
# not a report.
#
# REWRITTEN against the downloaded PDF. The earlier layout hunted for a
# headline "IPM" row that does not exist as such; the national figures sit in
# the last line of a proper table instead:
#
#   Caractéristiques géographiques   H (%)   A (%)   IPM
#   Urbain                            50,3    50,9   0,256
#   Ensemble du pays                  70,3    54,9   0,386
#
# The awkward part is that the SAME page also carries a severe-poverty chart
# (deprived in 50% or more of the weighted indicators) whose data labels are
# one number per region -- "Androy 63" directly above "Androy 91,7 59,4 0,545".
# Nothing but the count of numbers on the line separates them, which is what
# `exact_numbers` is for: the severe table takes lines with exactly one number,
# the metric table lines with exactly three.
#
# pdfplumber inserts stray spaces inside several region names as printed
# ("Sofi a", "Men abe", "Haute M atsiatra"), so the row patterns tolerate an
# optional space at those points. This is a rendering artefact of the source
# PDF, not a transcription choice.
#
# CROSS-CHECK (verbatim):
#   Ensemble du pays 70,3 | 54,9 | 0,386     Urbain 50,3 | 50,9 | 0,256
#   Rural            76,6 | 55,7 | 0,427     Androy 91,7 | 59,4 | 0,545
#   Analamanga       44,3 | 50,0 | 0,222     Sava   63,4 | 46,1 | 0,292
#   Severe poverty: Madagascar 39,3; Androy 63; Analamanga 16,1
# =========================================================================
_MG_REGIONS = [
    (r"^Analamanga\b", "Analamanga"),
    (r"^Vakinankaratra\b", "Vakinankaratra"),
    (r"^Itasy\b", "Itasy"),
    (r"^Bongolava\b", "Bongolava"),
    (r"^Haute ?M ?atsiatra\b", "Haute Matsiatra"),
    (r"^Amoron'?i ?mania\b", "Amoron'i Mania"),
    (r"^Vatovavy ?fitovinany\b", "Vatovavy Fitovinany"),
    (r"^Iho ?rombe\b", "Ihorombe"),
    (r"^Atsimo ?atsi ?nanana\b", "Atsimo Atsinanana"),
    (r"^Atsinanana\b", "Atsinanana"),
    (r"^Analanjirofo\b", "Analanjirofo"),
    (r"^Alaotra ?M? ?angoro\b", "Alaotra Mangoro"),
    (r"^Boeny\b", "Boeny"),
    (r"^Sof ?i ?a\b", "Sofia"),
    (r"^Betsiboka\b", "Betsiboka"),
    (r"^M ?elaky\b", "Melaky"),
    (r"^Atsimo ?andrefana\b", "Atsimo Andrefana"),
    (r"^Androy\b", "Androy"),
    (r"^Anosy\b", "Anosy"),
    (r"^Men ?abe\b", "Menabe"),
    (r"^Diana\b", "Diana"),
    (r"^Sava\b", "Sava"),
]

LAYOUT = {
    "mpi_type": "national",
    "measure_name": "IPM Madagascar",
    "survey": "MICS6 2018 (Multiple Indicator Cluster Survey)",
    "k_cutoff": 33.3, "n_dimensions": 3, "n_indicators": 14,
    "unit_of_analysis": "person", "frequency": "ad_hoc", "decimal": ",",
    "period": "2018", "reference_period": "MICS6 2018",
    "tables": [
        {   # H | A | IPM, by milieu and by région
            "page_contains": ["caractéristiques géographiques"],
            "exact_numbers": True,
            "leading_run": True,
            "columns": COLS_H_A_M0,
            "rows": [
                {"match": r"^Urb ?ain\b", **_URBAN, "locality_label": "Urbain"},
                {"match": r"^Rural\b", **_RURAL, "locality_label": "Rural"},
                *[{"match": pat, "geography": name}
                  for pat, name in _MG_REGIONS],
                {"match": r"^Ensemble du pays\b", **_NATIONAL},
            ],
        },
        {   # Extrême pauvreté (50% or more of the weighted indicators)
            "page_contains": ["extrême pauvreté selon la région"],
            "exact_numbers": True,
            "leading_run": True,
            "columns": [{"metric": "severe_poverty"}],
            "rows": [
                *[{"match": pat, "geography": name}
                  for pat, name in _MG_REGIONS],
                {"match": r"^Madagascar\b", **_NATIONAL},
            ],
        },
    ],
}


parse = make_parser(LAYOUT)
