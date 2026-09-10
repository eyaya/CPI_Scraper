"""Tanzania — unemployment / labour-force layout and parser.

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
# TANZANIA -- NBS Integrated Labour Force Survey (ILFS), now annual.
# Three single-topic tables (3.1 LFPR, 3.2 EPR, 4.1 unemployment), each with a
# THREE-LEVEL header: year (prev | curr) x area (TZM | ZNZ | URT) x sex
# (M | F | T) = eighteen numeric columns. Only the CURRENT year's nine are
# captured; the previous year is a restatement the prior run already holds.
#
# TZM = Tanzania Mainland, ZNZ = Zanzibar, URT = United Republic of Tanzania.
#
# CROSS-CHECK (ILFS 2025, URT Total): LFPR 75.9; EPR 71.4; unemployment 5.9.
# Identity: (75.9 - 71.4) / 75.9 = 5.9 ✓. Dar es Salaam unemployment 9.3.
# =========================================================================
def _tz_block(period: str) -> list[dict]:
    """One year's nine columns: area (TZM | ZNZ | URT) x sex (M | F | T)."""
    return [{"geography": g, "sex": s, "period": period,
             "reference_period": f"ILFS {period}"}
            for g in ("Tanzania Mainland", "Zanzibar", "Total country")
            for s in ("male", "female", "total")]


# BOTH YEARS ARE CAPTURED, EACH CARRYING ITS OWN PERIOD ON THE COLUMN.
#
# This was nine `skip`s followed by the current year, on the reasoning that the
# previous year is "a restatement the prior run already holds". It is not: this
# indicator has no `merge_keys`, so nothing holds anything between runs -- and
# more seriously, the period came from `period_patterns` scanning the page
# text, which matched the "ILFS 2024" mentioned in Table 2.1's caption. So the
# 2025 values were emitted, correctly read, and every one of them labelled
# 2024. The URT total unemployment rate went out as 5.9 for 2024, when 2024's
# printed value is 6.2 and 5.9 is 2025's.
#
# Reading a year off the running text is what made that possible, so the year
# now comes from the COLUMN's position in the header, which is what actually
# determines it.
_TZ_COLS = _tz_block("2024") + _tz_block("2025")

_TZ_ROWS = [
    {"match": r"^Rural\b", "locality": "rural", "locality_label": "Rural"},
    {"match": r"^Urban\b", "locality": "urban", "locality_label": "Urban"},
    {"match": r"^DSM\b", "locality": "other", "locality_label": "Dar es Salaam"},
    {"match": r"^Total\b", "locality": "all", "locality_label": "Total"},
    {"match": r"^15-24\b", "age_group": "15-24", "drop_leading": 2},
    {"match": r"^15-35\b", "age_group": "15-35", "drop_leading": 2},
    {"match": r"^36\+", "age_group": "36+", "drop_leading": 1},
]

LAYOUTS["tanzania"] = {
    # This report's renderer wraps long row labels onto their own line, leaving
    # the numbers stranded on the next -- see `_rejoin_wrapped`.
    "join_wrapped_labels": True,
    "survey": "Integrated Labour Force Survey (ILFS)",
    "frequency": "annual",
    "working_age_base": "15+",
    "decimal": ".",
    # Every column names its own year, so nothing is inferred from the prose.
    # `period` here is only the fallback the harness requires.
    "period": "2025",
    "reference_period": "ILFS 2025",
    "tables": [
        {"page_contains": ["labour force participation rates by geographical areas"],
         "defaults": {"topic": "labour_force_participation_rate",
                      "definition": "strict",
                      "label": "Labour Force Participation Rate"},
         "take": "trailing", "columns": _TZ_COLS, "rows": list(_TZ_ROWS)},
        {"page_contains": ["employment to population ratio by geographical areas"],
         "defaults": {"topic": "employment_to_population_ratio",
                      "label": "Employment to Population Ratio"},
         "take": "trailing", "columns": _TZ_COLS, "rows": list(_TZ_ROWS)},
        {"page_contains": ["unemployment rates by geographical areas"],
         "defaults": {"topic": "unemployment_rate", "definition": "strict",
                      "label": "Unemployment Rate"},
         "take": "trailing", "columns": _TZ_COLS, "rows": list(_TZ_ROWS)},
    ],
}


LAYOUT = LAYOUTS['tanzania']
parse = make_parser(LAYOUT)
