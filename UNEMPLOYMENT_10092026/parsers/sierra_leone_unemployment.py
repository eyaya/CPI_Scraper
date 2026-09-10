"""Sierra Leone — unemployment / labour-force layout and parser.

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
# SIERRA LEONE -- Stats SL Labour Force Survey 2014
# Table 1 "Key Aggregate Labor Market Statistics" (US spelling as printed).
# TRANSPOSED relative to every other report here: the ROWS are population
# groups and the COLUMNS are indicators, so the topics live in the columns.
#
# Two columns are deliberately skipped: "Unemployed (ILO)" and "Unemployed
# (Broad)" are expressed as shares of the WORKING-AGE population, not of the
# labour force, so neither is an unemployment rate and neither has an honest
# home in the topic vocabulary. They are held as skip placeholders so the
# positional map stays true.
#
# Base is 15-64 -- the only closed-upper-bound base in the whole collector.
#
# CROSS-CHECK (Overall): EPR 62.2, WAP 3,009,472, labour force 1,956,912,
# LFPR 65.0, unemployment 4.3. Identity: 62.2 + 2.8 = 65.0 and 2.8/65.0 = 4.3.
# =========================================================================
LAYOUTS["sierra_leone"] = {
    "survey": "Sierra Leone Labour Force Survey 2014",
    "frequency": "ad_hoc",
    "working_age_base": "15-64",
    "decimal": ".",
    "period": "2014",
    "reference_period": "July-August 2014",
    "tables": [{
        "page_contains": ["key aggregate labor market statistics"],
        "take": "trailing",
        "columns": [
            {"topic": "employment_to_population_ratio", "label": "Employed"},
            {"skip": True},          # Unemployed (ILO), % of working-age pop
            {"skip": True},          # Unemployed (Broad), % of working-age pop
            {"topic": "working_age_population", "label": "Working Age Population"},
            {"topic": "labour_force", "label": "Workforce (ILO Definition)"},
            {"topic": "labour_force_participation_rate", "definition": "strict",
             "label": "Labor Force Participation (ILO)"},
            {"topic": "unemployment_rate", "definition": "strict",
             "label": "Unemployment Rate (ILO)"},
        ],
        "rows": [
            {"match": r"^Overall\b", **_TOTAL},
            {"match": r"^Men\b", **_MALE},
            {"match": r"^Women\b", **_FEMALE},
            {"match": r"^Youth \(AFR\)", "age_group": "Youth (AFR)"},
            {"match": r"^Urban Freetown", "locality": "urban",
             "locality_label": "Urban Freetown", "geography": "Freetown"},
            {"match": r"^Other Urban", "locality": "other",
             "locality_label": "Other Urban"},
            {"match": r"^Rural\b", "locality": "rural", "locality_label": "Rural"},
            {"match": r"^Eastern\b", "geography": "Eastern"},
            {"match": r"^Northern\b", "geography": "Northern"},
            {"match": r"^Southern\b", "geography": "Southern"},
            {"match": r"^Western Area\b", "geography": "Western Area"},
        ],
    }],
}


LAYOUT = LAYOUTS['sierra_leone']
parse = make_parser(LAYOUT)
