"""Zimbabwe -- "Zimbabwe Poverty Update 2017-19" (JOINT REPORT, ZIMSTAT and
World Bank, hosted on zimstat.co.zw under Poverty_Statistics).

The Mini-PICES 2019 is ZIMSTAT's survey (PICES Technical Committee chaired
by ZIMSTAT, per the Foreword); consumption is partly imputed (SWIFT /
"hybrid survey"), and the 2017 PICES is REBASED onto new lines. Both carry
that in `survey`, so neither can pass for the PICES 2017 report's own
figures (`zimbabwe_poverty`), which stay as published.

Rebased lines (Table 3.1 / 4.1), US$ per person per month: food (extreme)
29.80, lower bound 45.60, upper bound 66.10 -> line_level extreme / other /
overall, the FPL/LBPL/UBPL mapping used for Namibia and South Africa.

Collected
  4.1  rebased 2017 P0 on all three lines, national / rural / urban (the
       "old method" columns repeat the PICES 2017 report and are not read)
  4.2  95% confidence limits of the extreme P0, 2017 (rebased) and Apr-May
       2019 -- the 2019 POINT estimates are printed only as chart labels
       (Figure 4.1) and are not read
  4.3  extreme poverty gap, 2017 and 2019, national / rural / urban
  4.5  extreme P0 by education completed (individuals), 2017 and 2019
Not collected: Table 4.6 (simulated December 2019), Figures 4.1 / E.1
(chart labels), the US$ deficits, Gini (inequality).

CROSS-CHECK (verbatim): rebased 2017 food / lower / upper 30.4 / 54.2 / 70.4;
rural 43.4 / 71.6 / 86.8; urban 3.9 / 15.9 / 34.5; extreme gap 7.8 -> 12.8;
2019 extreme CI 30.1-40.4; secondary-educated extreme 21 -> 30.
"""
from __future__ import annotations

import re

import pandas as pd

from . import _common as C

UNIT = "USD per person per month"
_LINES = {"extreme": ("Food poverty line (FPL, rebased)", 29.80),
          "other": ("Lower-bound poverty line (LBPL)", 45.60),
          "overall": ("Upper-bound poverty line (UBPL, rebased)", 66.10)}
_S17 = ("PICES 2017 (rebased; Poverty Update 2017-19, ZIMSTAT/World Bank)", "2017", "2017")
_S19 = ("Mini-PICES 2019, Apr-May (SWIFT-assisted; Poverty Update 2017-19, ZIMSTAT/World Bank)",
        "2019", "Apr-May 2019")
_LOC = {"Whole country": {}, "National": {},
        "Rural": {"topic": "locality", "locality": "rural", "locality_label": "Rural"},
        "Urban": {"topic": "locality", "locality": "urban", "locality_label": "Urban"}}

LAYOUT = {"survey": _S17[0], "welfare_aggregate": "consumption", "unit_of_analysis": "person",
          "frequency": "ad_hoc", "decimal": ".", "line_type": "national", "line_level": "extreme",
          "line_name": _LINES["extreme"][0], "line_unit": UNIT, "period": "2017",
          "reference_period": "2017", "tables": []}


def _b(s, level):
    name, value = _LINES[level]
    return dict(survey=s[0], welfare_aggregate="consumption", line_type="national",
                line_level=level, line_name=name, line_value=value, line_unit=UNIT,
                period=s[1], reference_period=s[2], frequency="ad_hoc")


def _table(text, caption):
    i = text.rindex(caption)          # the last occurrence; the first is the list of tables
    j = text.index("Source:", i)
    return text[i:j].splitlines()


def parse(path: str) -> pd.DataFrame:
    import pdfplumber
    with pdfplumber.open(path) as pdf:
        text = "\n".join(p.extract_text() or "" for p in pdf.pages)
    rows = []
    n = r"(\d+\.\d)"
    for ln in _table(text, "Poverty Rates for 2017 Using ZIMSTAT"):
        m = re.match(rf"^(Whole country|Rural|Urban) \(%\) {n} (N\.A\.|{n[1:-1]}) {n} {n} {n} {n}$", ln)
        if m:
            c = _LOC[m.group(1)]
            for level, v in zip(("extreme", "other", "overall"), m.groups()[4:7]):
                rows.append(C.row(metric="headcount", value=float(v), **_b(_S17, level), **c))
    for ln in _table(text, "Extreme Poverty in 2017–19: Confidence Intervals"):
        m = re.match(rf"^(National|Rural|Urban) \(%\) {n} {n} {n} {n}$", ln)
        if m:
            c = _LOC[m.group(1)]
            lo17, hi17, lo19, hi19 = (float(x) for x in m.groups()[1:])
            for s, lo, hi in ((_S17, lo17, hi17), (_S19, lo19, hi19)):
                rows.append(C.row(metric="headcount_ci_low", value=lo, **_b(s, "extreme"), **c))
                rows.append(C.row(metric="headcount_ci_high", value=hi, **_b(s, "extreme"), **c))
    for ln in _table(text, "Extreme Poverty Gap and Extreme Poverty Deficit"):
        m = re.match(rf"^(Whole country|Rural|Urban) \(%\) {n} {n}$", ln)
        if m:
            c = _LOC[m.group(1)]
            for s, v in ((_S17, m.group(2)), (_S19, m.group(3))):
                rows.append(C.row(metric="gap", value=float(v), **_b(s, "extreme"), **c))
    for ln in _table(text, "Extreme Poverty Rate by Educational Achievement of Individuals"):
        m = re.match(r"^(None|Primary|Secondary|Tertiary) (\d+) (\d+) -?\d+$", ln)
        if m:
            c = {"topic": "education", "characteristic": m.group(1)}
            for s, v in ((_S17, m.group(2)), (_S19, m.group(3))):
                rows.append(C.row(metric="headcount", value=float(v), **_b(s, "extreme"), **c))
    df = pd.DataFrame.from_records(rows)
    if len(df) != 9 + 12 + 6 + 8:
        raise ValueError(f"Zimbabwe Poverty Update: {len(df)} rows, expected 35")
    return df
