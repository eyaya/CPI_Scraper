"""Botswana -- monetary poverty (Statistics Botswana, BMTHS 2015/16 Poverty Stats Brief, Jan 2018).

National line = the household-specific Poverty Datum Line (PDL): a basket cost
per household compared with its total consumption (incl. aid, in-kind, school
meals); no single amount is printed. Rounds: HIES 2002/03, BCWIS 2009/10,
BMTHS 2015/16 (the brief calls its results preliminary).

Collected:
  T1  strata x 3 rounds: persons' poverty headcount, HOUSEHOLD poverty
      incidence, number of persons below the PDL
  T2  census districts x 2009/10, 2015/16: headcount + number of poor (the
      table prints 26 rows although the survey text speaks of 27 census districts)
  T3  share of poor HOUSEHOLDS that are male / female headed, by stratum
  T5  persons below "one Dollar a day" (the text: $1.90 PPP) x 3 rounds
  T6/T7 poverty gap and severity, urban / rural / national, 2009/10 and
      2015/16, on the PDL and on the dollar line
STRATA ARE BOTSWANA'S OWN: Cities/towns and Urban villages are filed as
locality "other" with their label (not flattened into urban); T6/T7's
"Urban" is both together.
Not collected: T4 (poverty WITHOUT government aid -- a counterfactual
welfare aggregate, not a published line), Gini, consumption shares,
food-insecurity worry (Table 9).
TEXT FIX: counts are printed "41, 093" (comma, space); the space is removed
between a comma and a 3-digit group before reading.

CROSS-CHECK: national headcount 30.6 / 19.3 / 16.3; households 21.7 / 10.8 /
9.0; poor persons 337,410 (2015/16); Kweneng West 50.6; Sowa Town 5.0;
dollar-a-day 23.4 / 6.4 / 5.8; gap 6.2 -> 4.2; severity 2.9 -> 1.7.
"""
from __future__ import annotations

import re

import pandas as pd

from . import poverty_tables as T

PDL = "Poverty Datum Line (PDL)"
USD = "US$1.90 a day (2011 PPP), as 'one Dollar a day'"
R3 = [("2002", "2002/03", "HIES 2002/03"), ("2009", "2009/10", "BCWIS 2009/10"),
      ("2015", "2015/16", "BMTHS 2015/16")]
_ST = [{"match": r"^Cities/towns(?=\s)", "topic": "locality", "locality": "other", "locality_label": "Cities/towns"},
       {"match": r"^Urban villages(?=\s)", "topic": "locality", "locality": "other", "locality_label": "Urban villages"},
       {"match": r"^Rural areas(?=\s)", "topic": "locality", "locality": "rural", "locality_label": "Rural areas"},
       {"match": r"^National(?=\s)"}]


def _r(p, ref, s, **kw):
    return {"period": p, "reference_period": ref, "survey": s, **kw}


def _gap(page, line_kw, start, end):
    cols = []
    for m in ("gap", "severity"):
        for p, ref, s in R3[1:]:
            cols.append(_r(p, ref, s, metric=m, **line_kw))
    # T6 and T7 share a page and their row labels: each is bounded by its caption.
    return {"page_contains": [page], "exact_numbers": True, "columns": cols,
            "start": start, "end": end,
            "rows": [{"match": r"^Urban(?=\s)", "topic": "locality", "locality": "urban", "locality_label": "Urban"},
                     {"match": r"^Rural(?=\s)", "topic": "locality", "locality": "rural", "locality_label": "Rural"},
                     {"match": r"^National(?=\s)"}]}


LAYOUT = {
    "survey": "BMTHS 2015/16", "welfare_aggregate": "consumption",
    "unit_of_analysis": "person", "frequency": "ad_hoc", "decimal": ".",
    "line_type": "national", "line_level": "overall", "line_name": PDL,
    "period": "2015", "reference_period": "2015/16",
    "tables": [
        {"page_contains": ["table 1: poverty incidence by strata"], "exact_numbers": True,
         "columns": [c for p, ref, s in R3 for c in (
             _r(p, ref, s, metric="headcount"),
             _r(p, ref, s, metric="headcount", unit_of_analysis="household"),
             _r(p, ref, s, metric="poor_count"))],
         "rows": _ST},
        {"page_contains": ["table 2: poverty incidence by district"], "exact_numbers": True,
         "columns": [_r("2009", "2009/10", "BCWIS 2009/10", metric="headcount"),
                     _r("2009", "2009/10", "BCWIS 2009/10", metric="poor_count"),
                     _r("2015", "2015/16", "BMTHS 2015/16", metric="headcount"),
                     _r("2015", "2015/16", "BMTHS 2015/16", metric="poor_count")],
         "row_scan": {"expect_rows": 26, "exclude_labels": ["National"],
                      "label": r"^([A-Z][A-Za-z/ ]{2,40}?)\s+(?=\d)",
                      # the round header "BCWIS 2009/10 BMTHS 2015/16" carries 4 numbers too
                      "exclude_lines": r"BCWIS|BMTHS|…|\.{4,}"}},
        {"page_contains": ["table 3: percentage distribution of poor households by sex"],
         "exact_numbers": True,
         "columns": [c for p, ref, s in R3[1:] for c in (
             _r(p, ref, s, metric="poor_share", unit_of_analysis="household", topic="sex_of_head",
                characteristic="Male Headed", sex="male"),
             _r(p, ref, s, metric="poor_share", unit_of_analysis="household", topic="sex_of_head",
                characteristic="Female Headed", sex="female"),
             {"skip": True})],
         # The stratum is a locality here, the topic the head's sex.
         "rows": [{"match": r"^Cities/Towns(?=\s)", "locality": "other", "locality_label": "Cities/towns"},
                  {"match": r"^Urban Villages(?=\s)", "locality": "other", "locality_label": "Urban villages"},
                  {"match": r"^Rural areas(?=\s)", "locality": "rural", "locality_label": "Rural areas"},
                  {"match": r"^Total(?=\s)"}]},
        {"page_contains": ["table 5: proportion of persons living below ppp one dollar"],
         "exact_numbers": True,
         "columns": [c for p, ref, s in R3 for c in (
             _r(p, ref, s, metric="poor_count", line_type="international", line_level="other", line_name=USD),
             _r(p, ref, s, metric="headcount", line_type="international", line_level="other", line_name=USD))],
         "rows": [dict(r, match=r.get("match").replace("Cities/towns", "Cities/Towns")) for r in _ST]},
        _gap("table 6: poverty gap and severity of poverty", {}, r"^Table 6", r"^Table 7"),
        _gap("table 7: poverty gap and severity of poverty",
             {"line_type": "international", "line_level": "other", "line_name": USD},
             r"^Table 7", r"^2\.8"),
    ],
}


def parse(path: str) -> pd.DataFrame:
    pages = T._pages(path, halves=False)
    pages["full"] = [re.sub(r"(\d), (\d{3})\b", r"\1,\2", t) for t in pages["full"]]
    rows = []
    for tbl in LAYOUT["tables"]:
        got, matched = T._parse_table(pages, LAYOUT, tbl, LAYOUT["period"], LAYOUT["reference_period"])
        miss = [r["match"] for i, r in enumerate(tbl.get("rows", [])) if i not in matched]
        if miss:
            raise ValueError(f"botswana: row spec(s) matched nothing: {miss}")
        rows += got
    return pd.DataFrame(rows)
