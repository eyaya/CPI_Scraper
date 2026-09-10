"""Botswana — unemployment / labour-force layout and parser.

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
# BOTSWANA -- Statistics Botswana, Quarterly Multi-Topic Survey (QMTS)
# Labour Force Module. "Table 1.0: National Headline Labour Force Indicators".
#
# Header: Indicator | Q4 2022 | Q3 2023 | Q1 2024 {Total | Male | Female}
#         | two % change columns.  Seven numeric columns; only the CURRENT
# quarter's three are captured -- the two historical columns are restatements
# and the change columns are derived.
#
# MIXED UNITS: rows 1-15 are absolute persons (row 13 is Pula), rows 17-24 are
# rates. An in-table sub-header line "Change (Percentage points)" occupies the
# position where row 16 would be, and row 23 is simply skipped in the source --
# the printed numbering is not contiguous.
#
# Printed typos preserved in the regexes: "Employment to Population Ration",
# "(15 year and above)" (singular).
#
# TWO PARALLEL BASES: 15+ and 18+ are published side by side (rows 6-9 and 20).
# Both are captured, each carrying its own `working_age_base`.
#
# LEVEL BREAK: the QMTS series (27.6% in Q1 2024) is NOT continuous with the
# BMTHS 2024/25 round (21.0%). Do not chain them without a flag.
#
# CROSS-CHECK (Q1 2024): population 15+ 1,651,820; labour force 1,041,204;
# employed 754,146; unemployed 287,059; EPR 45.7; LFPR 63.0;
# unemployment 27.6 (M 27.2 / F 27.9); extended 32.5; youth 15-35 38.2;
# NEET 41.3.
# =========================================================================
_BW_COLS = [{"skip": True}, {"skip": True},
            {"sex": "total"}, {"sex": "male"}, {"sex": "female"},
            {"skip": True}, {"skip": True}]

LAYOUTS["botswana"] = {
    "survey": "Quarterly Multi-Topic Survey (QMTS) -- Labour Force Module",
    "frequency": "quarterly",
    "working_age_base": "15+",
    "decimal": ".",
    # Each pattern must capture the WHOLE period phrase in ONE group --
    # `_resolve_period` feeds group(1) to `parse_period`, so a pattern that
    # splits the quarter and the year across two groups yields only "1".
    "period_patterns": [
        r"(QMTS\s+Q[1-4]\s+of\s+20\d{2})",
        r"(Q[1-4]\s+of\s+20\d{2})",
        r"\b(Q[1-4]\s*20\d{2})\b",
    ],
    "tables": [{
        "page_contains": ["national headline labour force indicators"],
        "take": "trailing",
        # EVERY ROW IS PREFIXED WITH ITS PRINTED INDEX -- "1 Population (15
        # years and above) 1,611,892 ...". With `^`-anchored patterns and
        # `re.search`, that index meant not one row spec matched. Stripping it
        # once here also removes it from the number list, which is why no row
        # below carries `drop_leading` for it any more: those were applied to
        # some rows and forgotten on others (rows 4, 5, 10 and 24 had none),
        # so fixing only the anchors would have shifted those four rows by a
        # column while leaving the rest correct -- the hardest kind of error
        # to notice, since every value would still be a plausible number.
        "strip_row_number": True,
        "columns": _BW_COLS,
        "rows": [
            # `\s+(?=[\d(])` -- "the label ends here and the data begins".
            # Needed because several labels are prefixes of others: without it
            # "Employed Population" also matches "Employed Population (18
            # years and above)", and the 15+ row silently takes the 18+ values.
            {"match": r"^Population \(15 years and above\)",
             "topic": "working_age_population",
             "label": "Population (15 years and above)"},
            {"match": r"^Population Outside Labour Force",
             "topic": "outside_labour_force",
             "label": "Population Outside Labour Force (15 years and above)"},
            {"match": r"^Labour Force \(15 years and above\)",
             "topic": "labour_force",
             "label": "Labour Force (15 years and above)"},
            {"match": r"^Employed Population\s+(?=[\d(])", "topic": "employed",
             "exclude": r"^Employed Population \(18",
             "label": "Employed Population"},
            {"match": r"^Unemployed Population\s+(?=[\d(])", "topic": "unemployed",
             "exclude": r"^Unemployed Population \(18",
             "label": "Unemployed Population"},
            {"match": r"^Population \(18 years and above\)",
             "topic": "working_age_population", "working_age_base": "18+",
             "label": "Population (18 years and above)"},
            {"match": r"^Labour Force \(18 years and above\)",
             "topic": "labour_force", "working_age_base": "18+",
             "label": "Labour Force (18 years and above)"},
            {"match": r"^Employed Population \(18 years and above\)",
             "topic": "employed", "working_age_base": "18+",
             "label": "Employed Population (18 years and above)"},
            {"match": r"^Unemployed Population \(18 years and above\)",
             "topic": "unemployed", "working_age_base": "18+",
             "label": "Unemployed Population (18 years and above)"},
            {"match": r"^Time Related Under Employed Population",
             "topic": "potential_labour_force",
             "label": "Time Related Under Employed Population"},
            # "Ration" is the printed spelling.
            {"match": r"^Employment to Population Rati?on \(EPR\)",
             "topic": "employment_to_population_ratio",
             "label": "Employment to Population Ratio (EPR)"},
            {"match": r"^Labour Force Participation Rate \(LFPR\)",
             "topic": "labour_force_participation_rate", "definition": "strict",
             "label": "Labour Force Participation Rate (LFPR)"},
            # "(15 year and above)" -- the singular is the printed typo.
            {"match": r"^Unemployment Rate % \(15 year",
             "topic": "unemployment_rate", "definition": "strict",
             "label": "Unemployment Rate % (15 years and above)"},
            {"match": r"^Unemployment Rate % \(18 years",
             "topic": "unemployment_rate", "definition": "strict",
             "working_age_base": "18+",
             "label": "Unemployment Rate % (18 years and above)"},
            {"match": r"^Extended Unemployment Rate %",
             "topic": "unemployment_rate", "definition": "broad",
             "label": "Extended Unemployment Rate % (15 years and above)"},
            # The label's own "15-35" is two numbers ahead of the data.
            {"match": r"^Youth Unemployment Rate \(15-35 years\)",
             "topic": "youth_unemployment_rate", "definition": "strict",
             "age_group": "15-35", "drop_leading": 2,
             "label": "Youth Unemployment Rate (15-35 years)"},
            # THE ONLY WRAPPED LABEL IN THE TABLE. It prints as
            #     Youth not in Education, not in Employment or
            #     24 Training (NEET Rate %) 39.9 38.5 41.3 40.6 42.0 1.4 2.8
            # so the line carrying the data begins "Training", and a pattern
            # anchored on "Youth not in Education" matches only the caption
            # half, which has no numbers.
            {"match": r"^Training \(NEET Rate", "topic": "neet_rate",
             "age_group": "15-35", "label": "Youth NEET Rate (15-35 years)"},
        ],
    }],
}


LAYOUT = LAYOUTS['botswana']
parse = make_parser(LAYOUT)
