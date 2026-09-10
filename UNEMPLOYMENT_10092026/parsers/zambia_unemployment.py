"""Zambia — unemployment / labour-force layout and parser.

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
# ZAMBIA -- ZamStats Labour Force Survey 2024 (annual, built from four
# quarterly rounds). "Summary of 2024 Labour Force Survey", front matter.
# Columns: Indicator | Mode of measurement | Total | Male | Female | Rural | Urban
# RURAL PRECEDES URBAN. Re-confirmed on a second read precisely because this is
# the reverse of Namibia and would corrupt two series in silence.
#
# Units are given by an explicit "Mode of measurement" column (Number/Percent),
# which makes this the cleanest of the PDF sources.
#
# Youth is 19-34, Zambia's national definition -- NOT 15-24 or 15-35. The band
# is carried in the row label and in `age_group`.
#
# `take: trailing` throughout because labels embed digits ("15 years or older",
# "(19-34 years)").
#
# CROSS-CHECK (2024, Total): WAP 15+ 11,995,355; labour force 4,560,760;
# employed 3,972,883; unemployed 587,876; LFPR 38.0; EPR 33.1;
# unemployment 12.9; youth 19-34 unemployment 18.4.
# =========================================================================
LAYOUTS["zambia"] = {
    "survey": "Labour Force Survey 2024",
    "frequency": "annual",
    "working_age_base": "15+",
    "decimal": ".",
    "period": "2024",
    "reference_period": "2024",
    "tables": [{
        "page_contains": ["mode of measurement"],
        "take": "trailing",
        "columns": COLS_TMF_RU,
        "rows": [
            {"match": r"^Working-age population", "topic": "working_age_population",
             "label": "Working-age population 15 years or older"},
            {"match": r"^Labour force\b", "exclude": r"participation",
             "topic": "labour_force", "label": "Labour force"},
            {"match": r"^Employed \(market production",
             "topic": "employed", "label": "Employed (market production activities)"},
            {"match": r"^Unemployed population", "exclude": r"Youth",
             "topic": "unemployed", "label": "Unemployed population"},
            {"match": r"^Labour force participation rate",
             "topic": "labour_force_participation_rate", "definition": "strict",
             "label": "Labour force participation rate"},
            {"match": r"^Employment-to-population ratio",
             "topic": "employment_to_population_ratio",
             "label": "Employment-to-population ratio"},
            {"match": r"^Unemployment rate", "exclude": r"Youth",
             "topic": "unemployment_rate", "definition": "strict",
             "label": "Unemployment rate"},
            {"match": r"^Youth \(19-34 years\) unemployment rate",
             "topic": "youth_unemployment_rate", "definition": "strict",
             "age_group": "19-34",
             "label": "Youth (19-34 years) unemployment rate"},
        ],
    }],
}


LAYOUT = LAYOUTS['zambia']
parse = make_parser(LAYOUT)
