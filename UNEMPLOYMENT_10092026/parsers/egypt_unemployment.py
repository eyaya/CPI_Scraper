"""Egypt — unemployment / labour-force layout and parser.

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
# EGYPT -- CAPMAS, Quarterly Bulletin of the Labour Force Survey.
#
# READ FROM THE PDF, NOT THE WORKBOOK. CAPMAS publishes each issue as Excel
# and/or PDF, and the Q2 2026 issue is PDF ONLY. The descriptor used to ask
# for Excel and the discovery quietly fell back to whatever existed, so a PDF
# was written to a .xlsx filename and handed to an Excel parser. That fallback
# is now refused by name in `core/discover.capmas_publication_file`; if CAPMAS
# restores the workbook, switch `prefer` and `parser` back together.
#
# ⚠️ THE COLUMN ORDER IS REVERSED RELATIVE TO THE WORKBOOK. The bulletin is
# laid out right-to-left, so the columns print as
#
#     Characteristics          Total - ةلمج   Females - ثانإ   Males - روكذ
#     Total                    5.8            14.4             3.4
#
# -- TOTAL FIRST, MALES LAST -- while the Excel edition runs Males, Females,
# Total. Reading this table with the workbook's order would report Egypt's
# male unemployment as 5.8% and its total as 3.4%: both plausible, both wrong.
# The values above are the check: female unemployment in Egypt runs several
# times male, so Females must be the LARGEST of the three.
#
# The three section headings ("Age group", "Educational Status",
# "Geograghical Regions" -- CAPMAS's own spelling) repeat the national figures
# on their own line, so they are deliberately not declared as rows; only the
# single `Total` row carries the national value.
#
# Egypt's geographic strata cross urban/rural with region, so `locality` takes
# the urban/rural half and `geography` keeps the published stratum whole.
#
# CROSS-CHECK (Q2 2026): national 5.8 (F 14.4 / M 3.4); 20-24 14.5;
# university & higher 10.7; urban governorates 11.2; rural Upper Egypt 3.2.
# =========================================================================
_EG_COLS = [
    {"sex": "total"},
    {"sex": "female"},
    {"sex": "male"},
]

_EG_AGES = ["15- 19", "20- 24", "25- 29", "30- 39", "40- 49", "50-59", "60- 64"]
_EG_EDUC = ["Illiterate", "Read & Write", "Less than intermediate",
            "General/ Azhari secondary", "Technical Secondary",
            "Above Intermediate", "University & Higher"]
_EG_REGIONS = ["Urban governorates", "Urban lower Egypt", "Rural lower Egypt",
               "Urban upper Egypt", "Rural upper Egypt",
               "Urban frontier governorates", "Rural frontier governorates"]


def _eg_rows(topic: str, definition: str) -> list[dict]:
    rows = [{"match": r"^Total\s+(?=[\d])", "topic": topic,
             "definition": definition, "label": "Total"}]
    for a in _EG_AGES:
        band = a.replace(" ", "")
        rows.append({"match": r"^%s\s+(?=[\d])" % a.replace(" ", r"\s*"),
                     "topic": topic, "definition": definition,
                     "age_group": band, "label": band, "drop_leading": 2})
    for e in _EG_EDUC:
        rows.append({"match": r"^%s\s+(?=[\d])" % re.escape(e),
                     "topic": topic, "definition": definition,
                     "education": e, "label": e})
    for g in _EG_REGIONS:
        low = g.lower()
        rows.append({"match": r"^%s\s+(?=[\d])" % re.escape(g),
                     "topic": topic, "definition": definition,
                     "geography": g, "locality_label": g,
                     "locality": "urban" if low.startswith("urban") else "rural",
                     "label": g})
    return rows


LAYOUTS["egypt"] = {
    "survey": "Quarterly Labour Force Survey",
    "frequency": "quarterly",
    "working_age_base": "15+",
    "decimal": ".",
    # The reference quarter is printed on every page of the bulletin, as a
    # MONTH RANGE and never as "Q2":
    #     Bulletinof Labour Force ( April -June) 2026
    # The whole phrase has to be captured in ONE group, because the year
    # sits OUTSIDE the parentheses and `parse_period` is handed group(1)
    # alone -- capturing just the months would date every issue to a
    # quarter with no year.
    "period_patterns": [
        r"(\(\s*[A-Z][a-z]+\s*[-–]\s*[A-Z][a-z]+\s*\)\s*20\d{2})",
    ],
    "tables": [
        {"page_contains": ["economic activity rates by age group"],
         "page_excludes": ["list of tables"],
         "columns": _EG_COLS,
         "rows": _eg_rows("labour_force_participation_rate", "strict")},
        {"page_contains": ["employment rates by age groups"],
         "page_excludes": ["list of tables"],
         "columns": _EG_COLS,
         "rows": _eg_rows("employment_to_population_ratio", "not_applicable")},
        {"page_contains": ["unemployment rates by age group"],
         "page_excludes": ["list of tables"],
         "columns": _EG_COLS,
         "rows": _eg_rows("unemployment_rate", "strict")},
    ],
}


LAYOUT = LAYOUTS['egypt']
parse = make_parser(LAYOUT)
