"""Zimbabwe -- ICES 2001 poverty report (CSO, "Poverty in Zimbabwe", 2001
ICES, published April 2007; on zimstat.co.zw/Poverty_Statistics).

The PICES 2017 report (`zimbabwe_poverty`) republishes the 2001 NATIONAL
figures; this report adds the breakdowns. Survey label "ICES 2001 (2001
poverty report)" keeps its own estimates apart from the 2017 republication.

Lines: Total Poverty Line (TPL, upper -> overall) and Food Poverty Line
(FPL, lower -> extreme); P1 and P2 are FGT on the TPL. Consumption per
capita. Every table except 2.2.1's "People" block is HOUSEHOLDS.

Collected
  2.2.1  households and people x rural / urban / all: P0, extreme P0, P1, P2
  2.3.1  10 provinces (households): share of poor households, P0, extreme, P1, P2
  2.4.2  sex of head (male / female-headed) and the female-headed types
         (de facto, divorced, widowed, never married): P0, extreme, P1, P2
  2.4.3  P0 by main activity of the head x rural / urban / all
  2.4.4  P0 and extreme P0 by sector of employment of the head x rural / urban
  3.1.1  8 rural provinces: share of poor, P0, extreme, P1, P2
  3.1.2  rural land-use areas; 3.1.3 natural regions (rural): P0, extreme, P1, P2
  3.3.1  education of head: P0, extreme P0, P1, P2 -- printed as FRACTIONS
         (None 0.810) under a "(%)" caption: kept as printed, unit "index"
  3.3.2  P0 by education of head x rural / urban (percent)
Not collected: 2.4.5-2.4.8 (members' employment,
income source -- no topic); asset and energy tables; the "**" employer cell
in rural 2.4.3 is kept, as printed, with the report's own caution.

CROSS-CHECK (verbatim): households 60.6 / 32.2 / 28.3 / 16.5; people 70.9 /
41.5 / 35.4 / 21.4; Matabeleland North 75.4; Harare 29.3; resettlement areas
87.8; widowed female heads 72.4; 3.3.1 None 0.810 / 0.523 / 0.433 / 0.273,
post-secondary 0.150 / 0.027 / 0.043 / 0.018; 3.3.2 rural none 82.6, urban
post-secondary 11.0; provinces' shares of poor households sum to
100.1.
"""
from __future__ import annotations

import re

import pandas as pd

from . import _common as C

_S = ("ICES 2001 (2001 poverty report)", "2001", "2001")
_TPL, _FPL = "Total Consumption Poverty Line (TCPL)", "Food Poverty Line (FPL)"
PROVS = ["Manicaland", "Mashonaland Central", "Mashonaland East", "Mashonaland West",
         "Matabeleland North", "Matabeleland South", "Midlands", "Masvingo", "Bulawayo", "Harare"]
LAYOUT = {"survey": _S[0], "welfare_aggregate": "consumption", "unit_of_analysis": "household",
          "frequency": "ad_hoc", "decimal": ".", "line_type": "national", "line_level": "overall",
          "line_name": _TPL, "period": "2001", "reference_period": "2001", "tables": []}
_N = r"(\d+\.\d|N/A)"


def _b(level, unit="household"):
    return dict(survey=_S[0], welfare_aggregate="consumption", unit_of_analysis=unit,
                line_type="national", line_level=level,
                line_name=_TPL if level == "overall" else _FPL,
                period="2001", reference_period="2001", frequency="ad_hoc")


def _emit(rows, metric, v, level, cut, unit="household"):
    if v in (None, "N/A"):
        return
    rows.append(C.row(metric=metric, value=float(str(v).rstrip("*")), **_b(level, unit), **cut))


def _four(rows, vals, cut, unit="household"):
    p0, ext, p1, p2 = vals
    _emit(rows, "headcount", p0, "overall", cut, unit)
    _emit(rows, "headcount", ext, "extreme", cut, unit)
    _emit(rows, "gap", p1, "overall", cut, unit)
    _emit(rows, "severity", p2, "overall", cut, unit)


def _seg(text, caption, end="Source:"):
    i = text.rindex(caption)
    return text[i:text.index(end, i)].splitlines()


_LOC = {"Rural": {"topic": "locality", "locality": "rural", "locality_label": "Rural"},
        "Urban": {"topic": "locality", "locality": "urban", "locality_label": "Urban"},
        "All Zimbabwe": {}}


def _place(loc):
    """The rural/urban cut WITHOUT its topic, for a row whose topic is a characteristic."""
    return {k: v for k, v in _LOC[loc].items() if k != "topic"}


