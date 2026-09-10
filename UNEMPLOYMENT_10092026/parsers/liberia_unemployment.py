"""Liberia — unemployment / labour-force layout and parser.

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
# LIBERIA -- LISGIS, Labour Force Survey 2016-2017.
# "Main labour force and labour underutilization (LU) indicators (%),
#  LBR-LFS 2016-2017 - Main job" (pp. 16-17).
#
# The widest table in the collector: SEVENTEEN columns in seven blocks --
# Sex | Residence | Region | Functional Difficulty | Age | Subsistence Farming
# | Total. Note the printed order puts FUNCTIONAL DIFFICULTY BEFORE AGE, and
# carries a Subsistence-Farming block that is easy to miss entirely.
#
# The caption claims "(%)" but the table is MIXED: the first five rows are
# absolute persons and the rest are percentages.
#
# The ICLS-19 ladder is labelled LU1-LU4 here (Cameroon and Burkina use SU1-SU4
# for the same concepts).
#
# Every count row sums correctly across all seven column blocks to the Total
# column, and LU1 reproduces as Unemployed/Labour force in all 17 columns --
# so a parse can be checked arithmetically rather than by eye.
#
# CROSS-CHECK (Total column): population 15+ 2,355,060; labour force 615,549;
# employed 538,902; unemployed 76,647; LFPR 26.1; EPR 22.9; LU1 12.5;
# LU3 18.0; LU4 27.1; informal employment 86.7.
# =========================================================================
_LR_COLS = [
    {"sex": "male"}, {"sex": "female"},
    {"locality": "urban", "locality_label": "Urban"},
    {"locality": "rural", "locality_label": "Rural"},
    {"geography": "Greater Monrovia"}, {"geography": "North Central"},
    {"geography": "North Western"}, {"geography": "South Central"},
    {"geography": "South Eastern A"}, {"geography": "South Eastern B"},
    {"education": "With functional difficulty"},
    {"education": "Without functional difficulty"},
    {"age_group": "Youth (15-35)"}, {"age_group": "Adult (36+)"},
    {"education": "Participated in subsistence farming"},
    {"education": "Not participated in subsistence farming"},
    {},                                    # Total
]

LAYOUTS["liberia"] = {
    "survey": "Liberia Labour Force Survey 2016-2017",
    "frequency": "ad_hoc",
    "working_age_base": "15+",
    "decimal": ".",
    "period": "2017",
    "reference_period": "2016-2017",
    "tables": [{
        "page_contains": ["main labour force and labour underutilization"],
        "take": "trailing",
        "columns": _LR_COLS,
        "rows": [
            {"match": r"^Population 15 years and older",
             "topic": "working_age_population", "drop_leading": 1,
             "label": "Population 15 years and older"},
            {"match": r"^Labour force\b", "exclude": r"participation",
             "topic": "labour_force", "label": "Labour force"},
            {"match": r"^-?\s*Employed\b", "topic": "employed", "label": "Employed"},
            {"match": r"^-?\s*Unemployed\b", "topic": "unemployed",
             "label": "Unemployed"},
            {"match": r"^Outside the labour force",
             "topic": "outside_labour_force", "label": "Outside the labour force"},
            {"match": r"^Labour force participation rate",
             "topic": "labour_force_participation_rate", "definition": "strict",
             "label": "Labour force participation rate"},
            {"match": r"^Employment-to-population ratio",
             "topic": "employment_to_population_ratio",
             "label": "Employment-to-population ratio"},
            {"match": r"^Time related underemployment rate",
             "topic": "underemployment_rate",
             "label": "Time related underemployment rate"},
            {"match": r"^LU1: Unemployment rate", "topic": "unemployment_rate",
             "definition": "strict", "drop_leading": 1,
             "label": "LU1: Unemployment rate"},
            {"match": r"^LU3: Combined rate of unemployment and potential",
             "topic": "labour_underutilisation_rate", "definition": "broad",
             "drop_leading": 1,
             "label": "LU3: Combined rate of unemployment and potential labour force"},
            {"match": r"^LU4: Composite measure",
             "topic": "labour_underutilisation_rate", "definition": "broad",
             "drop_leading": 1,
             "label": "LU4: Composite measure of labour underutilization"},
            {"match": r"^Persons with informal employment",
             "topic": "informal_employment_share",
             "label": "Persons with informal employment"},
        ],
    }],
}


LAYOUT = LAYOUTS['liberia']
parse = make_parser(LAYOUT)
