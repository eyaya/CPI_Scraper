"""Nigeria — unemployment / labour-force layout and parser.

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
# NIGERIA -- NBS Nigeria Labour Force Survey (NLFS)
# Table "Labour Market Indicators by Sex and Place of Residence" (~p.21).
# Header is two-level: [Total | Urban | Rural] x [Total | Male | Female],
# so nine numeric columns in that order.
#
# WATCH: the rows do NOT share a denominator. "Labour force population",
# "Employed population" and "Outside the labour force population" are shares
# of the WORKING-AGE population (so they are the participation rate and the
# employment-to-population ratio); "Unemployed population" is the unemployment
# rate, a share of the LABOUR FORCE. Verified on the published Q2 2024 figures:
# 79.5 - 76.1 = 3.4, and 3.4 / 79.5 = 4.3.
#
# CROSS-CHECK (Q2 2024, Total column): LFPR 79.5, EPR 76.1, unemployment 4.3,
# time-related underemployment 9.2, informal employment 93.0,
# youth 15-24 unemployment 6.5, NEET 15-24 12.5, LU2 13.0, LU3 5.9, LU4 14.5.
# =========================================================================
LAYOUTS["nigeria"] = {
    "survey": "Nigeria Labour Force Survey (NLFS)",
    "frequency": "quarterly",
    "working_age_base": "15+",
    "decimal": ".",
    "period_patterns": [
        r"(?:for the|the)\s+((?:first|second|third|fourth)\s+quarter\s+of\s+20\d{2})",
        r"\b(Q[1-4]\s*20\d{2})\b",
    ],
    "tables": [{
        "page_contains": ["labour market indicators"],
        "take": "trailing",
        "columns": (_sex_x_locality("all", "Total")
                    + _sex_x_locality("urban", "Urban")
                    + _sex_x_locality("rural", "Rural")),
        "rows": [
            {"match": r"^Labour force population",
             "topic": "labour_force_participation_rate", "definition": "strict",
             "label": "Labour force population"},
            {"match": r"^Employed population", "exclude": r"agricultur",
             "topic": "employment_to_population_ratio",
             "label": "Employed population"},
            {"match": r"^Unemployed population",
             "topic": "unemployment_rate", "definition": "strict",
             "label": "Unemployed population"},
            {"match": r"^Time-related underemployment",
             "topic": "underemployment_rate",
             "label": "Time-related underemployment"},
            {"match": r"^Informal employment", "exclude": r"excluding",
             "topic": "informal_employment_share", "label": "Informal employment"},
            {"match": r"^Young unemployed", "topic": "youth_unemployment_rate",
             "definition": "strict", "age_group": "15-24",
             "label": "Young unemployed (aged 15-24)", "drop_leading": 2},
            {"match": r"^NEET \(aged", "topic": "neet_rate", "age_group": "15-24",
             "label": "NEET (aged 15-24)", "drop_leading": 2},
            {"match": r"^LU2\b", "topic": "labour_underutilisation_rate",
             "definition": "broad", "label": "LU2", "drop_leading": 1},
            {"match": r"^LU3\b", "topic": "labour_underutilisation_rate",
             "definition": "broad", "label": "LU3", "drop_leading": 1},
            {"match": r"^LU4\b", "topic": "labour_underutilisation_rate",
             "definition": "broad", "label": "LU4", "drop_leading": 1},
        ],
    }],
}


LAYOUT = LAYOUTS['nigeria']
parse = make_parser(LAYOUT)
