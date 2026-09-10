"""Zimbabwe — unemployment / labour-force layout and parser.

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
# ZIMBABWE -- ZIMSTAT Quarterly Labour Force Survey. "Table 1: Key findings".
# Header is `Indicator | <quarter> {Number | Percent}` and MANY CELLS ARE
# DELIBERATELY BLANK -- a rate row has no Number, a stock row has no Percent.
# So the column set varies by block, which is exactly what block-level
# `columns` overrides exist for.
#
# Working-age base is 16+, not 15+ ("Working Age Population refers to persons
# aged 16 and above").
#
# The report states NO fieldwork dates anywhere -- preface, methodology and
# executive summary were all checked. The period therefore comes from the
# column header, matched by `period_patterns`.
#
# CROSS-CHECK (Q2 2025): WAP 16+ 8,539,402; labour force 4,020,125;
# employed 3,186,598; LFPR 47.1; EPR 37.3; unemployment 833,527 / 20.7;
# expanded unemployment 37.1; youth 15-24 39.3 (expanded 58.2);
# youth 15-35 28.9 (expanded 46.1); NEET 15-24 47.6; NEET 15-35 49.2.
# =========================================================================
_ZW_COUNT = [{"measure": "count", "unit": "persons"}]
_ZW_RATE = [{"measure": "rate", "unit": "percent"}]
_ZW_COUNT_RATE = [{"measure": "count", "unit": "persons"},
                  {"measure": "rate", "unit": "percent"}]

LAYOUTS["zimbabwe"] = {
    "survey": "Quarterly Labour Force Survey (QLFS)",
    "frequency": "quarterly",
    "working_age_base": "16+",
    "decimal": ".",
    "period_patterns": [
        r"\b((?:1st|2nd|3rd|4th|First|Second|Third|Fourth)\s+Quarter\s+20\d{2})\b",
        r"\b(20\d{2}\s+(?:FIRST|SECOND|THIRD|FOURTH)\s+QUARTER)\b",
    ],
    "tables": [{
        "page_contains": ["key findings"],
        "take": "trailing",
        "columns": _ZW_COUNT,
        "blocks": [
            {"id": "strict", "match": r"^Unemployment\s*$", "columns": _ZW_COUNT_RATE,
             "definition": "strict"},
            {"id": "broad", "match": r"Expanded/Relaxed Unemployment",
             "columns": _ZW_RATE, "definition": "broad"},
            {"id": "neet", "match": r"Not in Employment, Education or Training",
             "columns": _ZW_COUNT_RATE},
        ],
        "rows": [
            {"match": r"^Working Age Population", "topic": "working_age_population",
             "columns": _ZW_COUNT, "label": "Working Age Population (16 years and above)",
             "drop_leading": 1},
            {"match": r"^Labour Force \(16 years", "topic": "labour_force",
             "columns": _ZW_COUNT, "label": "Labour Force (16 years and above)",
             "drop_leading": 1},
            {"match": r"^Labour Force Participation Rate",
             "topic": "labour_force_participation_rate", "definition": "strict",
             "columns": _ZW_RATE, "label": "Labour Force Participation Rate (LFPR)"},
            {"match": r"^Total Employed", "topic": "employed",
             "columns": _ZW_COUNT, "label": "Total Employed"},
            {"match": r"^Employment to Population Ratio",
             "topic": "employment_to_population_ratio", "columns": _ZW_RATE,
             "label": "Employment to Population Ratio (EPR)"},
            # Strict block
            {"match": r"^National \(16 years", "block": "strict",
             "topic": "unemployment_rate", "definition": "strict",
             "columns": _ZW_COUNT_RATE, "drop_leading": 1,
             "label": "National (16 years and above)"},
            {"match": r"^Youth \(15-24 years\)", "block": "strict",
             "topic": "youth_unemployment_rate", "definition": "strict",
             "age_group": "15-24", "columns": _ZW_COUNT_RATE, "drop_leading": 2,
             "label": "Youth (15-24 years)"},
            {"match": r"^Youth \(15-35 years\)", "block": "strict",
             "topic": "youth_unemployment_rate", "definition": "strict",
             "age_group": "15-35", "columns": _ZW_COUNT_RATE, "drop_leading": 2,
             "label": "Youth (15-35 years)"},
            # Expanded / relaxed block -- percent only
            {"match": r"^National \(16 years", "block": "broad",
             "topic": "unemployment_rate", "definition": "broad",
             "columns": _ZW_RATE, "drop_leading": 1,
             "label": "National (16 years and above), expanded/relaxed"},
            {"match": r"^Youth \(15-24 years\)", "block": "broad",
             "topic": "youth_unemployment_rate", "definition": "broad",
             "age_group": "15-24", "columns": _ZW_RATE, "drop_leading": 2,
             "label": "Youth (15-24 years), expanded/relaxed"},
            {"match": r"^Youth \(15-35 years\)", "block": "broad",
             "topic": "youth_unemployment_rate", "definition": "broad",
             "age_group": "15-35", "columns": _ZW_RATE, "drop_leading": 2,
             "label": "Youth (15-35 years), expanded/relaxed"},
            # NEET block
            {"match": r"^Youth \(15-24 years\) NEET", "block": "neet",
             "topic": "neet_rate", "age_group": "15-24",
             "columns": _ZW_COUNT_RATE, "drop_leading": 2,
             "label": "Youth (15-24 years) NEET"},
            {"match": r"^Youth \(15-35 years\) NEET", "block": "neet",
             "topic": "neet_rate", "age_group": "15-35",
             "columns": _ZW_COUNT_RATE, "drop_leading": 2,
             "label": "Youth (15-35 years) NEET"},
        ],
    }],
}


LAYOUT = LAYOUTS['zimbabwe']
parse = make_parser(LAYOUT)
