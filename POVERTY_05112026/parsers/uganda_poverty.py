"""Uganda -- monetary-poverty layout (UBOS, UNHS 2019/20 report, chapter 6).

Welfare = real private consumption per adult equivalent (2009/10 prices),
against the official national (absolute) poverty line, set per region.

Collected:
  6.7  2019/20 and 6.8  2016/17 (the same layout): national, rural/urban, 4
       regions, region x residence, 15 sub-regions -- population share, P0,
       P1, P2 and the contribution to each. Mean consumption and the poor in
       millions are not collected (no money metric; a count in millions would
       need rescaling).
  Box 6.1  food poverty (consumption below the FOOD line -> line_level
       extreme), national / rural / urban / regions, 2016/17 and 2019/20.
  6.13 P0 P1 P2 by sector of employment and main activity of the household
       head, 2019/20 ("All" columns only).
Not collected: 6.12 and 6.13's pre-/during-COVID split (sub-samples of one
survey), 6.10 (Gini -- inequality), the USD 1.77 / 1.90 lines (text only).

CROSS-CHECK (verbatim): 2019/20 P0 20.3 / P1 5.2 / P2 2.0; rural 23.4;
Karamoja 65.7 / 28.1 / 14.6; Acholi 67.7; 2016/17 P0 21.4, Elgon 35.3;
food poverty 8.5 (both years); crop-agriculture heads 25.9.
"""
from __future__ import annotations

from ._vocab import label_rows
from .poverty_tables import make_parser

_COLS = [{"metric": "population_share"}, {"skip": True},
         {"metric": "headcount"}, {"metric": "gap"}, {"metric": "severity"},
         {"metric": "poor_share"}, {"metric": "gap_contribution"},
         {"metric": "severity_contribution"}, {"skip": True}]
_R = {"topic": "locality", "locality": "rural", "locality_label": "Rural"}
_U = {"topic": "locality", "locality": "urban", "locality_label": "Urban"}
_REG = ("Central", "Eastern", "Northern", "Western")
_ROW_ATTRS = {}
for _g in _REG:
    _ROW_ATTRS[f"{_g} rural"] = {"geography": _g, **_R}
    _ROW_ATTRS[f"{_g} urban"] = {"geography": _g, **_U}


def _survey(year, ref, survey):
    return {"period": year, "reference_period": ref, "survey": survey}


def _main(caption, s):
    return [
        {"page_contains": [caption], "exact_numbers": True, "defaults": s, "columns": _COLS,
         "rows": [{"match": r"^Uganda(?=\s)"}, {"match": r"^Rural(?=\s)", **_R},
                  {"match": r"^Urban(?=\s)", **_U}]},
        {"page_contains": [caption], "defaults": s, "columns": _COLS,
         "row_scan": {"expect_rows": 27, "exclude_labels": ["Uganda", "Rural", "Urban"],
                      "row_attrs": _ROW_ATTRS}},
    ]


_S19 = _survey("2019", "2019/20", "UNHS 2019/20")
_S16 = _survey("2016", "2016/17", "UNHS 2016/17")
_FOOD = {"line_level": "extreme", "line_name": "Food poverty line (UBOS)"}
_FOOD_COLS = [{"metric": "headcount", **_FOOD, **_S16}, {"skip": True},
              {"metric": "headcount", **_FOOD, **_S19}, {"skip": True}]

LAYOUT = {
    "survey": "UNHS 2019/20", "welfare_aggregate": "consumption",
    "unit_of_analysis": "person", "frequency": "ad_hoc", "decimal": ".",
    "line_type": "national", "line_level": "overall",
    "line_name": "Official national poverty line (UBOS, regional, 2009/10 prices)",
    "period": "2019", "reference_period": "2019/20",
    "tables": (
        _main("table 6.7: income poverty statistics in 2019/20", _S19)
        + _main("table 6.8: income poverty statistics in the unhs, 2016/17", _S16)
        + [
            {"page_contains": ["box 6.1: living standards below the official food poverty line"],
             "exact_numbers": True, "columns": _FOOD_COLS,
             "rows": [{"match": r"^Uganda(?=\s)"}, {"match": r"^Rural(?=\s)", **_R},
                      {"match": r"^Urban(?=\s)", **_U}]
                     + [{"match": rf"^{g}(?=\s)", "geography": g} for g in _REG]},
            {"page_contains": ["table 6.13: poverty statistics by main activity"],
             "start": r"^Sector of employment", "end": r"^Main Activity",
             "exact_numbers": True,
             "columns": [{"skip": True}, {"metric": "headcount"}, {"metric": "gap"},
                         {"metric": "severity"}] + [{"skip": True}] * 8,
             "rows": [dict(r, characteristic="Sector of employment: " + r["characteristic"])
                      for r in label_rows("employment_of_head", [
                          "Crop agriculture", "Non-crop agriculture", "Industry", "Trade",
                          "other services", "Not working"])]},
            {"page_contains": ["table 6.13: poverty statistics by main activity"],
             "start": r"^Main Activity", "exact_numbers": True,
             "columns": [{"skip": True}, {"metric": "headcount"}, {"metric": "gap"},
                         {"metric": "severity"}] + [{"skip": True}] * 8,
             "rows": [dict(r, characteristic="Main activity: " + r["characteristic"])
                      for r in label_rows("employment_of_head", [
                          "Owner account workers", "Public employment", "Private employment",
                          "Contributing family worker", "Not working"])]},
        ]),
}

parse = make_parser(LAYOUT)
