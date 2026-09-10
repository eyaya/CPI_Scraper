"""Rwanda — unemployment / labour-force layout and parser.

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
# RWANDA -- NISR, Annual Labour Force Survey.
# "Trend of Labour force survey Main indicators (Compare 7 years), Rwanda."
#
# A PERIOD-COLUMN table: rows are indicators, columns are the last seven YEARS.
# Each run therefore re-collects the whole back-series, which is a feature --
# NISR revises earlier years.
#
# WORKING-AGE BASE IS 16+. Data are collected from 14+, but "only persons aged
# 16 years and above are covered for reporting".
#
# MIXED UNITS BY ROW, and the row label is the only cue: most rows are percent,
# one is thousands of jobs, two are hours, four are Rwandan francs. Only the
# percent rows in the topic vocabulary are captured; the francs and hours rows
# have no topic and are deliberately left rather than mislabelled.
#
# Printed typos preserved in the regexes: two rows omit the space before "(%)",
# and the salary row has a DOUBLED closing parenthesis.
#
# NOTE what this report does NOT contain: no unemployment-by-district table and
# no LFPR-by-sex table -- verified against the report's own List of Tables,
# which runs only 4.1 to 4.11. Those breakdowns exist as FIGURES only, and are
# not scraped. The quarterly bulletin is an infographic with no table at all.
#
# CROSS-CHECK (2025 column): unemployment 12.4; LFPR 63.8; EPR 55.9;
# youth unemployment 14.7; time-related underemployment 36.1;
# combined labour underutilisation 56.0; informal employment 91.8.
# =========================================================================
_RW_YEARS = [{"period": str(y)} for y in range(2019, 2026)]

LAYOUTS["rwanda"] = {
    "survey": "Labour Force Survey (annual)",
    "frequency": "annual",
    "working_age_base": "16+",
    "decimal": ".",
    "period": "2025",
    "reference_period": "2019-2025 trend",
    "tables": [{
        "page_contains": ["trend of labour force survey main indicators"],
        "take": "trailing",
        # THREE OF THIS TABLE'S LABELS WRAP AROUND THEIR OWN NUMBERS --
        #     Time related underemployment
        #     26.8 23.7 31.2 31.7 29.4 32.6 36.1
        #     rate(%)
        # -- so time-related underemployment, LU4 and female unemployment were
        # dropped without a word. Everything else on the page fits one line,
        # which is why the loss was invisible: the table still produced a
        # complete-looking seven-year series for five other indicators.
        "join_wrapped_labels": True,
        "columns": _RW_YEARS,
        "rows": [
            {"match": r"^Unemployment rate\s*\(%\)",
             "topic": "unemployment_rate", "definition": "strict",
             "label": "Unemployment rate (%)"},
            {"match": r"^Labour force participation rate\s*\(%\)",
             "topic": "labour_force_participation_rate", "definition": "strict",
             "label": "Labour force participation rate (%)"},
            {"match": r"^Employment to population ratio\s*\(%\)",
             "topic": "employment_to_population_ratio",
             "label": "Employment to population ratio (%)"},
            {"match": r"^Youth unemployment rate\s*\(%\)",
             "topic": "youth_unemployment_rate", "definition": "strict",
             "age_group": "16-30", "label": "Youth unemployment rate (%)"},
            {"match": r"^Time related underemployment rate\s*\(%\)",
             "topic": "underemployment_rate",
             "label": "Time related underemployment rate (%)"},
            {"match": r"^Combined rate of labour underutilization\s*\(%\)",
             "topic": "labour_underutilisation_rate", "definition": "broad",
             "label": "Combined rate of labour underutilization (%)"},
            {"match": r"^Informal employment rate\s*\(%\)",
             "topic": "informal_employment_share",
             "label": "Informal employment rate (%)"},
            {"match": r"^Unemployment rate among females",
             "topic": "unemployment_rate", "definition": "strict", "sex": "female",
             "label": "Unemployment rate among females (%)"},
            {"match": r"^Unemployment rate among males",
             "topic": "unemployment_rate", "definition": "strict", "sex": "male",
             "label": "Unemployment rate among males (%)"},
        ],
    }],
}


LAYOUT = LAYOUTS['rwanda']
parse = make_parser(LAYOUT)
