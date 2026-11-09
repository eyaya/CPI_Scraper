"""Namibia -- monetary poverty (Namibia Statistics Agency / former CBS).

Three cost-of-basic-needs lines, per ADULT EQUIVALENT per month (N$):
  FPL  food poverty line                       -> line_level extreme
  LBPL lower bound poverty line ("severely poor") -> line_level other
  UBPL upper bound poverty line ("poor")       -> line_level overall
(the same FPL/LBPL/UBPL family as Stats SA; mapped the same way).

PRIMARY: "NHIES 2015/2016 Key Poverty Indicators (Preliminary Figures)",
Table 3 (line values) and Table 4 (headcount ratio of PERSONS on each line,
2003/04, 2009/10, 2015/16). NSA's own cautionary note calls these
preliminary; the full NHIES 2015/16 report is not on the rebuilt nsa.org.na.

EXTRA: "A Review of Poverty and Inequality in Namibia" (CBS/NPC, 2008), Annex
F, NHIES 2003/04, HOUSEHOLDS: P0/P1/P2 and poverty share on the lower and
upper bound lines by region and urban/rural (F-1), sex and age of head (F-2),
education of head (F-24). Its household headcounts (13.8 / 27.6) are not the
person headcounts the 2016 release gives for 2003/04 (21.9 / 37.7) -- told
apart by unit_of_analysis, both published.

Not collected: F-3..F-20 (language, income source, dwelling, assets --
no topic), F-21..F-23 (urbanisation shares, ranks), Annex I confidence
intervals, Gini (inequality), the 1993/94 report (food-share indicator, not
a poverty line).

CROSS-CHECK: 2015/16 persons FPL 5.8 / LBPL 11.0 / UBPL 18.0; 2009/10 7.3 /
15.3 / 28.7; lines 2015/16 N$293.1 / 389.3 / 520.8. 2003/04 households UBPL
P0 27.6 P1 8.9 P2 4.1; Kavango 56.5; Khomas 2.4 (LBPL); female head 30.4.
"""
from __future__ import annotations

import pandas as pd

from ._vocab import label_rows
from .poverty_tables import make_parser

UNIT = "NAD per adult equivalent per month"
_LINES = {  # Table 3, current N$ per adult equivalent per month
    "extreme": ("Food poverty line (FPL)", {"2003": 127.15, "2009": 204.05, "2015": 293.1}),
    "other": ("Lower-bound poverty line (LBPL)", {"2003": 184.56, "2009": 277.54, "2015": 389.3}),
    "overall": ("Upper bound poverty line (UBPL, poor)", {"2003": 262.45, "2009": 377.96, "2015": 520.8}),
}
_ROUNDS = [("2003", "2003/04", "NHIES 2003/04"), ("2009", "2009/10", "NHIES 2009/10"),
           ("2015", "2015/16", "NHIES 2015/16")]


def _t4(level, start, end):
    name, vals = _LINES[level]
    cols = [{"metric": "headcount", "period": p, "reference_period": r, "survey": s,
             "line_level": level, "line_name": name, "line_value": vals[p], "line_unit": UNIT}
            for p, r, s in _ROUNDS] + [{"skip": True}] * 3
    return {"page_contains": ["table 4: selected inequality and poverty estimates"],
            "start": start, "end": end, "columns": cols,
            "rows": [{"match": r"^Headcount ratio \(%\)"}]}


LAYOUT = {
    "survey": "NHIES 2015/16", "welfare_aggregate": "consumption",
    "unit_of_analysis": "person", "frequency": "ad_hoc", "decimal": ".",
    "line_type": "national", "line_level": "overall",
    "line_name": _LINES["overall"][0],
    "period": "2015", "reference_period": "2015/16",
    "tables": [
        _t4("extreme", r"^Food Poverty Line", r"^Lower Poverty Line"),
        _t4("other", r"^Lower Poverty Line", r"^Upper Poverty Line"),
        _t4("overall", r"^Upper Poverty Line", r"^Source|^2\.3"),
    ],
}


def _f_cols():
    """Annex F: LBPL P0 P1 P2 share | UBPL P0 P1 P2 share | households."""
    out = []
    for level in ("other", "overall"):
        name, vals = _LINES[level]
        common = {"line_level": level, "line_name": name, "line_value": vals["2003"], "line_unit": UNIT}
        out += [{"metric": m, **common} for m in ("headcount", "gap", "severity", "poor_share")]
    return out + [{"skip": True}]


_F = {"exact_numbers": True, "columns": _f_cols()}
REVIEW = {
    "survey": "NHIES 2003/04", "welfare_aggregate": "consumption",
    "unit_of_analysis": "household", "frequency": "ad_hoc", "decimal": ".",
    "line_type": "national", "line_level": "overall", "line_name": _LINES["overall"][0],
    "period": "2003", "reference_period": "2003/04",
    "tables": [
        {"page_contains": ["table f-1: incidence, depth and severity of poverty by region"], **_F,
         "row_scan": {"expect_rows": 13, "exclude_labels": ["Namibia", "Urban", "Rural"]}},
        {"page_contains": ["table f-1: incidence, depth and severity of poverty by region"], **_F,
         "rows": [{"match": r"^Namibia(?=\s)"},
                  {"match": r"^Urban(?=\s)", "topic": "locality", "locality": "urban", "locality_label": "Urban"},
                  {"match": r"^Rural(?=\s)", "topic": "locality", "locality": "rural", "locality_label": "Rural"}]},
        {"page_contains": ["table f-2: incidence, depth and severity of poverty by sex and age"], **_F,
         "start": r"^Sex of head of household", "end": r"^Age of head",
         "rows": [{"match": r"^Female(?=\s)", "topic": "sex_of_head", "characteristic": "Female", "sex": "female"},
                  {"match": r"^Male(?=\s)", "topic": "sex_of_head", "characteristic": "Male", "sex": "male"}]},
        {"page_contains": ["table f-2: incidence, depth and severity of poverty by sex and age"], **_F,
         "start": r"^Age of head of household", "end": r"^Namibia",
         "rows": label_rows("age_of_head", ["16-20", "21-24", "25-29", "30-34", "35-39", "40-44",
                                             "45-49", "50-54", "55-59", "60-64", "65+"])},
        {"page_contains": ["table f-24: incidence, depth and severity of poverty by highest level"], **_F,
         "join_wrapped_labels": True, "start": r"severity share households$",
         "end": r"^Namibia",
         "rows": label_rows("education_of_head", ["No formal education", "Primary education",
                                                   "Secondary education", "Tertiary education"])},
    ],
}

_kpi = make_parser(LAYOUT)
_review = make_parser(REVIEW)


def parse(path: str, extras: list[str] | None = None) -> pd.DataFrame:
    frames = [_kpi(path)]
    for ex in extras or []:
        if "review_poverty" in ex.lower():
            frames.append(_review(ex))
    return pd.concat(frames, ignore_index=True)
