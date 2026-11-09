"""Namibia -- further NSA poverty releases, one parser per file.

`parse_final` -- "Namibia Household Income and Expenditure Survey (NHIES)
2015/2016 Report" (NSA, the FINAL report; on nsa.org.na since 2024). Its
Table 11.2.2 REVISES the preliminary 2016 release that `namibia_poverty`
reads (2015/16 UBPL 17.4 vs 18.0 preliminary; 2009/10 28.8 vs 28.7; 2003/04
37.5 vs 37.7; food line 2003/04 11.0 vs 9.0), so every round from this table
carries "(final report 2018)" in `survey`, beside the preliminary figures.
  11.2.1  the three lines per adult equivalent per month, 2003/04-2015/16
  11.2.2  person headcount on FPL / LBPL / UBPL, three rounds
  11.2.3  P0 / P1 / P2 on the UBPL ("poor") and LBPL ("severely poor"), 2015/16
Sex of head, urban/rural and regional rates are charts only (11.2.1-11.2.3
figures) and are not read.

`parse_summary2009` -- "NHIES 2009/2010 Summary" (NSA, June 2012), Table 6:
share of HOUSEHOLDS that are poor (UBPL) and severely poor (LBPL), 2003/04
and 2009/10. Only 2009/10 is read: the 2003/04 values equal the 2008
review's (27.6 / 13.8), already collected with their line amounts.

Lines: FPL -> extreme, LBPL ("severely poor") -> other, UBPL ("poor") ->
overall, as in `namibia_poverty`.

CROSS-CHECK (verbatim): final 6.1 / 10.7 / 17.4 (2015/16); 7.2 / 15.4 / 28.8
(2009/10); P1 6.0 / 3.4, P2 2.9 / 1.5; households 2009/10 19.5 / 9.6.
"""
from __future__ import annotations

import re

import pandas as pd

from . import _common as C

UNIT = "NAD per adult equivalent per month"
_NAME = {"extreme": "Food poverty line (FPL)",
         "other": "Lower-bound poverty line (LBPL)",
         "overall": "Upper bound poverty line (UBPL, poor)"}
_ROUNDS = [("2003", "2003/04"), ("2009", "2009/10"), ("2015", "2015/16")]

LAYOUT_FINAL = {"survey": "NHIES 2015/16 (final report 2018)", "welfare_aggregate": "consumption",
                "unit_of_analysis": "person", "frequency": "ad_hoc", "decimal": ".",
                "line_type": "national", "line_level": "overall", "line_name": _NAME["overall"],
                "line_unit": UNIT, "period": "2015", "reference_period": "2015/16", "tables": []}
LAYOUT_SUMMARY = {**LAYOUT_FINAL, "survey": "NHIES 2009/10", "unit_of_analysis": "household",
                  "period": "2009", "reference_period": "2009/10"}


def _text(path):
    import pdfplumber
    with pdfplumber.open(path) as pdf:
        return "\n".join(p.extract_text() or "" for p in pdf.pages)


def _base(period, ref, level, value, survey, unit="person"):
    return dict(survey=survey, welfare_aggregate="consumption", unit_of_analysis=unit,
                line_type="national", line_level=level, line_name=_NAME[level],
                line_value=value, line_unit=UNIT if value != "" else "",
                period=period, reference_period=ref, frequency="ad_hoc")


def parse_final(path: str) -> pd.DataFrame:
    t = _text(path)
    lines = {}
    for lv, lab in (("extreme", "FPL"), ("other", "LBPL"), ("overall", "UBPL")):
        m = re.search(rf"^{lab} \([^)]*\) ([\d.]+) ([\d.]+) ([\d.]+)$", t, re.M)
        lines[lv] = [float(x) for x in m.groups()]
    rows = []
    blk = t[t.rindex("Table 11.2.2 Selected inequality and poverty estimates"):]
    for lv, head in (("extreme", "FOOD POVERTY LINE"), ("other", "LOWER POVERTY LINE"),
                     ("overall", "UPPER POVERTY LINE")):
        m = re.search(rf"{head}\nHeadcount ratio \(%\) ([\d.]+) ([\d.]+) ([\d.]+) ", blk)
        for k, ((p, r), v) in enumerate(zip(_ROUNDS, m.groups())):
            rows.append(C.row(metric="headcount", value=float(v),
                              **_base(p, r, lv, lines[lv][k], f"NHIES {r} (final report 2018)")))
    blk = t[t.rindex("Table 11.2.3 Incidence, depth and severity of poverty"):]
    for lab, lv in (("Poor", "overall"), ("Severely poor", "other")):
        m = re.search(rf"^{lab} ([\d.]+)% ([\d.]+)% ([\d.]+)$", blk, re.M)
        b = _base("2015", "2015/16", lv, lines[lv][2], "NHIES 2015/16 (final report 2018)")
        for metric, v in zip(("headcount", "gap", "severity"), m.groups()):
            rows.append(C.row(metric=metric, value=float(v), **b))
    df = pd.DataFrame.from_records(rows)
    key = ["survey", "line_level", "metric", "period"]
    df = df.drop_duplicates(key)       # 11.2.3's P0 repeats 11.2.2's 2015/16 headcount
    if len(df) != 9 + 4:
        raise ValueError(f"NHIES 2015/16 final report: {len(df)} rows, expected 13")
    return df


def parse_summary2009(path: str) -> pd.DataFrame:
    t = _text(path)
    rows = []
    for lab, lv in (("Severely poor households", "other"), ("Poor households \\(incl. severely poor\\)", "overall")):
        m = re.search(rf"^{lab} - ([\d.]+)% ([\d.]+)%$", t, re.M)
        for (p, r), v in zip(_ROUNDS[:2], m.groups()):
            if p == "2003":
                continue    # = the 2008 review's figure, already collected with its line
            rows.append(C.row(metric="headcount", value=float(v),
                              **_base(p, r, lv, "", f"NHIES {r}", unit="household")))
    if len(rows) != 2:
        raise ValueError("NHIES 2009/10 summary Table 6: rows not found")
    return pd.DataFrame.from_records(rows)
