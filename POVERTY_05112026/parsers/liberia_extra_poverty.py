"""Liberia -- LISGIS "Household Income and Expenditure Survey 2014:
Statistical Abstract" (March 2016), chapter 3.

Three measures, as in HIES 2016: absolute (overall) poverty, FOOD poverty
(food consumption below the food line) and EXTREME poverty (total
consumption below the food line). Table 3-1: rates for Liberia, rural/urban
and six regions; Table 3-2: numbers of poor (counts printed with stray
spaces, "1,622 ,501" -- re-joined); Table 3-3: by sex, age, education and
employment sector of the head, with each group's population share.

LISGIS's caveats, carried in the notes: fieldwork stopped in August 2014 at
about half the sample (Ebola), during the pre-harvest lean season -- no
county estimates (except Montserrado as a region), rates "likely slightly
higher than the true percentages", and NOT comparable with CWIQ 2007/2010
or with HIES 2016 (different recall periods and consumption module).
The 15-19 age group (36 observations, flagged in the report) is kept as
printed.
"""
from __future__ import annotations

import re

import pandas as pd

from . import _common as C

_LINES = [
    {"line_level": "overall", "line_name": "Absolute poverty line 2014"},
    {"line_level": "other", "line_name": "Food poverty (food consumption below the food poverty line)"},
    {"line_level": "extreme", "line_name": "Food poverty line 2014 (total consumption)"},
]
LAYOUT = {"survey": "HIES 2014 (incomplete, Ebola)", "welfare_aggregate": "consumption",
          "unit_of_analysis": "person", "frequency": "ad_hoc", "line_type": "national",
          **_LINES[0], "period": "2014", "reference_period": "2014 (Jan-Aug)", "tables": []}
_REGIONS = ["Montserrado", "North Central", "North Western", "South Central",
            "South Eastern A", "South Eastern B"]


def _row(line, metric, value, **cell):
    return C.row(metric=metric, value=value, survey=LAYOUT["survey"], welfare_aggregate="consumption",
                 line_type="national", line_level=line["line_level"], line_name=line["line_name"],
                 period="2014", reference_period=LAYOUT["reference_period"], frequency="ad_hoc",
                 unit_of_analysis="person",
                 topic=cell.get("topic", "total"), characteristic=cell.get("characteristic", "Total"),
                 geography=cell.get("geography", "Total country"),
                 locality=cell.get("locality", "all"), locality_label=cell.get("locality_label", "Total"))


def _cell(lab):
    if lab == "Liberia":
        return {}
    if lab in ("Rural", "Urban"):
        return {"topic": "locality", "locality": lab.lower(), "locality_label": lab}
    if lab in _REGIONS:
        return {"geography": lab}
    return None


def parse(path: str) -> pd.DataFrame:
    import pdfplumber
    with pdfplumber.open(path) as pdf:
        pages = [(p.extract_text() or "") for p in pdf.pages]
    rows = []
    p31 = [p for p in pages if "Table 3-1 Poverty levels by geographic characteristics" in p][-1]   # last: the list of tables repeats it
    for ln in p31.splitlines():
        m = re.match(r"^([A-Za-z][A-Za-z ]*?)\s+(\d+\.\d)\s+(\d+\.\d)\s+(\d+\.\d)$", ln.strip())
        if m and _cell(m.group(1)) is not None:
            for line, v in zip(_LINES, m.groups()[1:]):
                rows.append(_row(line, "headcount", float(v), **_cell(m.group(1))))
    p32 = [p for p in pages if "Table 3-2 Total numbers of poor by geographic" in p][-1]   # last: the list of tables repeats it
    for ln in p32.splitlines():
        s = re.sub(r"(?<=\d)\s+,", ",", ln.strip())          # "1,622 ,501"
        s = re.sub(r"(?<=,)\s+(?=\d)", "", s)                # "407, 173"
        # a comma group has exactly three digits: "84,5 57" -> "84,557"
        while True:
            t = re.sub(r",(\d{1,2})\s+(\d)", r",\1\2", s)
            if t == s:
                break
            s = t
        m = re.match(r"^([A-Za-z][A-Za-z ]*?)\s+([\d,]+)\s+([\d,]+)\s+([\d,]+)\s+([\d,]+)$", s)
        if m and _cell(m.group(1)) is not None:
            for line, v in zip(_LINES, m.groups()[2:]):
                if not re.fullmatch(r"\d{1,3}(,\d{3})+", v):
                    raise ValueError(f"Table 3-2: unreadable count {v!r} on {ln!r}")
                rows.append(_row(line, "poor_count", float(v.replace(",", "")), **_cell(m.group(1))))
    p33 = [p for p in pages if "Table 3-3 Poverty levels by characteristics of household head" in p][-1]   # last: the list of tables repeats it
    topic, pend = None, ""
    heads = {"Sex of household head": "sex_of_head", "Age of household head": "age_of_head",
             "Highest education level attained of household head": "education_of_head",
             "Employment sector of household head": "employment_of_head"}
    for ln in p33[p33.index("Table 3-3"):].splitlines():
        s = ln.strip()
        for h, t in heads.items():
            if s.startswith(h):
                topic, pend = t, ""
        m = re.match(r"^(.+?)\*?\s+(\d+\.\d)\s+(\d+\.\d)\s+(\d+\.\d)\s+(\d+\.\d)$", s)
        if not m or topic is None:
            if topic == "employment_of_head" and s and not re.search(r"\d", s) and not s.startswith("Employment"):
                pend = s
            if s.startswith("* category"):
                break
            continue
        lab = m.group(1).strip()
        if lab.startswith("agriculture)") or lab.startswith("employment"):
            pass
        if pend and topic == "employment_of_head":
            lab = f"{pend} {lab}".strip()
            pend = ""
        if lab.startswith("Sex of household head"):
            lab = lab[len("Sex of household head"):].strip()
        lab = lab.replace("15 – 19", "15-19").replace("20 - 29", "20-29").replace("30 - 39", "30-39") \
                 .replace("40 - 49", "40-49").replace("50 - 59", "50-59")
        lab = lab.replace("(non- agriculture)", "(non-agriculture)")
        cell = {"topic": topic, "characteristic": lab}
        if topic == "sex_of_head":
            cell["sex"] = lab.lower()
        v = [float(x) for x in m.groups()[1:]]
        rows.append({**_row(_LINES[0], "population_share", v[0], **{k: x for k, x in cell.items() if k != "sex"}),
                     "sex": cell.get("sex", "total")})
        for line, x in zip(_LINES, v[1:]):
            r = _row(line, "headcount", x, **{k: y for k, y in cell.items() if k != "sex"})
            r["sex"] = cell.get("sex", "total")
            rows.append(r)
    df = pd.DataFrame(rows)
    if len(df) < 90:
        raise ValueError(f"{path}: {len(df)} rows")
    return df
