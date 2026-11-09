"""Tanzania (Mainland) -- HBS 1991/92, 2000/01, 2007 and 2011/12, beside HBS 2017/18.

Three NBS publications, each its own descriptor (Wayback `id_` copies of NBS's
own files; the old nbs.go.tz/nbs/takwimu/hbs/ tree is gone from the live site):

* `parse` -- "HBS 2000/01 Key Findings":
    Table 9   food and basic-needs P0 by stratum (Dar es Salaam, other urban,
              rural, Mainland), 1991/92 and 2000/01.
    Table 10  % of the poor by stratum (basic needs), 1991/92 and 2000/01.
    Selected indicators by region (p. 23): food and basic-needs P0 for the 20
              regions, 2000/01, printed as WHOLE NUMBERS. The region header is
              rotated text, so the column order is taken from its reading order
              (Dodoma ... Mara, then Mainland) and confirmed by the report's own
              prose: Lindi, Mara, Singida, Shinyanga poorest; Dar es Salaam and
              Mbeya least poor; Mainland 36 = Table 9's 35.7.
* `parse_2007` -- "HBS 2007 Report" (2009):
    Table 7.2 food and basic-needs P0 by stratum, 1991/92, 2000/01, 2007.
    Table 7.3 population share and % of the poor (both lines), 2000/01, 2007.
    Tables 8.1, 8.3, 8.7  P0 and % of the poor by household size, sex and
              education of the head, 1991/92, 2000/01, 2007.
    Line values from Table 7.1 (Mainland, TZS per adult equivalent per 28 days).
* `parse_2011` -- "HBS 2011/12 Poverty Key Findings" (zip on the NBS site):
    Tables 1-3: basic-needs and food P0 by area, poverty gap by area, P0 and
    distribution of the poor by children aged 0-6 and by household size.

TWO METHODS, TWO LINE NAMES: 1991/92-2007 use the 2000/01 lines inflated by a
Fisher index; 2011/12 introduced a new line, and NBS says the 2007 and 2011/12
rates are NOT strictly comparable. NBS's 2020 "Poverty trend 1991-2020"
leaflet prints a re-estimated 2007 (34.4) in a chart, and a 2020 PROJECTION;
neither is collected (chart-only / modelled). Geography is "Tanzania
Mainland" (the HBS excludes Zanzibar), as in the 2017/18 rows.

CROSS-CHECK (verbatim): basic needs 38.6 / 35.7 / 33.6 (1991/92, 2000/01,
2007), food 21.6 / 18.7 / 16.6; 2011/12 28.2 (food 9.7, gap 6.7); Dar es
Salaam 2011/12 4.2; 2000/01 regions Singida 55, Lindi 53, Dar es Salaam 18.
"""
from __future__ import annotations
import re

import pandas as pd

from . import _common as C
from . import poverty_tables as T

_BN = {"line_level": "overall", "line_name": "Basic needs poverty line (NBS, HBS 2000/01 basis)"}
_FD = {"line_level": "extreme", "line_name": "Food poverty line (NBS, HBS 2000/01 basis)"}
_BN12 = {"line_level": "overall", "line_name": "Basic needs poverty line (NBS, HBS 2011/12)",
         "line_value": 36482, "line_unit": "TZS per adult equivalent per month"}
_FD12 = {"line_level": "extreme", "line_name": "Food poverty line (NBS, HBS 2011/12)",
         "line_value": 26085, "line_unit": "TZS per adult equivalent per month"}
_LINEVAL = {("1991", "overall"): 2777, ("1991", "extreme"): 2083,
            ("2000", "overall"): 7253, ("2000", "extreme"): 5295,
            ("2007", "overall"): 13998, ("2007", "extreme"): 10219}
_ROUND = {"1991": ("HBS 1991/92", "1991/92"), "2000": ("HBS 2000/01", "2000/01"),
          "2007": ("HBS 2007", "2007"), "2011": ("HBS 2011/12", "2011/12")}
_NAT = "Tanzania Mainland"
_STRATA = {"Dar es Salaam": {"geography": "Dar es Salaam"},
           "Other urban": {"geography": _NAT, "topic": "locality", "locality": "other",
                           "locality_label": "Other urban areas"},
           "Rural": {"geography": _NAT, "topic": "locality", "locality": "rural",
                     "locality_label": "Rural areas"},
           "Mainland": {"geography": _NAT}}
_REGIONS_2001 = ["Dodoma", "Arusha", "Kilimanjaro", "Tanga", "Morogoro", "Pwani", "Dar es Salaam",
                 "Lindi", "Mtwara", "Ruvuma", "Iringa", "Mbeya", "Singida", "Tabora", "Rukwa",
                 "Kigoma", "Shinyanga", "Kagera", "Mwanza", "Mara"]

LAYOUT = {"survey": "HBS 2000/01", "welfare_aggregate": "consumption", "unit_of_analysis": "person",
          "frequency": "ad_hoc", "decimal": ".", "line_type": "national", **_BN,
          "period": "2000", "reference_period": "2000/01", "tables": []}
