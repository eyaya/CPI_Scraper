"""Sierra Leone -- "A Poverty Profile for Sierra Leone" (2014; statistics.sl/
images/StatisticsSL/Documents/poverty_profile_for_sierra_leone.pdf).

JOINT WORK of Statistics Sierra Leone and the World Bank PREM unit ("Tasks
undertaken jointly include ... the construction of the consumption aggregate,
the development of a poverty line ... and the calculation of poverty
statistics", para 1.3), hosted on Stats SL's own site -- the joint-report
rule applied to the Zimbabwe 2017-19 update and the Seychelles HBS reports.

It re-estimates BOTH SLIHS rounds on one method (a 2003 line inflated to 2011
by the national CPI): SLIHS 2003/04 (fieldwork March 2003 - April 2004) and
SLIHS 2011 (January - December 2011). Survey labels "... (Poverty Profile
2014)" keep them apart from the SLIHS 2011 report's originals (2011: 53.9
there, 52.9 here) and the 2018 report's comparable-aggregate re-estimate.
Total poverty line only (the overall line; the food and extreme lines are
described but not tabulated); consumption per adult equivalent; people.

Collected
  A1 (2003), A2 (2011): P0, P1, P2, % of population, contribution to P0 /
     P1 / P2, number of poor -- national, 4 regions, 14 districts, rural /
     urban / Freetown / other urban. Column order proven by identity:
     contribution_k = population share x P_k / national P_k (Western urban
     2011: 16.6 x 20.7 / 52.9 = 6.5, printed 6.5). Gini and population size
     are not poverty measures and are left out.
  A5 (2011): P0, P1, P2 by sex and education of the household head.
Not collected: A5's geography and district rows (they repeat A2; the
geography rows are printed as fractions, 0.661 = A2's 66.1), its standard
errors (no metric), the regressions A3/A4, charts.

Names follow the other Sierra Leone outputs: regions East / North / South /
West; "Porto Loko" (sic, A1/A2) -> Port Loko; Western rural -> Western Area
Rural; Western urban -> Freetown (the district; identical values to the
"Freetown" area-of-residence row).

IDENTITIES: 2003 regional and rural + urban poor sum to the national
3,193,537 (districts 3,193,535). 2011 rural + urban sum to the national
3,090,961, but the four regions sum to 2,912,468 (and their population
sizes to 5,515,993 against 5,838,160): A2's own inconsistency, kept as
printed. Population shares and P0 contributions sum to 100 +/- 0.1.

CROSS-CHECK (verbatim): 2003 national 66.4 / 27.0 / 14.0, poor 3,193,537;
2011 national 52.9 / 16.1 / 6.7, poor 3,090,961; Tonkolili 2011 76.4;
Kailahun 2003 93.0; female heads 2011 49.8; no education 61.3.
"""
from __future__ import annotations

import re

import pandas as pd

from . import _common as C

_LINE = "Total poverty line (Poverty Profile 2014)"
_ROUND = {"A1": ("SLIHS 2003/04 (Poverty Profile 2014)", "2003", "2003/04"),
          "A2": ("SLIHS 2011 (Poverty Profile 2014)", "2011", "2011")}
LAYOUT = {"survey": _ROUND["A2"][0], "welfare_aggregate": "consumption",
          "unit_of_analysis": "person", "frequency": "ad_hoc", "decimal": ".",
          "line_type": "national", "line_level": "overall", "line_name": _LINE,
          "period": "2011", "reference_period": "2011", "tables": []}
_REGION = {"Eastern": "East", "Northern": "North", "Southern": "South", "Western": "West"}
_DISTRICT = {"Porto Loko": "Port Loko", "Western rural": "Western Area Rural",
             "Western urban": "Freetown"}
_AREA = {"Rural": dict(topic="locality", locality="rural", locality_label="Rural", characteristic="Rural"),
         "Urban": dict(topic="locality", locality="urban", locality_label="Urban", characteristic="Urban"),
         "Freetown": dict(topic="locality", locality="other", locality_label="Freetown",
                          characteristic="Freetown"),
         "Other urban": dict(topic="locality", locality="other", locality_label="Other urban",
                             characteristic="Other urban")}
