"""Sierra Leone -- monetary-poverty layout (Stats SL, SLIHS 2018 report,
chapter 9 "Poverty and inequality" and Appendices 1-2).

National line Le 3,921,000 per adult equivalent per year (old leones, before
the 2022 redenomination); food line Le 2,125,000 = the EXTREME line.
Consumption per adult equivalent.

Read:
  Appendix 1  total and extreme P0/P1/P2 (SEs skipped) for Sierra Leone,
              rural/urban, Greater Freetown / other urban, 5 provinces and
              14 districts + Western Area Rural + Freetown
  Table 9.1   P0 (both lines) and population share by household size, sex,
              age, education, occupation of the head, economic diversification
  Appendix 2  the 2011 column only: P0 on a welfare aggregate made comparable
              with 2018 (2018 line deflated to 2011). Its 2018 column is a
              DIFFERENT aggregate from Appendix 1 (rural 78.5 vs 73.6) and
              would collide with it, so it is not read.

THE REPORT'S PROSE DISAGREES WITH ITS OWN TABLES (extreme 12.9% in 9.1 vs
13.7 in Appendix 1; rural 73.9 vs 73.6; Freetown 22.8 vs 23.5; P2 7.5 vs 7.6).
Only tables are read. The official 2011 rate (52.9%) is prose only and NOT
comparable (Box 2).

CROSS-CHECK (verbatim): 56.8 / 18.0 / 7.6; extreme 13.7 / 2.8 / 0.8;
Tonkolili 84.4; Pujehun extreme 30.8; Freetown 16.7; 8+ member households 71.5;
University-educated head 5.3; 2011 comparable 62.4.
"""
from __future__ import annotations

from ._vocab import label_rows
from .poverty_tables import make_parser

_EX = {"line_level": "extreme", "line_name": "Food poverty line 2018",
       "line_value": 2125000, "line_unit": "SLL (old leones) per adult equivalent per year"}
_S = {"skip": True}
_FGT_SE = [{"metric": "headcount"}, _S, {"metric": "gap"}, _S, {"metric": "severity"}, _S]

_PROV = ["East", "North", "North West", "South", "West"]
_DIST = ["Kailahun", "Kenema", "Kono", "Bombali", "Falaba", "Koinadugu", "Tonkolili",
         "Kambia", "Karene", "Port Loko", "Bo", "Bonthe", "Moyamba", "Pujehun"]


def _geo_rows(war_label: str):
    rows = [{"match": r"^Sierra Leone(?=\s+\d)"},
            {"match": r"^[Rr]ural(?=\s+\d)", "topic": "locality", "locality": "rural",
             "locality_label": "Rural"},
            {"match": r"^[Uu]rban(?=\s+\d)", "topic": "locality", "locality": "urban",
             "locality_label": "Urban"},
            {"match": r"^Greater Freetown(?:14)?(?=\s+\d+\.\d)", "topic": "locality",
             "locality": "other", "locality_label": "Greater Freetown"},
            {"match": r"^other urban(?=\s+\d)", "topic": "locality", "locality": "other",
             "locality_label": "Other urban"}]
    rows += [{"match": rf"^{g}(?=\s+\d)", "geography": g} for g in _PROV + _DIST]
    rows += [{"match": rf"^{war_label}(?=\s+\d)", "geography": "Western Area Rural"},
             {"match": r"^Freetown(?=\s+\d)", "geography": "Freetown"}]
    return rows


def _t91(start, end, topic, labels, **extra):
    return {"page_contains": ["table 9.1: poverty rates by household characteristics"],
            "start": start, "end": end, "exact_numbers": True,
            "columns": [{"metric": "headcount"}, {"metric": "headcount", **_EX},
                        {"metric": "population_share"}],
            "rows": label_rows(topic, labels, **extra)}


_A2 = {"period": "2011", "reference_period": "2011",
       "survey": "SLIHS 2011 (aggregate comparable with 2018)", "line_value": "", "line_unit": ""}


def _a2_rows():
    return [{"match": r"^National(?=\s+\d)"},
            {"match": r"^Freetown(?=\s+\d)", "topic": "locality", "locality": "other",
             "locality_label": "Freetown (2011-18 comparable)"},
            {"match": r"^Other Urban(?=\s+\d)", "topic": "locality", "locality": "other",
             "locality_label": "Other urban (2011-18 comparable)"},
            {"match": r"^Rural(?=\s+\d)", "topic": "locality", "locality": "rural",
             "locality_label": "Rural (2011-18 comparable)"}]


LAYOUT = {
    "survey": "SLIHS 2018", "welfare_aggregate": "consumption",
    "unit_of_analysis": "person", "frequency": "ad_hoc", "decimal": ".",
    "line_type": "national", "line_level": "overall",
    "line_name": "National poverty line 2018", "line_value": 3921000,
    "line_unit": "SLL (old leones) per adult equivalent per year",
    "period": "2018", "reference_period": "2018",
    "tables": [
        {"page_contains": ["appendix 1: poverty rates for 2018", "total poverty measures"],
         "exact_numbers": True, "columns": _FGT_SE, "rows": _geo_rows("WAR")},
        {"page_contains": ["extreme poverty measures", "western area rural"],
         "exact_numbers": True, "defaults": _EX, "columns": _FGT_SE,
         "rows": _geo_rows("Western Area Rural")},
        _t91(r"^Household size$", r"^Sex of household head$", "household_size",
             ["1 to 3", "4 or 5", "6 or 7", "8 or more"]),
        {**_t91(r"^Sex of household head$", r"^Age of household head$", "sex_of_head", []),
         "rows": [{"match": r"^Male(?=\s+\d)", "topic": "sex_of_head",
                   "characteristic": "Male", "sex": "male"},
                  {"match": r"^Female(?=\s+\d)", "topic": "sex_of_head",
                   "characteristic": "Female", "sex": "female"}]},
        _t91(r"^Age of household head$", r"^Education of household head$", "age_of_head",
             ["17 to 25", "26 to 35", "36 to 45", "46 to 55", "56 to 65", "66 and over"]),
        _t91(r"^Education of household head$", r"^Occupation of household head$",
             "education_of_head",
             ["None", "Primary incomplete", "Primary complete", "Secondary incomplete",
              "Secondary complete", "Technical / vocational", "University"]),
        _t91(r"^Occupation of household head$", r"^Economic diversification$",
             "employment_of_head",
             ["Agriculture, forestry and fishing", "Mining and quarrying", "Manufacturing",
              "Construction", "Wholesale and retail trade", "Education", "Other",
              "Not working"]),
        _t91(r"^Economic diversification$", r"^Source", "employment_of_head",
             ["Primary production only", "Primary production and business only",
              "business only", "wage employment (at least one hh member)"]),
        {   # Appendix 2 -- the 2011 comparable estimates only
            "page_contains": ["appendix 2: poverty trends, 2011-2018"],
            "start": r"^Poverty rate$", "end": r"^Extreme Poverty Rate$",
            "defaults": {**_A2,
                         "line_name": "2018 national line deflated to 2011 (comparable aggregate)"},
            "columns": [{"metric": "headcount"}], "rows": _a2_rows()},
        {"page_contains": ["appendix 2: poverty trends, 2011-2018"],
         "start": r"^Extreme Poverty Rate$", "end": r"^Poverty lines in",
         "defaults": {**_EX, **_A2,
                      "line_name": "2018 food line deflated to 2011 (comparable aggregate)"},
         "columns": [{"metric": "headcount"}], "rows": _a2_rows()},
    ],
}

parse = make_parser(LAYOUT)
