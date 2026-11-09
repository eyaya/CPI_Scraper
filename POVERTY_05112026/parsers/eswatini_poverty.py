"""Eswatini -- "2009/10 Swaziland Household Income and Expenditure Survey.
Poverty in a decade of slow economic growth: Swaziland in the 2000's"
(Central Statistical Office with UNDP, February 2010 [sic: SHIES 2009/10]).

A Wayback `id_` copy of CSO's own file on its old swazistats.org.sz site
(www.gov.sz times out; the CSO's poverty report is not on any live host).

Both SHIES rounds on ONE line held fixed in real terms (January 2010
prices): E461 per adult equivalent per month (overall), food line E215
(extreme). Consumption per adult equivalent.

Appendix 1 (Tables A1.1-A1.5), each row
    label | population share | P0 | P1 | P2 | P1/P0 | C0 | C1 | C2
for 2000/01 and 2009/10 blocks: A1.1 regions + urban/rural; A1.2 the same on
the extreme line; A1.3 region x urban/rural; A1.4 main economic activity
(2009/10 only); A1.5 sex of head. C0/C1/C2 are each group's contribution to
national P0/P1/P2 (poor_share / gap_contribution / severity_contribution).
P1/P0 (income-gap ratio) has no schema metric and is not read.

CROSS-CHECK (verbatim): P0 69.0 -> 63.0, P1 32.4 -> 30.4, P2 18.4 -> 18.1;
extreme 30.0 -> 28.8; Shiselweni 82.0 -> 68.3; rural Lubombo 2009/10 76.2;
female-headed 71.9 -> 67.1; contributions sum to 100.0 in every block.
"""
from __future__ import annotations

import re

import pandas as pd

from . import _common as C

UNIT = "SZL per adult equivalent per month (January 2010 prices)"
_LINE = {"overall": ("National poverty line", 461), "extreme": ("Food (extreme) poverty line", 215)}
_ROUNDS = {"2000/01": ("SHIES 2000/01", "2000"), "2009/10": ("SHIES 2009/10", "2009")}
LAYOUT = {"survey": "SHIES 2009/10", "welfare_aggregate": "consumption", "unit_of_analysis": "person",
          "frequency": "ad_hoc", "decimal": ".", "line_type": "national", "line_level": "overall",
          "line_name": "National poverty line", "line_value": 461, "line_unit": UNIT,
          "period": "2009", "reference_period": "2009/10", "tables": []}
_ROW = re.compile(r"^([A-Z][A-Za-z -]+?) (\d+\.\d)((?: \d+\.\d){7})$")
REGIONS = ("Hhohho", "Manzini", "Shiselweni", "Lubombo")


def _table(pages, caption, level, kind):
    """Rows of one appendix table: (round, cut, values) for both year blocks."""
    text = next(t for t in pages if caption in t and "Source:" in t)
    text = text[text.index(caption):]
    nxt = re.search(r"\nTable A1\.\d", text[len(caption):])
    if nxt:
        text = text[:len(caption) + nxt.start()]
    out, rnd, section = [], None, None
    for ln in text.splitlines():
        s = ln.strip()
        if s in _ROUNDS:
            rnd = s
            continue
        if s in ("Region", "Area", "Urban", "Rural"):
            section = s
            continue
        m = _ROW.match(s)
        if not (m and rnd):
            continue
        lab = m.group(1)
        vals = [float(m.group(2))] + [float(x) for x in m.group(3).split()]
        if lab in ("Swaziland", "All"):
            cut = {}
        elif kind == "region":
            if lab in REGIONS:
                cut = {"geography": lab}
            elif lab in ("Urban", "Rural"):
                cut = {"topic": "locality", "locality": lab.lower(), "locality_label": lab}
            else:
                continue
        elif kind == "region_area":
            cut = {"geography": lab, "topic": "locality", "locality": section.lower(),
                   "locality_label": section}
        elif kind == "activity":
            cut = {"topic": "employment_of_head", "characteristic": lab}
        else:   # sex of head
            cut = {"topic": "sex_of_head", "characteristic": lab, "sex": lab.lower()}
        out.append((rnd, cut, vals))
    return out


def parse(path: str) -> pd.DataFrame:
    import pdfplumber
    with pdfplumber.open(path) as pdf:
        pages = [p.extract_text() or "" for p in pdf.pages]
    specs = [("Table A1.1: Indices of poverty by area and administrative region", "overall", "region"),
             ("Table A1.2: Indices of extreme poverty by area and administrative region", "extreme", "region"),
             ("Table A1.3: Indices of poverty by area/region", "overall", "region_area"),
             ("Table A1.4: Indices of poverty by main economic activity", "overall", "activity"),
             ("Table A1.5: Indices of poverty, by Gender of Household Head", "overall", "sex")]
    rows, seen = [], set()
    for cap, level, kind in specs:
        got = _table(pages, cap, level, kind)
        if not got:
            raise ValueError(f"Swaziland poverty profile: nothing read from {cap!r}")
        name, value = _LINE[level]
        for rnd, cut, (pop, p0, p1, p2, _ratio, c0, c1, c2) in got:
            survey, period = _ROUNDS[rnd]
            b = dict(survey=survey, welfare_aggregate="consumption", line_type="national",
                     line_level=level, line_name=name, line_value=value, line_unit=UNIT,
                     period=period, reference_period=rnd, frequency="ad_hoc")
            key = (rnd, level, tuple(sorted(cut.items())))
            if key in seen:          # the national row repeats in every table
                continue
            seen.add(key)
            metrics = [("headcount", p0), ("gap", p1), ("severity", p2)]
            if cut:
                metrics += [("population_share", pop), ("poor_share", c0),
                            ("gap_contribution", c1), ("severity_contribution", c2)]
            for metric, v in metrics:
                rows.append(C.row(metric=metric, value=v, **b, **cut))
    df = pd.DataFrame.from_records(rows)
    if len(df) < 250:
        raise ValueError(f"Swaziland poverty profile: {len(df)} rows, expected >= 250")
    return df
