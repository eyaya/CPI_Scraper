"""Tanzania -- monetary-poverty layout (NBS, 2017-18 HBS Key Indicators Report).

TANZANIA MAINLAND ONLY: the HBS excludes Zanzibar (which OCGS surveys
separately), so every row's geography is "Tanzania Mainland" or one of its 26
regions -- never "Total country".

Consumption per adult equivalent per month; lines (Table 4.2): basic needs
TZS 49,320, food TZS 33,748. "Food poverty" here = below the FOOD line
("extremely poor ... cannot afford basic foodstuffs") -> line_level extreme.

Collected:
  4.3  P0 P1 P2 for both lines: rural / urban, 26 regions, Mainland total.
  4.4  P0 for both lines by household size -- NOTE the columns are
       Food | Basic Needs here, the reverse of every other table.
  4.5  P0 P1 P2 for both lines by sex of the household head.
  4.6  P0 P1 P2 for both lines by number of children under five.
Not collected: 4.1 (consumption), 4.2's back-round lines (no P0 table for
those rounds; 2011-12's 28.2 / 9.7 are in prose and Figure 4.1 only), 4.7
(Gini), figures 4.2-4.4.

CROSS-CHECK (verbatim): Mainland 26.4 / 6.2 / 2.1, food 8.0 / 1.4 / 0.4;
rural 31.3, urban 15.8; Rukwa 45.0 (food 19.8); Dar es Salaam 8.0; 7+ member
households 38.7 (food 12.9); female-headed 27.4.
"""
from __future__ import annotations

from ._vocab import label_rows
from .poverty_tables import make_parser

_BN = {"line_level": "overall", "line_name": "Basic needs poverty line (NBS, HBS 2017-18)",
       "line_value": 49320, "line_unit": "TZS per adult equivalent per month"}
_FOOD = {"line_level": "extreme", "line_name": "Food poverty line (NBS, HBS 2017-18)",
         "line_value": 33748, "line_unit": "TZS per adult equivalent per month"}
_COLS6 = ([{"metric": m, **_BN} for m in ("headcount", "gap", "severity")]
          + [{"metric": m, **_FOOD} for m in ("headcount", "gap", "severity")])
_MAIN = {"geography": "Tanzania Mainland"}

LAYOUT = {
    "survey": "HBS 2017-18", "welfare_aggregate": "consumption",
    "unit_of_analysis": "person", "frequency": "ad_hoc", "decimal": ".",
    "line_type": "national", **_BN,
    "period": "2017", "reference_period": "2017-18",
    "tables": [
        {"page_contains": ["table 4.3: poverty indices by rural/urban and region"],
         "exact_numbers": True, "columns": _COLS6, "defaults": _MAIN,
         "rows": [{"match": r"^Rural(?=\s)", "topic": "locality", "locality": "rural",
                   "locality_label": "Rural"},
                  {"match": r"^Urban(?=\s)", "topic": "locality", "locality": "urban",
                   "locality_label": "Urban"},
                  {"match": r"^Total \(average\)(?=\s)"}]},
        {"page_contains": ["table 4.3: poverty indices by rural/urban and region"],
         "columns": _COLS6,
         "row_scan": {"expect_rows": 26, "exclude_labels": ["Rural", "Urban", "Total"]}},
        {"page_contains": ["table 4.4: incidence of poverty (percent) by size of household"],
         "start": r"^Household Size", "end": r"^Total \(average\)", "exact_numbers": True,
         "defaults": _MAIN,
         "columns": [{"metric": "headcount", **_FOOD}, {"metric": "headcount", **_BN}],
         "rows": [{"match": rf"^{n}(?=\s)", "topic": "household_size",
                   "characteristic": c}
                  for n, c in (("1", "1 person"), ("2", "2 persons"), ("3", "3 persons"),
                               ("4", "4 persons"), ("5", "5 persons"), ("6", "6 persons"),
                               (r"7\+", "7+ persons"))]},
        {"page_contains": ["table 4.5: incidence of poverty (percent) by sex of household head"],
         "start": r"^Sex of Household Head", "exact_numbers": True, "defaults": _MAIN,
         "columns": _COLS6,
         "rows": [{"match": r"^Male(?=\s)", "topic": "sex_of_head", "characteristic": "Male",
                   "sex": "male"},
                  {"match": r"^Female(?=\s)", "topic": "sex_of_head",
                   "characteristic": "Female", "sex": "female"}]},
        {"page_contains": ["table 4.6: incidence of poverty (percent) by number of children"],
         "start": r"^Under Age Five", "exact_numbers": True, "defaults": _MAIN,
         "columns": _COLS6,
         "rows": [dict(r, characteristic="Children under five: " + r["characteristic"])
                  for r in label_rows("household_type", [
                      "No Child", "One Child", "Two Children", "Three to Five Children",
                      "Six or More Children"])]},
    ],
}

parse = make_parser(LAYOUT)
