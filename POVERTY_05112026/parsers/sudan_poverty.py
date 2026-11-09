"""Sudan -- monetary poverty, CBS National Baseline Household Survey 2009.

Fieldwork 2009, the 15 states of NORTHERN Sudan (the survey predates the 2011
secession, so its coverage is today's Sudan; South Sudan's own NBHS 2009 is a
separate SSCCSE survey). cbs.gov.sd no longer resolves; the file is the
Wayback Machine's `id_` copy of CBS's own PDF (the route unemployment/ and
labour/ use for Sudan). Poverty line SDG 113,8 per person per month (p. 27,
"well below the poverty line calculated similar to SDG 113.8").

Collected:
  Table 9.1 (MDG indicators)  P0 (MDG 1.1) and poverty gap (MDG 1.2) for
                              Northern Sudan and its six regions
  Annex B3                    share of the population that is poor, urban /
                              rural / total, by age group and by state (whole
                              numbers). Its "Northern 15 States" TOTAL (46) is
                              Table 9.1's 46,5 rounded -- one key, so only the
                              unrounded figure is kept; its urban and rural
                              cells are new.
Not collected: B3's "Non poor" columns (the complement), MDG 1.3 (share of
the poorest quintile -- inequality), MDG 1.6 (poverty among the EMPLOYED 15+ --
a sub-population this schema has no topic for), the 2014/15 NHBPS food
security and poverty analysis (charts only).

REGIONS AND STATES SHARE NAMES ("Northern", "Khartoum"): the six regions of
Table 9.1 are filed as "<name> region" so a region never lands on its state.

CROSS-CHECK (verbatim): P0 46,5, gap 16,2; Khartoum region 26,0 / 6,4;
Darfur 62,7 / 24,6; urban 27, rural 57; Red Sea state 58 (rural 80); age 5-9
56.
"""
from __future__ import annotations

import re

from .poverty_tables import make_parser

_REGIONS = ["Northern", "Eastern", "Khartoum", "Central", "Kordufan", "Darfur"]
_REG_COLS = [{}] + [{"geography": f"{r} region"} for r in _REGIONS]

_U = {"topic": "locality", "locality": "urban", "locality_label": "Urban"}
_R = {"topic": "locality", "locality": "rural", "locality_label": "Rural"}
_B3 = [{"metric": "headcount", "locality": "urban", "locality_label": "Urban"}, {"skip": True},
       {"metric": "headcount", "locality": "rural", "locality_label": "Rural"}, {"skip": True},
       {"metric": "headcount"}, {"skip": True}]
_AGES = ["0- 4", "5- 9", "10-14", "15-19", "20-24", "25-29", "30-34", "35-39", "40-44",
         "45-49", "50-54", "55-59", "60-64", "65+"]

LAYOUT = {
    "survey": "NBHS 2009", "welfare_aggregate": "consumption",
    "unit_of_analysis": "person", "frequency": "ad_hoc", "decimal": ".",
    "line_type": "national", "line_level": "overall",
    "line_name": "National poverty line (NBHS 2009)",
    "line_value": 113.8, "line_unit": "SDG per person per month",
    "period": "2009", "reference_period": "2009",
    "tables": [
        {   # Table 9.1 -- Northern Sudan + six regions
            "page_contains": ["table 9.1 selected mdg indicators"],
            "exact_numbers": True,
            "columns": [dict(c, metric="headcount") for c in _REG_COLS],
            "rows": [
                {"match": r"^MDG 1\.1 Proportion of Percent"},
                {"match": r"^MDG 1\.2 Poverty gap ratio Percent",
                 "columns": [dict(c, metric="gap") for c in _REG_COLS]},
            ],
        },
        {   # Annex B3 -- national urban / rural; age groups
            "page_contains": ["b3. percentage distribution of total population by poverty status"],
            "exact_numbers": True, "columns": _B3,
            "rows": [
                {"match": r"^Northern 15 States", "characteristic": "Total",
                 "columns": [dict(_B3[0], topic="locality", characteristic="Urban"), {"skip": True},
                             dict(_B3[2], topic="locality", characteristic="Rural"), {"skip": True},
                             {"skip": True}, {"skip": True}]},
                *[{"match": r"^(?:Age group\s+)?" + re.escape(a).replace(r"\ ", r"\s?") + r"(?=\s+\d)",
                   "topic": "age", "characteristic": a.replace(" ", "")} for a in _AGES],
            ],
        },
        {   # Annex B3 -- the 15 states
            "page_contains": ["b3. percentage distribution of total population by poverty status"],
            "start": r"^State\b", "start_inclusive": True, "columns": _B3,
            "row_scan": {"expect_rows": 15,
                         "label": r"^(?:State\s+)?\d{2}\s+([A-Za-z][A-Za-z ]+?)\s+(?=\d)"},
        },
    ],
}

parse = make_parser(LAYOUT)
