"""Liberia -- monetary-poverty layout (LISGIS, "Household Income and
Expenditure Survey 2016: Statistical Abstract", chapter 3).

HIES 2016, fieldwork mid-January 2016 to mid-January 2017. Consumption per
adult equivalent; absolute (overall) line LD 65,383.58 and food line
LD 37,151.95 per adult equivalent per year (Annex A). THREE measures:
  absolute poverty  total consumption below the absolute line  -> overall
  extreme poverty   total consumption below the FOOD line      -> extreme
  food poverty      FOOD consumption below the food line       -> other
Only headcounts are published (no P1/P2).

Read:
  Table 3.1  the three headcounts for Liberia, rural/urban, 6 regions,
             14 counties (county "Monrovia/Montserrado" is the Montserrado
             region again, same figures -- read once, as the region)
  Table 3.2  numbers of poor on each measure, Liberia, rural/urban, regions
  Table 3.3  population share + the three headcounts by sex, age, education
             and employment sector of the household head
Tables continue across page breaks, so the document is read as one text.
NOT read: the half-year (Q1-Q2) 2014 vs 2016 comparison, which exists only
in Figures 6-7 and is a different measure (54.1 / 61.2 on the 2014 line).

CROSS-CHECK (verbatim): 50.9 / 39.1 / 16.5; rural 71.6, urban 31.5;
Maryland 84.0 / 71.5 / 47.5; 2,157,861 poor; female head 46.3; post-secondary
head 15.9; self-employed (agriculture) 79.6.
"""
from __future__ import annotations

import re

import pandas as pd

from . import poverty_tables as T
from ._vocab import label_rows

_N = r"(?=\s+\d)"
_UNIT = "LRD per adult equivalent per year"
_ABS = {"line_level": "overall", "line_name": "Absolute poverty line 2016",
        "line_value": 65383.58, "line_unit": _UNIT}
_EXT = {"line_level": "extreme", "line_name": "Food poverty line 2016 (total consumption)",
        "line_value": 37151.95, "line_unit": _UNIT}
_FOOD = {"line_level": "other", "line_name": "Food poverty (food consumption below the food poverty line)",
         "line_value": 37151.95, "line_unit": _UNIT}

_REGIONS = ["Montserrado", "North Central", "North Western", "South Central",
            "South Eastern A", "South Eastern B"]
_COUNTIES = ["Bomi", "Bong", "Grand Bassa", "Grand Cape Mount", "Grand Gedeh", "Grand Kru",
             "Lofa", "Margibi", "Maryland", "Nimba", "River Cess", "Sinoe", "River Gee", "Gbarpolu"]


def _geo_rows(names):
    return [{"match": "^" + re.escape(n) + _N, "geography": n} for n in names]


_TOP = [{"match": r"^Liberia" + _N},
        {"match": r"^Rural" + _N, "topic": "locality", "locality": "rural", "locality_label": "Rural"},
        {"match": r"^Urban" + _N, "topic": "locality", "locality": "urban", "locality_label": "Urban"}]

_THREE = [{"metric": "headcount", **_ABS}, {"metric": "headcount", **_FOOD},
          {"metric": "headcount", **_EXT}]
_COUNTS = [{"skip": True}, {"metric": "poor_count", **_ABS}, {"metric": "poor_count", **_FOOD},
           {"metric": "poor_count", **_EXT}]
_HEAD = [{"metric": "population_share"}] + _THREE


def _head(start, end, topic, labels, pats=None):
    rows = label_rows(topic, labels)
    for r, p in zip(rows, pats or []):
        if p:
            r["match"] = p
    return {"page_contains": ["table 3.3: poverty levels by characteristics of household head"],
            "start": start, "end": end, "exact_numbers": True, "columns": _HEAD, "rows": rows}


LAYOUT = {
    "survey": "HIES 2016", "welfare_aggregate": "consumption", "unit_of_analysis": "person",
    "frequency": "ad_hoc", "decimal": ".", "line_type": "national", **_ABS,
    "period": "2016", "reference_period": "2016",
    "tables": [
        {"page_contains": ["table 3.1: poverty levels by geographic characteristics",
                           "south eastern b"],
         "start": r"^Table 3\.1: Poverty levels(?!.*\.{4})", "end": r"^3\.4 Number of Poor",
         "exact_numbers": True, "columns": _THREE,
         "rows": _TOP + _geo_rows(_REGIONS + _COUNTIES)},
        {"page_contains": ["table 3.2: total numbers of poor"],
         "start": r"^Table 3\.2: Total numbers(?!.*\.{4})", "end": r"^3\.5 Poverty by",
         "exact_numbers": True, "columns": _COUNTS, "rows": _TOP + _geo_rows(_REGIONS)},
        {**_head(r"^Sex of household head", r"^Age of household head", "sex_of_head", []),
         "rows": [{"match": r"^Female" + _N, "topic": "sex_of_head", "characteristic": "Female", "sex": "female"},
                  {"match": r"^Male" + _N, "topic": "sex_of_head", "characteristic": "Male", "sex": "male"}]},
        _head(r"^Age of household head", r"^Highest education", "age_of_head",
              ["15-19", "20-29", "30-39", "40-49", "50-59", "60+"],
              [r"^15 \S+ 19" + _N, r"^20 \S+ 29" + _N, r"^30 \S+ 39" + _N, r"^40 \S+ 49" + _N,
               r"^50 \S+ 59" + _N, r"^60\+" + _N]),
        _head(r"^Highest education level", r"^Employment sector", "education_of_head",
              ["None", "Primary", "Secondary", "Post-secondary"]),
        _head(r"^Employment sector of household head", r"^The highest levels", "employment_of_head",
              ["Paid employee", "Self-employed (non-agriculture)", "Self-employed (agriculture)",
               "Not working / Unpaid employment"]),
    ],
}


def parse(path: str) -> pd.DataFrame:
    pages = T._pages(path, halves=False)
    # Tables 3.1 and 3.2 break across pages; read the chapter as one text,
    # without the running page numbers between the halves.
    doc = "\n".join(re.sub(r"\n\d{1,3}\n?$", "\n", p) for p in pages["full"])
    pages = {"full": [doc]}
    rows, misses = [], []
    for tbl in LAYOUT["tables"]:
        got, matched = T._parse_table(pages, LAYOUT, tbl, "2016", "2016")
        rows.extend(got)
        misses += [r["match"] for ri, r in enumerate(tbl["rows"]) if ri not in matched]
    if misses:
        raise ValueError(f"{len(misses)} Liberia row spec(s) matched nothing: {misses[:6]}")
    return pd.DataFrame.from_records(rows)