LAYOUT_2007 = {**LAYOUT, "survey": "HBS 2007", "period": "2007", "reference_period": "2007"}
LAYOUT_2011 = {**LAYOUT, **_BN12, "survey": "HBS 2011/12", "period": "2011",
               "reference_period": "2011/12"}


def _base(year: str, line: dict, **kw) -> dict:
    survey, ref = _ROUND[year]
    lv = dict(line)
    if "line_value" not in lv:
        lv["line_value"] = _LINEVAL.get((year, lv["line_level"]), "")
        lv["line_unit"] = "TZS per adult equivalent per 28 days" if lv["line_value"] else ""
    d = dict(survey=survey, welfare_aggregate="consumption", unit_of_analysis="person",
             line_type="national", period=year, reference_period=ref, frequency="ad_hoc",
             geography=_NAT, **lv)
    d.update(kw)
    return d


_N = r"\d+(?:\.\d+)?"


def _page(pages, pat):
    for p in pages:
        if re.search(pat, p, re.I) and len(re.findall(r"\.{8,}", p)) < 5:
            return p
    raise ValueError(f"not found: {pat!r}")


def _vals(line: str) -> list[float]:
    return [float(x.replace(",", "")) for x in re.findall(r"\d[\d,]*(?:\.\d+)?", line)]


def parse(path: str) -> pd.DataFrame:
    """HBS 2000/01 Key Findings."""
    P = T._pages(path, halves=False)["full"]
    out = []
    t9 = _page(P, r"TABLE 9 PERCENTAGE OF THE POPULATION IN POVERTY")
    strata = ["Dar es Salaam", "Other urban", "Rural", "Mainland"]
    for lab, line in (("Food poverty", _FD), ("Basic needs poverty", _BN)):
        ln = next(l for l in t9.splitlines() if l.startswith(lab))
        v = _vals(ln)
        if len(v) != 8:
            raise ValueError(f"Table 9 {lab}: {v}")
        for k, s in enumerate(strata):
            for j, y in enumerate(("1991", "2000")):
                out.append(C.row(metric="headcount", value=v[2 * k + j], **{**_base(y, line), **_STRATA[s]}))
    ln = next(l for l in t9.splitlines() if l.startswith("% of the poor"))
    v = _vals(ln)
    for k, s in enumerate(strata[:3]):
        for j, y in enumerate(("1991", "2000")):
            out.append(C.row(metric="poor_share", value=v[2 * k + j], **{**_base(y, _BN), **_STRATA[s]}))
    reg = _page(P, r"% of population below basic needs poverty line")
    for lab, line in (("% of population below food poverty line", _FD),
                      ("% of population below basic needs poverty line", _BN)):
        ln = next(l for l in reg.splitlines() if l.startswith(lab))
        v = _vals(ln[len(lab):])
        if len(v) != 21:
            raise ValueError(f"regions {lab}: {len(v)} values")
        if abs(v[20] - round([r for r in out if r["metric"] == "headcount" and r["period"] == "2000"
                               and r["geography"] == _NAT and r["topic"] == "total"
                               and r["line_level"] == line["line_level"]][0]["value"])) > 0.5:
            raise ValueError("regional table's Mainland column does not match Table 9")
        for name, x in zip(_REGIONS_2001, v[:20]):
            if name == "Dar es Salaam":
                continue      # Table 9 prints Dar es Salaam to one decimal
            out.append(C.row(metric="headcount", value=x, **_base("2000", line, geography=name)))
    return pd.DataFrame(out)


