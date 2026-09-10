"""Eswatini — unemployment / labour-force layout and parser.

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
# ESWATINI -- CSO Integrated Labour Force Survey 2023, key findings booklet.
# No combined headline table: the three indicators sit in four separate
# single-topic tables, each `Region | Male | Female | Both Sexes`. The topic
# therefore lives in each table's `defaults`.
#
# Strict = Table 6.7 "Unemployment rate by sex and region" (national 35.4).
# Broad  = Table 6.25 "Combined rates of unemployment and potential labour
#          force" (LU3, national 45.6). Note 6.25 prints "Both sexes" with a
#          lower-case s while 6.7 prints "Both Sexes".
#
# The booklet gives no fieldwork dates, so the period is fixed at 2023.
#
# CROSS-CHECK (All regions): LFPR 54.1 / 48.0 / 50.8; EPR 36.2 / 29.9 / 32.8;
# unemployment 33.1 / 37.6 / 35.4; combined LU3 42.4 / 48.4 / 45.6.
# =========================================================================
_SZ_REGIONS = [
    {"match": r"^Hhohho\b", "geography": "Hhohho"},
    {"match": r"^Manzini\b", "geography": "Manzini"},
    {"match": r"^Shiselweni\b", "geography": "Shiselweni"},
    {"match": r"^Lubombo\b", "geography": "Lubombo"},
    {"match": r"^All regions\b", "geography": "Total country"},
]
_SZ_RESIDENCE = [
    {"match": r"^Urban\b", "locality": "urban", "locality_label": "Urban"},
    {"match": r"^Rural\b", "locality": "rural", "locality_label": "Rural"},
    {"match": r"^All Residence\b", "geography": "Total country"},
]

LAYOUTS["eswatini"] = {
    "survey": "Integrated Labour Force Survey 2023",
    "frequency": "ad_hoc",
    "working_age_base": "15+",
    "decimal": ".",
    "period": "2023",
    "reference_period": "2023",
    "tables": [
        {"page_contains": ["labour force participation rate by sex and regions"],
         "defaults": {"topic": "labour_force_participation_rate",
                      "definition": "strict",
                      "label": "Labour force participation rate"},
         "columns": COLS_MFT, "rows": list(_SZ_REGIONS)},
        {"page_contains": ["employment-to-population ratio"],
         "defaults": {"topic": "employment_to_population_ratio",
                      "label": "Employment-to-population ratio (Absorption Rate)"},
         "columns": COLS_MFT, "rows": _SZ_REGIONS + _SZ_RESIDENCE},
        {"page_contains": ["unemployment rate by sex and region"],
         "defaults": {"topic": "unemployment_rate", "definition": "strict",
                      "label": "Unemployment rate"},
         "columns": COLS_MFT, "rows": list(_SZ_REGIONS)},
        {"page_contains": ["combined rates of unemployment and potential labour force"],
         "defaults": {"topic": "labour_underutilisation_rate", "definition": "broad",
                      "label": "Combined rate of unemployment and potential "
                               "labour force (LU3)"},
         "columns": COLS_MFT, "rows": _SZ_REGIONS + _SZ_RESIDENCE},
    ],
}


LAYOUT = LAYOUTS['eswatini']
parse = make_parser(LAYOUT)
