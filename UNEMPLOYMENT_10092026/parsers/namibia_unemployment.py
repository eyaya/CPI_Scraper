"""Namibia — unemployment / labour-force layout and parser.

One module per country, as everywhere else in this repo. The layout is
declarative and read by `pdf_key_indicators.make_parser`; the comments beside
it record the report's actual column order and the cross-check values used to
prove the layout still holds.
"""
from __future__ import annotations

import re  # noqa: F401  -- some layouts build their rows with it

from ._vocab import *  # noqa: F401,F403
from .pdf_key_indicators import make_parser

LAYOUTS: dict[str, dict] = {}

# =========================================================================
# NAMIBIA -- NSA, 2023 Population & Housing Census Labour Force Report
# Table 0.1 "Selected Key Indicators of the Labour Market by Urban/Rural and
# Sex" (p. xiii). Columns: Total | Male | Female | Urban | Rural.
# NOTE the residence order is Urban-then-Rural here, the OPPOSITE of Zambia.
#
# MIXED UNITS with no units column: rows 1-7 are absolute persons, rows 8-11
# are percentages, and they look structurally identical. Each row therefore
# declares its own measure via its topic.
#
# The broad measure is CRUPLF -- "Combined Rate of Unemployment and Potential
# Labour Force" -- printed in the table as the bare acronym.
#
# CROSS-CHECK (2023, Total): WAP 15+ 1,876,122; employed 546,805;
# unemployed 320,442; labour force 867,247; potential LF 341,931;
# LFPR 46.2; EPR 29.1; unemployment 36.9; CRUPLF 54.8.
# =========================================================================
LAYOUTS["namibia"] = {
    # This report's renderer wraps long row labels onto their own line, leaving
    # the numbers stranded on the next -- see `_rejoin_wrapped`.
    "join_wrapped_labels": True,
    # It also LETTER-SPACES some cells, so the unemployment rate arrives as
    # "3 6 . 9" and CRUPLF as "5 4 . 8 5 0 . 6 ..." -- eight and fifteen
    # numbers on rows that hold five. See `_despace_numbers`.
    "despace_numbers": True,
    "survey": "Population and Housing Census 2023 -- Labour Force Report",
    "frequency": "ad_hoc",
    "working_age_base": "15+",
    "decimal": ".",
    "period": "2023",
    "reference_period": "Census reference night 24 September 2023",
    "tables": [{
        # ANCHORED ON THE HEADER ROW, NOT THE CAPTION. On the table's own page
        # the caption is rendered with every letter DOUBLED --
        #     TTaabbllee 00..11:: SSeelleecctteedd K Keey yIn Idnidcaictaotros ...
        # -- so a caption match found only the LIST OF TABLES page, and the
        # layout was being run against the contents listing, where of course
        # nothing matched. The header row is printed once and cleanly.
        "page_contains": ["indicators total male female urban rural"],
        "take": "trailing",
        "columns": COLS_TMF_UR,
        "rows": [
            {"match": r"^Working Age Population", "topic": "working_age_population",
             "label": "Working Age Population 15 + years", "drop_leading": 1},
            {"match": r"^Employed\b", "topic": "employed", "label": "Employed"},
            {"match": r"^Unemployed\b", "topic": "unemployed", "label": "Unemployed"},
            {"match": r"^Labour Force\b", "exclude": r"Potential|Extended|Participation",
             "topic": "labour_force", "label": "Labour Force"},
            {"match": r"^Potential Labour Force", "topic": "potential_labour_force",
             "label": "Potential Labour Force"},
            {"match": r"^Labour Force Participation Rate",
             "topic": "labour_force_participation_rate", "definition": "strict",
             "label": "Labour Force Participation Rate"},
            {"match": r"^Employment to Population Ratio",
             "topic": "employment_to_population_ratio",
             "label": "Employment to Population Ratio"},
            {"match": r"^Unemployment Rate", "topic": "unemployment_rate",
             "definition": "strict", "label": "Unemployment Rate"},
            {"match": r"^CRUPLF", "topic": "labour_underutilisation_rate",
             "definition": "broad",
             "label": "CRUPLF (Combined Rate of Unemployment and Potential Labour Force)"},
        ],
    }],
}


LAYOUT = LAYOUTS['namibia']
parse = make_parser(LAYOUT)
