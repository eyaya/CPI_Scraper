"""South Sudan -- monetary-poverty layout (NBS, National Baseline Household
Survey 2009 report, annex Table 10.3 "Poverty Profile").

Per capita consumption; national poverty line SDG 72.9 per person per month
(Table 10.1: food 53.1 + non-food 19.8), Sudanese pounds of 2009 -- before
independence and the South Sudanese pound, so the currency is SDG as printed.
Estimates were produced by SSCCSE (the NBS's predecessor) in "Poverty in
Southern Sudan: Estimates from the NBHS 2009" (2010), which this report
summarises.

Collected: 10.3 -- P0, P1, P2, population share and share of the poor for
South Sudan, urban / rural, the three greater regions and the ten states (the
greater regions overlap the states: they are groupings of them).
Not collected: "poverty gap among the poor" (P1 / P0 x 100, no schema
metric), standard errors (Table 10.2), chapter 10's charts and its rounded
state table 10.4 (repeats 10.3 to whole numbers), head-of-household cuts
(chart only). No extreme-poverty rate is published.

CROSS-CHECK (verbatim): 50.6 / 23.7 / 14.3; urban 24.4, rural 55.4; Northern
Bahr Al Ghazal 75.6; Upper Nile 25.7. State population shares sum to 99.9,
shares of the poor to 100.1.
"""
from __future__ import annotations

from .poverty_tables import make_parser

_COLS = [{"metric": "headcount"}, {"metric": "gap"}, {"metric": "severity"},
         {"skip": True}, {"metric": "population_share"}, {"metric": "poor_share"}]

LAYOUT = {
    "survey": "NBHS 2009", "welfare_aggregate": "consumption",
    "unit_of_analysis": "person", "frequency": "ad_hoc", "decimal": ".",
    "line_type": "national", "line_level": "overall",
    "line_name": "National poverty line (SSCCSE, NBHS 2009)",
    "line_value": 72.9, "line_unit": "SDG per person per month",
    "period": "2009", "reference_period": "2009",
    "tables": [
        {"page_contains": ["10.3poverty profile"], "exact_numbers": True, "columns": _COLS,
         "rows": [{"match": r"^South Sudan(?=\s)"},
                  {"match": r"^Urban(?=\s)", "topic": "locality", "locality": "urban",
                   "locality_label": "Urban"},
                  {"match": r"^Rural(?=\s)", "topic": "locality", "locality": "rural",
                   "locality_label": "Rural"}]},
        {"page_contains": ["10.3poverty profile"], "columns": _COLS,
         "row_scan": {"expect_rows": 13,
                      "exclude_labels": ["South Sudan", "Urban", "Rural"]}},
    ],
}

parse = make_parser(LAYOUT)