_F = r"(\d+\.\d)"
_ROW = re.compile(rf"^([A-Z][A-Za-z ]+?) {_F} {_F} {_F} {_F} {_F} {_F} {_F} (0\.\d{{4}})"
                  rf"(?: ([\d,]+) ([\d,]+))?$")
_METRICS = ("headcount", "gap", "severity", "population_share", "poor_share",
            "gap_contribution", "severity_contribution")


def _base(survey, period, ref):
    return dict(survey=survey, welfare_aggregate="consumption", unit_of_analysis="person",
                line_type="national", line_level="overall", line_name=_LINE,
                period=period, reference_period=ref, frequency="ad_hoc")


def _table(text, cap, end, key):
    survey, period, ref = _ROUND[key]
    i = text.index(cap)
    seg = text[i:text.index(end, i)]
    # A1's national row wraps its two counts onto the next line, with a stray
    # space inside each ("4,808 ,019 3,193 ,537").
    seg = re.sub(r"(\d) ,(\d{3})", r"\1,\2", seg)
    seg = re.sub(r"(0\.\d{4})\n([\d,]+ [\d,]+)\n", r"\1 \2\n", seg)
    rows, region, n = [], None, 0
    for ln in (l.strip() for l in seg.splitlines()):
        if ln in _REGION:
            region = _REGION[ln]
            continue
        if ln == "Area of residence":
            region = "AREA"
            continue
        m = _ROW.match(ln)
        if not m:
            continue
        lab = m.group(1)
        if lab == "National":
            cut = {}
        elif region == "AREA":
            cut = _AREA[lab]
        elif lab == "Total":
            cut = {"geography": region}
        else:
            cut = {"geography": _DISTRICT.get(lab, lab)}
        for metric, v in zip(_METRICS, m.groups()[1:8]):
            rows.append(C.row(metric=metric, value=float(v), **_base(survey, period, ref), **cut))
        if m.group(11):  # groups 9-11: Gini, population size, number of poor
            rows.append(C.row(metric="poor_count", value=float(m.group(11).replace(",", "")),
                              **_base(survey, period, ref), **cut))
        n += 1
    if n != 1 + 4 + 14 + 4:
        raise ValueError(f"Sierra Leone profile {key}: {n} rows, expected 23")
    return rows


def _a5(text):
    """A5 prints each row's numbers on the line BEFORE its label."""
    survey, period, ref = _ROUND["A2"]
    i = text.rindex("Table A5 : Poverty Statistics (2011)")  # not the list of tables
    lines = [l.strip() for l in text[i:text.index("Table A6", i)].splitlines()]
    topic = {"Gender of Household Head": "sex_of_head", "Education": "education_of_head"}
    labels = {"sex_of_head": ("Male", "Female"),
              "education_of_head": ("No education", "Primary", "Junior", "Secondary", "Post-Secondary")}
    rows, cur, n = [], None, 0
    for k, ln in enumerate(lines):
        if ln in topic:
            cur = topic[ln]
            continue
        if ln in ("District", "Geography"):
            cur = None
            continue
        if cur and ln in labels[cur]:
            m = re.match(rf"^{_F} {_F} {_F} {_F} {_F} {_F}$", lines[k - 1])
            if not m:
                raise ValueError(f"Sierra Leone A5: no numbers above {ln!r}: {lines[k - 1]!r}")
            p0, _, p1, _, p2, _ = m.groups()
            cut = {"topic": cur, "characteristic": ln}
            if cur == "sex_of_head":
                cut["sex"] = "male" if ln == "Male" else "female"
            for metric, v in (("headcount", p0), ("gap", p1), ("severity", p2)):
                rows.append(C.row(metric=metric, value=float(v), **_base(survey, period, ref), **cut))
            n += 1
    if n != 7:
        raise ValueError(f"Sierra Leone A5: {n} rows, expected 7")
    return rows


def parse(path: str) -> pd.DataFrame:
    import pdfplumber
    with pdfplumber.open(path) as pdf:
        text = "\n".join(p.extract_text() or "" for p in pdf.pages)
    rows = (_table(text, "Table A1 : Total poverty (2003)\nPoverty", "Table A2", "A1")
            + _table(text, "Table A2 : Total poverty (2011)\nSeverity", "Table A3", "A2")
            + _a5(text))
    return pd.DataFrame.from_records(rows)
