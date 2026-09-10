"""Ethiopia — unemployment / labour-force layout and parser.

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
# ETHIOPIA -- ESS, Labour Force and Migration Survey 2021.
# Summary Table 1A: rows are Region x Sex, columns are three indicators x four
# survey periods (Mar-99, Mar-05, Jun-13, Feb-21) = twelve numeric columns.
# Only the CURRENT period (Feb-21) is captured from each indicator block.
#
# WORKING-AGE BASE IS 10+, not 15+ -- confirmed by ST3's own caption,
# "(Age 10 years and above)". Ethiopian rates are not comparable with a 15+
# series without saying so, and the base travels on every row.
#
# TWO BLANK PATTERNS the parser must survive, and they sit at opposite ends of
# a row: TIGRAY is excluded from the 2021 round (its Feb-21 cells are blank at
# the row TAIL), and SIDAMA did not exist as a region before 2020 (its 1999,
# 2005 and 2013 cells are blank at the row HEAD). Reading from the end of the
# line handles Sidama; Tigray simply produces too few numbers and is skipped
# rather than misaligned -- which is the correct outcome, since Tigray has no
# 2021 estimate to report.
#
# Printed typos preserved: ST3's caption reads "Economically Activity Persons".
#
# CROSS-CHECK (Country Total, Feb-21): LFPR 64.7 (M 72.6 / F 56.8);
# EPR 59.5 (M 69.0 / F 50.2); unemployment 8.0 (M 5.0 / F 11.7).
# Addis Ababa unemployment 22.1; Dire Dawa 15.9; Sidama 5.5.
# ST3 country total: economically active 45,245,760; employed 41,637,071;
# unemployed 3,608,688; urban unemployment 17.9; rural 5.2.
# =========================================================================
_ET_CURRENT = [{"skip": True}] * 3 + [{}]      # keep only the 4th (Feb-2021)

_ET_REGIONS = [
    {"match": r"^Country[- ]?Total", "geography": "Total country"},
    {"match": r"^Afar\b", "geography": "Afar"},
    {"match": r"^Amhara\b", "geography": "Amhara"},
    {"match": r"^Oromia\b", "geography": "Oromia"},
    {"match": r"^Somali\b", "geography": "Somali"},
    {"match": r"^Benishangul", "geography": "Benishangul-Gumuz"},
    {"match": r"^SNNP\b", "geography": "SNNP"},
    {"match": r"^Sidama\b", "geography": "Sidama"},
    {"match": r"^Gambella\b", "geography": "Gambella"},
    {"match": r"^Harari\b", "geography": "Harari"},
    {"match": r"^Addis Ababa", "geography": "Addis Ababa"},
    {"match": r"^Dire Dawa", "geography": "Dire Dawa"},
]

LAYOUTS["ethiopia"] = {
    "survey": "Labour Force and Migration Survey (LMS)",
    "frequency": "ad_hoc",
    "working_age_base": "10+",
    "decimal": ".",
    "period": "2021",
    "reference_period": "February 2021",
    "tables": [{
        # Summary Table 3: economically active / employed / unemployed counts
        # plus the unemployment rate, by region and by urban/rural.
        "page_contains": ["economically activity persons of regions"],
        "take": "trailing",
        "columns": [
            {"topic": "labour_force", "sex": "total"},
            {"topic": "labour_force", "sex": "male"},
            {"topic": "labour_force", "sex": "female"},
            {"topic": "employed", "sex": "total"},
            {"topic": "employed", "sex": "male"},
            {"topic": "employed", "sex": "female"},
            {"topic": "unemployed", "sex": "total"},
            {"topic": "unemployed", "sex": "male"},
            {"topic": "unemployed", "sex": "female"},
            {"topic": "unemployment_rate", "definition": "strict", "sex": "total"},
            {"topic": "unemployment_rate", "definition": "strict", "sex": "male"},
            {"topic": "unemployment_rate", "definition": "strict", "sex": "female"},
        ],
        "defaults": {"label": "Economically active / employed / unemployed"},
        "rows": _ET_REGIONS + [
            {"match": r"^Urban\b", "locality": "urban", "locality_label": "Urban"},
            {"match": r"^Rural\b", "locality": "rural", "locality_label": "Rural"},
        ],
    }],
}


LAYOUT = LAYOUTS['ethiopia']
parse = make_parser(LAYOUT)
