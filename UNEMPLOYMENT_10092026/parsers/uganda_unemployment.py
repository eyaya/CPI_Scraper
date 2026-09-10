"""Uganda — unemployment / labour-force layout and parser.

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
# UGANDA -- UBOS, Labour Market Survey 2025. Slides 56 and 57,
# "Summary Labour Indicators - Household".
#
# SMALL BUT IMPORTANT. Each slide carries only two indicator rows, but between
# them they capture the trap that makes Uganda worth collecting carefully:
# UBOS publishes the SAME indicators on TWO WORKING-AGE DEFINITIONS side by
# side -- the ILO 15+ and the National Employment Policy 2011's 14-64 -- with
# two matching youth bands, 15-24 and 18-30. Unemployment reads 12.2% on one
# base and 12.4% on the other; youth unemployment 17.9% against 16.2%.
# Reporting either without its base is wrong.
#
# The rest of the deck's indicators are BAR CHARTS, not tables, and are not
# scraped -- see the README's "what this collector will not do".
#
# CROSS-CHECK: ILO 15+ unemployment 12.2, youth 15-24 17.9; informal employment
# excl. agriculture 87.6 and 95.1. National 14-64 unemployment 12.4, youth
# 18-30 16.2; informal 87.6 and 91.5.
# =========================================================================
_UG_ROWS = [
    {"match": r"^Unemployment rate", "topic": "unemployment_rate",
     "definition": "strict", "label": "Unemployment rate"},
    {"match": r"^Informal employment \(excluding agriculture",
     "topic": "informal_employment_share",
     "label": "Informal employment (excluding agriculture, forestry and fishing)"},
]

LAYOUTS["uganda"] = {
    # This report's renderer wraps long row labels onto their own line, leaving
    # the numbers stranded on the next -- see `_rejoin_wrapped`.
    "join_wrapped_labels": True,
    "survey": "Labour Market Survey 2025",
    "frequency": "ad_hoc",
    "working_age_base": "15+",
    "decimal": ".",
    "period": "2025",
    "reference_period": "2025",
    # THE SLIDE HEADINGS ARE LETTER-SPACED, one character at a time:
    #     I n t e r n a t i o n a l  C l a s s i f i c a t i o n
    #     N a t i o n a l  C l a s s i f i c a t i o n
    # so neither page anchor ever matched and both slides were skipped. (The
    # second is also a SUFFIX of the first, which would have selected both
    # pages for the national table even if the spacing were fixed.)
    #
    # The age-band labels are rendered normally and are unique to their slide,
    # so they identify the two classifications unambiguously: 15+/15-24 is the
    # ILO basis, 14-64/18-30 is Uganda's National Employment Policy basis.
    "tables": [
        {"page_contains": ["15-24 years"],
         "take": "trailing",
         "columns": [{"age_group": "Total"},
                     {"age_group": "15-24", "topic": "youth_unemployment_rate"}],
         "rows": list(_UG_ROWS)},
        {"page_contains": ["14-64 years"],
         "take": "trailing",
         "defaults": {"working_age_base": "14-64"},
         "columns": [{"age_group": "Total"},
                     {"age_group": "18-30", "topic": "youth_unemployment_rate"}],
         "rows": list(_UG_ROWS)},
    ],
}


LAYOUT = LAYOUTS['uganda']
parse = make_parser(LAYOUT)
