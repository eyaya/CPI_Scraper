"""Somalia — unemployment / labour-force layout and parser.

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
# SOMALIA -- SNBS Somali Labour Force Survey 2019
# Table 1.1 "Key Labour force Indicators" (lower-case "force" is as printed).
# Columns: Total | Male | Female | Urban | Rural. MIXED UNITS: the first block
# of rows is absolute persons, the second is percentages -- the only cue is
# the row label, so each row carries its own measure/unit.
#
# Coverage caveat recorded in the descriptor: the survey excludes the nomadic
# /pastoralist population and non-liberated areas.
#
# CROSS-CHECK (2019, Total): WAP 15+ 3,751,264; labour force 1,215,472;
# employed 955,820; unemployed 259,652; LFPR 32.4; EPR 25.5;
# unemployment 21.4; youth 15-24 37.4; NEET 44.2; LU3 34.8.
# =========================================================================
LAYOUTS["somalia"] = {
    "survey": "Somali Labour Force Survey 2019",
    "frequency": "ad_hoc",
    "working_age_base": "15+",
    "decimal": ".",
    "period": "2019",
    "reference_period": "2019",
    "tables": [{
        "page_contains": ["key labour force indicators"],
        "take": "trailing",
        "columns": COLS_TMF_UR,
        "rows": [
            {"match": r"^Population 15 years old and over",
             "topic": "working_age_population", "drop_leading": 1,
             "label": "Population 15 years old and over"},
            {"match": r"^In Labour force", "topic": "labour_force",
             "label": "In Labour force"},
            {"match": r"^Employed\b", "topic": "employed", "label": "Employed"},
            {"match": r"^Unemployed\b", "topic": "unemployed", "label": "Unemployed"},
            {"match": r"^Outside labour force\b", "exclude": r"%",
             "topic": "outside_labour_force", "label": "Outside labour force"},
            {"match": r"^Potential labour force", "topic": "potential_labour_force",
             "label": "Potential labour force"},
            {"match": r"^Labour force participation rate",
             "topic": "labour_force_participation_rate", "definition": "strict",
             "label": "Labour force participation rate"},
            {"match": r"^Employment-to-population ratio",
             "topic": "employment_to_population_ratio",
             "label": "Employment-to-population ratio"},
            {"match": r"^Unemployment rate \(15 and over\)",
             "topic": "unemployment_rate", "definition": "strict",
             "label": "Unemployment rate (15 and over)", "drop_leading": 1},
            {"match": r"^Youth \(15 to 24 years\) unemployment",
             "topic": "youth_unemployment_rate", "definition": "strict",
             "age_group": "15-24", "drop_leading": 2,
             "label": "Youth (15 to 24 years) unemployment"},
            {"match": r"^LU3 rate", "topic": "labour_underutilisation_rate",
             "definition": "broad", "label": "LU3 rate", "drop_leading": 1},
            {"match": r"^LU4 rate", "topic": "labour_underutilisation_rate",
             "definition": "broad", "label": "LU4 rate", "drop_leading": 1},
            {"match": r"^NEET rate", "topic": "neet_rate", "age_group": "15-24",
             "label": "NEET rate"},
        ],
    }],
}


LAYOUT = LAYOUTS['somalia']
parse = make_parser(LAYOUT)
