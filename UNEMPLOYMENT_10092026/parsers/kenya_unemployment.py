"""Kenya — unemployment / labour-force layout and parser.

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
# KENYA -- KNBS, Quarterly Labour Force Report.
#
# A HISTORICAL BACKFILL, not a live series. KNBS ran the QLFS from 2019 Q1 to
# 2022 Q4 and then stopped; the whole run was bulk-uploaded into a single
# /2023/09/ folder, which is itself the evidence the series was archived rather
# than continued. The 2026 Kenya Integrated Labour Force Survey is in the field
# and will supersede it, but has published nothing yet.
#
# The Economic Survey's Chapter 3 workbook is NOT used: it is establishment /
# administrative employment (wage employment by industry), not an ILO household
# unemployment rate, and does not belong in this indicator.
#
# Table shape: Indicator | <year-ago quarter> | <previous quarter> |
# <current quarter>. Only the current quarter's column is captured.
#
# WORKING-AGE BASE IS 15-64 -- a closed upper bound, like Sierra Leone.
# Both ICLS rates are published and labelled LU1 (strict) and LU3 (broad).
#
# CROSS-CHECK (2022 Q4): population 15-64 29,066,237; labour force 19,398,165;
# employed 18,438,164; LFPR 66.7; EPR 63.4; LU1 4.9; LU3 13.9;
# long-term unemployment 3.2; NEET 19.0.
# =========================================================================
LAYOUTS["kenya"] = {
    "survey": "Quarterly Labour Force Report (QLFS)",
    "frequency": "quarterly",
    "working_age_base": "15-64",
    "decimal": ".",
    # THE PERIOD IS PINNED, NOT SCANNED. The table's header is split over two
    # lines --
    #     Quarter 4,  Quarter 3,  Quarter 4,
    #     Indicator      2021        2022        2022
    # -- so a pattern looking for a quarter near a year finds "Quarter 4" next
    # to 2021 and dated the whole release 2021-Q4. The values taken are the
    # THIRD column, which is Q4 2022. Pinning is safe here in a way it would
    # not be for a live series: the descriptor points at one archived file and
    # KNBS discontinued the QLFS after this issue.
    "period": "2022-Q4",
    "reference_period": "October - December 2022",
    "tables": [{
        "page_contains": ["unemployment rate"],
        # Every label is followed by LEADER DOTS out to the first column:
        #     Labour Force.......................... 18,716,433 19,113,051 19,398,165
        # so `^Labour Force\s*$` -- and four patterns like it -- matched
        # nothing, and this table shipped four of its nineteen rows. The
        # `\.{2,}` is also what stops "Labour Force" swallowing "Labour Force
        # Participation (%)".
        #
        # Three labels had been guessed rather than read. The report prints:
        #     "Employment/Population Ratio (%)"  not "Employment-to-Population Ratio"
        #     "Labour Force Participation (%)"   not "... Participation Rate"
        #     "Long-Term Unemployed (%)"         not "Long-Term Unemployment Rate"
        #
        # `take: trailing` picks the current quarter and, as a side effect,
        # absorbs digits inside a label ("(15-64)", "[LU1]", "Unemployed1"),
        # so no row needs `drop_leading`.
        "take": "trailing",
        "columns": [{"skip": True}, {"skip": True}, {}],
        "rows": [
            {"match": r"^Population \(15", "topic": "working_age_population",
             "label": "Population (15-64)"},
            {"match": r"^Labour Force\.{2,}", "topic": "labour_force",
             "definition": "strict", "label": "Labour Force"},
            {"match": r"^Extended Labour Force\.{2,}", "topic": "labour_force",
             "definition": "broad", "label": "Extended Labour Force"},
            {"match": r"^Employed\.{2,}", "topic": "employed", "label": "Employed"},
            {"match": r"^Employment/Population Ratio",
             "topic": "employment_to_population_ratio",
             "label": "Employment/Population Ratio (%)"},
            {"match": r"^Unemployed1", "topic": "unemployed",
             "definition": "strict", "label": "Unemployed (strict)"},
            {"match": r"^Unemployment Rate \[?LU1", "topic": "unemployment_rate",
             "definition": "strict", "label": "Unemployment Rate [LU1]"},
            {"match": r"^Unemployed2", "topic": "unemployed", "definition": "broad",
             "label": "Unemployed incl. potential labour force"},
            {"match": r"^Unemployment Rate \[?LU3",
             "topic": "labour_underutilisation_rate", "definition": "broad",
             "label": "Unemployment Rate [LU3]"},
            {"match": r"^Long-?Term Unemployed \(%\)",
             "topic": "long_term_unemployment_share",
             "label": "Long-Term Unemployed (%)"},
            {"match": r"^Long-?Term Unemployed\.{2,}", "topic": "unemployed",
             "label": "Long-Term Unemployed"},
            # Two inactivity lines are printed: the first includes the
            # potential labour force, the second (footnote 3) excludes it.
            # Only the first is taken -- the schema has a single
            # `outside_labour_force` topic and nowhere to hang the difference.
            {"match": r"^Not in Labor Force \(Inactive\)\.{2,}",
             "topic": "outside_labour_force",
             "label": "Not in Labour Force (Inactive)"},
            {"match": r"^Labour Force Participation \(%\)",
             "topic": "labour_force_participation_rate", "definition": "strict",
             "label": "Labour Force Participation (%)"},
            {"match": r"^Labour Under Utilization \(LU2\)",
             "topic": "labour_underutilisation_rate", "definition": "broad",
             "label": "Labour Underutilization (LU2)"},
            # The report's youth band is 15-34; this row previously said 15-24.
            {"match": r"^Youth \(15-34", "topic": "working_age_population",
             "age_group": "15-34", "label": "Youth (15-34)"},
            {"match": r"^Youth Not in Employment, Education or Training",
             "topic": "neet_rate", "age_group": "15-34", "measure": "count",
             "unit": "persons", "label": "Youth NEET (count)"},
            {"match": r"^NEET Rate", "topic": "neet_rate", "age_group": "15-34",
             "label": "NEET Rate"},
        ],
    }],
}


LAYOUT = LAYOUTS['kenya']
parse = make_parser(LAYOUT)
