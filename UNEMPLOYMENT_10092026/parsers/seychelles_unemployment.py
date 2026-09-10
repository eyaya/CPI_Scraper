"""Seychelles — unemployment / labour-force layout and parser.

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
# SEYCHELLES -- NBS Labour Force Survey Bulletin, quarterly.
# Table 1A "Distribution of key populations by sex for selected key
# indicators". Two-tier header: [prev quarter | current quarter] x
# [Male | Female | Both Sexes] = six numeric columns.
#
# Only the RATES block is captured. The block above the "RATES (%)" divider
# holds sex SHARES that sum to 100 -- they are distributions, not levels, and
# reading them as populations would be badly wrong.
#
# Every indicator has two indented sub-rows, `National (15 years and above)`
# and `Youth (15 to 24)`, so the age band comes from the row, not the column.
#
# CROSS-CHECK (Q1 2026): unemployment 3.5 / 3.2 / 3.3; youth 14.1 / 11.7 / 12.8;
# LFPR 69.8 / 66.1 / 67.8; EPR 67.4 / 64.0 / 65.6; NEET youth 24.5 / 18.5 / 21.4.
# Identity: EPR = LFPR x (1 - unemployment rate) holds on every headline cell.
# =========================================================================
_SC_COLS = [{"skip": True}, {"skip": True}, {"skip": True}] + COLS_MFT

LAYOUTS["seychelles"] = {
    "survey": "Labour Force Survey Bulletin",
    "frequency": "quarterly",
    "working_age_base": "15+",
    "decimal": ".",
    "period_patterns": [
        r"for the\s+((?:first|second|third|fourth)\s+quarter\s+of\s+20\d{2})",
        r"Labour Force Survey\s+(20\d{2}/Q[1-4])",
    ],
    "tables": [{
        "page_contains": ["rates (%)"],
        "take": "trailing",
        "columns": _SC_COLS,
        "blocks": [
            {"id": "unemp", "match": r"^Unemployment rate\s*$",
             "topic": "unemployment_rate", "definition": "strict",
             "label": "Unemployment rate"},
            {"id": "lfpr", "match": r"^Labour Force Participation Rate\s*$",
             "topic": "labour_force_participation_rate", "definition": "strict",
             "label": "Labour Force Participation Rate"},
            {"id": "epr", "match": r"^Employment-to-Population Ratio",
             "topic": "employment_to_population_ratio",
             "label": "Employment-to-Population Ratio (Employment Rate)"},
            {"id": "informal", "match": r"^Informal employment rate",
             "topic": "informal_employment_share", "label": "Informal employment rate"},
            {"id": "neet", "match": r"education,? (?:or|and) training \(NEET\) rate",
             "topic": "neet_rate", "label": "NEET rate"},
        ],
        "rows": [
            {"match": r"^National \(15 years and above\)", "block": "unemp",
             "drop_leading": 1},
            {"match": r"^Youth \(15 to 24\)", "block": "unemp",
             "topic": "youth_unemployment_rate", "age_group": "15-24",
             "drop_leading": 2},
            {"match": r"^National \(15 years and above\)", "block": "lfpr",
             "drop_leading": 1},
            {"match": r"^Youth \(15 to 24\)", "block": "lfpr",
             "age_group": "15-24", "drop_leading": 2},
            {"match": r"^National \(15 years and above\)", "block": "epr",
             "drop_leading": 1},
            {"match": r"^Youth \(15 to 24\)", "block": "epr",
             "age_group": "15-24", "drop_leading": 2},
            {"match": r"^National \(15 years and above\)", "block": "informal",
             "drop_leading": 1},
            {"match": r"^Youth \(15 to 24\)", "block": "neet",
             "age_group": "15-24", "drop_leading": 2},
        ],
    }],
}


LAYOUT = LAYOUTS['seychelles']
parse = make_parser(LAYOUT)