def parse_2007(path: str) -> pd.DataFrame:
    """HBS 2007 Report."""
    P = T._pages(path, halves=False)["full"]
    out = []
    t72 = _page(P, r"Table 7\.2 Incidence and Depth of Poverty in Tanzania").splitlines()
    i = next(k for k, l in enumerate(t72) if l.startswith("Table 7.2"))
    strata = ["Dar es Salaam", "Other urban", "Rural", "Mainland"]
    line = None
    n = 0
    for ln in t72[i:]:
        if ln.startswith("Food"):
            line = _FD
        elif ln.startswith("Basic Needs"):
            line = _BN
        m = re.search(rf"(1991/92|2000/01|2007)\s+({_N})\s+({_N})\s+({_N})\s+({_N})\s*$", ln)
        if m and line:
            y = m.group(1)[:4]
            for s, v in zip(strata, m.groups()[1:]):
                out.append(C.row(metric="headcount", value=float(v), **{**_base(y, line), **_STRATA[s]}))
            n += 1
    if n != 6:
        raise ValueError(f"Table 7.2: expected 6 rows, got {n}")
    # Table 7.3
    t73 = _page(P, r"Table 7\.3\s+Distribution of the Poor in Tanzania")
    lines = t73.splitlines()
    share = next(l for l in lines if l.startswith("Share of population"))
    pv = _vals(share)
    food = basic = None
    after = False
    for l in lines:
        if l.startswith("Percentage of poor"):
            after = True
        elif after and l.startswith("Food Poverty"):
            food = _vals(l)
        elif after and l.startswith("Basic Needs"):
            basic = _vals(l)
    for k, s in enumerate(strata[:3]):
        for j, y in enumerate(("2000", "2007")):
            out.append(C.row(metric="population_share", value=pv[2 * k + j], **{**_base(y, _BN), **_STRATA[s]}))
            out.append(C.row(metric="poor_share", value=food[2 * k + j], **{**_base(y, _FD), **_STRATA[s]}))
            out.append(C.row(metric="poor_share", value=basic[2 * k + j], **{**_base(y, _BN), **_STRATA[s]}))
    # Tables 8.1 / 8.3 / 8.7 -- headcount and % of poor for 1991/92, 2000/01, 2007
    specs = [(r"Table 8\.1 Distribution of Poverty by Household Size", "household_size",
              [("1", None), ("2", None), ("3", None), ("4", None), ("5", None), ("6", None),
               ("7", None), ("8", None), ("9", None), ("10 or more", None)], r"^Total"),
             (r"Table 8\.3 Distribution of Poverty by Sex of Household Head", "sex_of_head",
              [("Male", "male"), ("Female", "female")], r"^Total"),
             (r"Table 8\.7 Distribution of Poverty by Education of the Household Head",
              "education_of_head", [("None", None), ("Adult educ. Only", None),
                                    ("Primary only", None), ("Above primary", None)], r"^Total")]
    for cap, topic, labels, end in specs:
        page = _page(P, cap).splitlines()
        i = next(k for k, l in enumerate(page) if re.search(cap, l))
        got = 0
        for l in page[i + 1:]:
            if re.match(end, l):
                break
            for lab, sex in labels:
                m = re.match(rf"^{re.escape(lab)}\s+((?:{_N}\s+){{5}}{_N})\s*$", l)
                if m:
                    v = [float(x) for x in m.group(1).split()]
                    for j, y in enumerate(("1991", "2000", "2007")):
                        extra = {"sex": sex} if sex else {}
                        b = _base(y, _BN, topic=topic, characteristic=lab, **extra)
                        out.append(C.row(metric="headcount", value=v[2 * j], **b))
                        out.append(C.row(metric="poor_share", value=v[2 * j + 1], **b))
                    got += 1
                    break
        if got != len(labels):
            raise ValueError(f"{cap}: expected {len(labels)} rows, got {got}")
    return pd.DataFrame(out)


def parse_2011(path: str) -> pd.DataFrame:
    """HBS 2011/12 Poverty Key Findings."""
    P = T._pages(path, halves=False)["full"]
    out = []
    strata = ["Dar es Salaam", "Other urban", "Rural", "Mainland"]
    t1 = _page(P, r"Table 1: Poverty Headcount Rates by Area").splitlines()
    for i, l in enumerate(t1):
        if l.startswith("Basic Needs Poverty"):
            v = _vals(l)
            for s, x in zip(strata, v):
                out.append(C.row(metric="headcount", value=x, **{**_base("2011", _BN12), **_STRATA[s]}))
        if l.startswith("Food Poverty"):
            v = _vals(l) or _vals(t1[i + 1])
            if len(v) != 4:
                raise ValueError(f"Table 1 food: {v}")
            for s, x in zip(strata, v):
                out.append(C.row(metric="headcount", value=x, **{**_base("2011", _FD12), **_STRATA[s]}))
    t2 = _page(P, r"Table 2: Poverty Gap Index by Area")
    l = next(x for x in t2.splitlines() if x.startswith("Poverty Gap Index "))
    for s, x in zip(strata, _vals(l)):
        out.append(C.row(metric="gap", value=x, **{**_base("2011", _BN12), **_STRATA[s]}))
    t3 = _page(P, r"Table 3: Poverty by Household Composition").splitlines()
    block, n = None, 0
    for l in t3:
        if l.startswith("Children aged 0 to 6"):
            block = "children"
            continue
        if l.startswith("Household size"):
            block = "size"
            continue
        m = re.match(rf"^(None|1 child|2 children|3 \+ children|[1-6]|7 \+)\s+({_N})\s+({_N})\s*$", l)
        if m and block:
            lab = m.group(1)
            if block == "children":
                kw = dict(topic="household_type", characteristic=f"Children aged 0 to 6: {lab}")
            else:
                kw = dict(topic="household_size", characteristic=lab.replace("7 +", "7+"))
            b = _base("2011", _BN12, **kw)
            out.append(C.row(metric="headcount", value=float(m.group(2)), **b))
            out.append(C.row(metric="poor_share", value=float(m.group(3)), **b))
            n += 1
    if n != 11:
        raise ValueError(f"Table 3: expected 11 rows, got {n}")
    return pd.DataFrame(out)