def parse(path: str) -> pd.DataFrame:
    import pdfplumber
    with pdfplumber.open(path) as pdf:
        text = "\n".join(p.extract_text() or "" for p in pdf.pages)
    rows = []
    unit = None
    for ln in _seg(text, "Table 2.2.1 Poverty Indices by Place of Residence"):
        if ln.strip() in ("Households", "People"):
            unit = "household" if ln.strip() == "Households" else "person"
        m = re.match(rf"^(Rural|Urban|All Zimbabwe) {_N} {_N} {_N} {_N}$", ln.strip())
        if m and unit:
            _four(rows, m.groups()[1:], _LOC[m.group(1)], unit)
    for ln in _seg(text, "Table 2.3.1 Household Poverty Indices by Province"):
        m = re.match(rf"^({'|'.join(PROVS)}) {_N} {_N} {_N} {_N} {_N}$", ln.strip())
        if m:
            c = {"geography": m.group(1)}
            _emit(rows, "poor_share", m.group(2), "overall", c)
            _four(rows, m.groups()[2:], c)
    for ln in _seg(text, "Table 2.4.2 Household Poverty by Household Headship"):
        m = re.match(rf"^(Male-headed|Female-headed|Defacto|Divorced|Widowed|Never Married) {_N} {_N} {_N} {_N}$", ln.strip())
        if m:
            lab = m.group(1)
            if lab in ("Male-headed", "Female-headed"):
                c = {"topic": "sex_of_head", "characteristic": lab,
                     "sex": "male" if lab.startswith("Male") else "female"}
            else:
                c = {"topic": "marital_status_of_head", "characteristic": f"Female-headed: {lab}",
                     "sex": "female"}
            _four(rows, m.groups()[1:], c)
    seg = _seg(text, "Table 2.4.3 Prevalence of Household Poverty by Main Activity")
    seg = [re.sub(r"^Communal/resettlement (\S+ \S+ \S+)$", r"Communal/resettlement own-account worker \1", l.strip())
           for l in seg]
    for ln in seg:
        m = re.match(r"^([A-Z][A-Za-z/ -]+?) (\d+\.\d)\*{0,2} (\d+\.\d) (\d+\.\d)$", ln)
        if m:
            for loc, v in zip(("Rural", "Urban", "All Zimbabwe"), m.groups()[1:]):
                _emit(rows, "headcount", v, "overall",
                      {"topic": "employment_of_head", "characteristic": m.group(1), **_place(loc)})
    seg = [l.strip() for l in _seg(text, "Table 2.4.4 Prevalence of Household Poverty by Sector")]
    for ln in seg:
        m = re.match(rf"^(Own-account|Government worker|Parastatal worker|Formal Sector|Informal Sector) {_N} {_N} {_N} {_N}$", ln)
        if m:
            lab = {"Own-account": "Own-account communal or resettlement farmer",
                   "Formal Sector": "Private formal sector",
                   "Informal Sector": "Private informal sector"}.get(m.group(1), m.group(1))
            vals = m.groups()[1:]
            for k, loc in enumerate(("Rural", "Urban")):
                c = {"topic": "employment_of_head", "characteristic": f"Sector: {lab}", **_place(loc)}
                _emit(rows, "headcount", vals[2 * k], "overall", c)
                _emit(rows, "headcount", vals[2 * k + 1], "extreme", c)
    for ln in _seg(text, "Table 3.1.1 Household Poverty by Province, Rural Zimbabwe"):
        m = re.match(rf"^({'|'.join(PROVS)}) {_N} {_N} {_N} {_N} {_N}$", ln.strip())
        if m:
            c = {"geography": m.group(1), **_LOC["Rural"]}
            _emit(rows, "poor_share", m.group(2), "overall", c)
            _four(rows, m.groups()[2:], c)
    for cap, rx, pref in (("Table 3.1.2 Rural Household Poverty Indices by Land Use Areas",
                           r"(Communal Areas|Small scale Commercial Farms|Large scale Commercial Farms|Resettlement Areas)", ""),
                          ("Table 3.1.3 Poverty by Natural Region in Rural Areas", r"(NR I|NR II|NR III|NR IV|NR V)", "Natural Region ")):
        for ln in _seg(text, cap):
            m = re.match(rf"^{rx} {_N} {_N} {_N} {_N}$", ln.strip())
            if m:
                lab = pref + m.group(1).replace("NR ", "") if pref else m.group(1)
                _four(rows, m.groups()[1:], {"topic": "locality", "locality": "rural", "locality_label": lab})
    # 3.3.1 prints FRACTIONS under a "(%)" caption (None 0.810 ...): kept as
    # printed, unit "index" (value_std puts them on the percent scale).
    i = text.index("Table 3.3.1: Poverty by Education of the Household Head")
    edu = r"(None|Primary School|Secondary School|Post-secondary)"
    n331 = 0
    for ln in text[i:text.index("Source:", i)].splitlines():
        m = re.match(rf"^{edu} (0\.\d{{3}}) (0\.\d{{3}}) (0\.\d{{3}}) (0\.\d{{3}})$", ln.strip())
        if m:
            c = {"topic": "education_of_head", "characteristic": m.group(1)}
            for metric, level, v in zip(("headcount", "headcount", "gap", "severity"),
                                        ("overall", "extreme", "overall", "overall"), m.groups()[1:]):
                rows.append(C.row(metric=metric, value=float(v), unit="index", **_b(level), **c))
            n331 += 1
    # 3.3.2: upper-line headcount by education of head x rural / urban (percent).
    i = text.index("Table 3.3.2: Prevalence of Household Poverty by Household Head")
    n332 = 0
    for ln in text[i:text.index("Source:", i)].splitlines():
        m = re.match(r"^(None|Primary School|Secondary School|Post-secondary School) (\d+\.\d) (\d+\.\d)$", ln.strip())
        if m:
            lab = "Post-secondary" if m.group(1).startswith("Post") else m.group(1)
            for loc, v in zip(("Rural", "Urban"), m.groups()[1:]):
                _emit(rows, "headcount", v, "overall",
                      {"topic": "education_of_head", "characteristic": lab, **_place(loc)})
            n332 += 1
    if (n331, n332) != (4, 4):
        raise ValueError(f"Zimbabwe ICES 2001 education tables: {n331} / {n332} rows of 4")
    df = pd.DataFrame.from_records(rows)
    want = 24 + 50 + 24 + 21 + 18 + 40 + 36 + 16 + 8
    if len(df) < want - 4:
        raise ValueError(f"Zimbabwe ICES 2001: {len(df)} rows, expected about {want}")
    return df
