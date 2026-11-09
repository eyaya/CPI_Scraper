"""Nigeria -- NBS poverty publications before the NLSS 2018/19 report.

`parse_profile2004` -- "Poverty Profile for Nigeria" (NBS, 2005), from the
NLSS 2003/04, with the National Consumer Survey (NCS) rounds 1980, 1985,
1992 and 1996 republished in its trend tables. Four measures, each its own
line (Appendix B):

  * RELATIVE (the 1996/97 study's method, NBS's headline at the time:
    54.4% in 2004): line_type relative. Appendix A Table 6 gives P0, P1, P2,
    population share and contribution C0 for the nation, urban/rural, six
    zones and 37 states; P1 and P2 are printed as 0-1 indices (unit index).
    Appendix A Table 1 adds the 1996 state rates; Tables 3.8 / 3.10 / 3.13 /
    3.14 add 1980-1996 (and 2004 where Table 6 does not already carry it) by
    sector, zone, education and occupation of the head.
    "Core poor" (Tables 1.6, 3.9) is NBS's lower relative line, filed as its
    own relative line, level extreme. ("Moderately poor" is a band between the
    two lines, not a headcount below one, and is not read.)
  * ABSOLUTE (food-energy intake: 2,900 kcal food line N21,743 + non-food
    N8,385 = N30,128 per adult equivalent per year): line_type national,
    level overall -- Tables 3.2 (sector, zone) and A.2 (states).
  * DOLLAR PER DAY (2002 World Bank PPP adjusted to 2003, N59.2 = US$1;
    N21,608 per person per year): international -- Tables 3.3 and A.3.
  * Subjective (self-assessed) poverty is not a consumption measure: not read.

PUBLISHED INCONSISTENCIES kept as printed: Table 3.8 prints rural 1996 69.3,
Table 1.7 69.8 and the prose 68.8 -- 3.8 (the 1980-2004 series) is read.
Table 3.3's Total row is 51.6 against A.3's 51.55 -- the state table's own
Total is read; 3.3's is not. The 2004 sector/zone columns of 3.8 / 3.10
repeat Table 6 rounded and are not re-read.
"""
from __future__ import annotations

import re

import pandas as pd

from . import _common as C

_REL = {"line_type": "relative", "line_level": "overall",
        "line_name": "NBS relative poverty line (1996/97 method)"}
_CORE = {"line_type": "relative", "line_level": "extreme",
         "line_name": "NBS relative core poverty line (1996/97 method)"}
_ABS = {"line_type": "national", "line_level": "overall",
        "line_name": "Absolute poverty line, food energy intake (NLSS 2003/04)",
        "line_value": 30128, "line_unit": "NGN per adult equivalent per year, 2003/04"}
_USD = {"line_type": "international", "line_level": "other",
        "line_name": "US$1 a day (2002 World Bank PPP, adjusted to 2003: N59.2 per US$)",
        "line_value": 21608, "line_unit": "NGN per person per year, 2003/04"}

LAYOUT_PROFILE2004 = {"survey": "NLSS 2003/04", "welfare_aggregate": "consumption",
                      "unit_of_analysis": "person", "frequency": "ad_hoc",
                      "period": "2003", "reference_period": "2003/04", **_REL, "tables": []}

_ZONES = ["South South", "South East", "South West", "North Central", "North East", "North West"]
_YEARS = ["1980", "1985", "1992", "1996", "2004"]


def _survey(year: str) -> tuple[str, str, str]:
    if year == "2004":
        return "NLSS 2003/04", "2003", "2003/04"
    return f"NCS {year}", year, year


def _row(line: dict, metric: str, value: float, year: str = "2004", unit=None, **cell) -> dict:
    survey, period, ref = _survey(year)
    return C.row(metric=metric, value=value, survey=survey, welfare_aggregate="consumption",
                 line_type=line["line_type"], line_level=line["line_level"],
                 line_name=line["line_name"], line_value=line.get("line_value", "") if year == "2004" else "",
                 line_unit=line.get("line_unit", "") if year == "2004" else "",
                 period=period, reference_period=ref, frequency="ad_hoc",
                 unit_of_analysis="person", unit=unit,
                 topic=cell.get("topic", "total"), characteristic=cell.get("characteristic", "Total"),
                 geography=cell.get("geography", "Total country"),
                 locality=cell.get("locality", "all"), locality_label=cell.get("locality_label", "Total"))


def _geo(label: str) -> dict | None:
    lab = re.sub(r"\s+", " ", label.replace("-", " ")).strip()
    if lab in ("National", "Total", "All Nigeria"):
        return {}
    if lab in ("Urban", "Rural"):
        return {"topic": "locality", "locality": lab.lower(), "locality_label": lab}
    if lab in _ZONES:
        return {"geography": lab + " zone"}
    return {"geography": "Nassarawa" if lab == "Nassarawa" else lab}


def _pages(path: str) -> list[str]:
    import pdfplumber
    with pdfplumber.open(path) as pdf:
        return [(p.extract_text() or "") for p in pdf.pages]


def _page(pages, *needles) -> str:
    hits = [p for p in pages if all(n in p for n in needles)]
    if not hits:
        raise ValueError(f"page with {needles} not found")
    return hits[-1]


_NUM = r"(-?\d+(?:\.\d+)?)%?"


def _lines_after(text: str, start: str, stop: str | None = None):
    on = False
    for ln in text.splitlines():
        if not on:
            on = start in ln
            continue
        if stop and stop in ln:
            break
        yield ln.strip()


def parse_profile2004(path: str) -> pd.DataFrame:
    pages = _pages(path)
    rows: list[dict] = []

    # --- Appendix A Table 6: relative line, full FGT set -------------------
    t6 = _page(pages, "POVERTY FIGURES BY SECTOR, ZONE AND STATE")
    for ln in t6.splitlines():
        m = re.match(rf"^([A-Za-z][A-Za-z .\-]*?)\s+{_NUM}\s+{_NUM}\s+(\d\.\d+)\s+(\d\.\d+)\s+(\d\.\d+)\s+{_NUM}\s+(\d\.\d+)\s*$",
                     ln.strip())
        if not m:
            continue
        cell = _geo(m.group(1))
        if cell is None:
            continue
        national = cell == {}
        if not national:
            rows.append(_row(_REL, "population_share", float(m.group(2)), **cell))
            rows.append(_row(_REL, "poor_share", float(m.group(7)), **cell))
        rows.append(_row(_REL, "headcount", float(m.group(3)), **cell))
        rows.append(_row(_REL, "gap", float(m.group(4)), unit="index", **cell))
        rows.append(_row(_REL, "severity", float(m.group(5)), unit="index", **cell))

    # --- Appendix A Table 1: 1996 by state (2004 column = Table 6) ---------
    t1 = _page(pages, "POVERTY INCIDENCE BY STATE (1996, 2004)")
    for ln in _lines_after(t1, "STATE 1996 2004"):
        m = re.match(r"^([A-Za-z][A-Za-z .]*?)\s+(\d+\.\d+)\s+(\d+\.\d+)\s*$", ln)
        if m and m.group(1) != "All Nigeria":
            rows.append(_row(_REL, "headcount", float(m.group(2)), year="1996", **_geo(m.group(1))))

    # --- Table 3.8: relative, urban/rural 1980-1996 -------------------------
    p = _page(pages, "RELATIVE POVERTY INCIDENCE BY SECTOR (1980-2004)")
    for ln in _lines_after(p, "Year Urban Rural", "Source"):
        m = re.match(r"^(19\d\d)\s+(\d+\.\d)\s+(\d+\.\d)$", ln)
        if m:
            for loc, v in (("Urban", m.group(2)), ("Rural", m.group(3))):
                rows.append(_row(_REL, "headcount", float(v), year=m.group(1), **_geo(loc)))

    # --- Table 3.9: core poor by sector, 1980-2004 --------------------------
    for ln in _lines_after(p, "Year Core Moderately", "Source"):
        m = re.match(r"^(19\d\d|2004)\s+" + r"\s+".join([r"(\d+\.\d)"] * 6) + "$", ln)
        if m:
            rows.append(_row(_CORE, "headcount", float(m.group(2)), year=m.group(1), **_geo("Urban")))
            rows.append(_row(_CORE, "headcount", float(m.group(5)), year=m.group(1), **_geo("Rural")))

    # --- Table 1.6: national core poor 1980-1996 ---------------------------
    p = _page(pages, "THE POOR AND THE CORE POOR BY YEAR")
    for ln in _lines_after(p, "Core Poor (%)", "Source"):
        m = re.match(r"^(19\d\d)\s+(\d+\.\d)\s+(\d+\.\d)\s+(\d+\.\d)$", ln)
        if m:
            rows.append(_row(_CORE, "headcount", float(m.group(4)), year=m.group(1)))

    # --- Table 3.10: zones 1980-1996 ----------------------------------------
    p = _page(pages, "TRENDS IN POVERTY LEVEL BY ZONES")
    for ln in _lines_after(p, "Zone 1980 1985", "Source"):
        m = re.match(r"^([A-Za-z ]+?)\s+" + r"\s+".join([r"(\d+\.\d)"] * 5) + "$", ln)
        if m:
            for y, v in zip(_YEARS[:4], m.groups()[1:5]):
                rows.append(_row(_REL, "headcount", float(v), year=y, **_geo(m.group(1))))

    # --- Tables 3.13 / 3.14: head's education and occupation, 1980-2004 -----
    p = _page(pages, "RELATIVE POVERTY INCIDENCE BY EDUCATIONAL LEVELS")
    for cap, topic, stop in (("RELATIVE POVERTY INCIDENCE BY EDUCATIONAL LEVELS", "education_of_head", "Source"),
                             ("RELATIVE POVERTY INCIDENCE BY OCCUPATION", "employment_of_head", "Source")):
        for ln in _lines_after(p, cap, stop):
            m = re.match(r"^([A-Za-z][A-Za-z &]+?)\s+" + r"\s+".join([r"(\d+\.\d)"] * 5) + "$", ln)
            if not m:
                continue
            lab = m.group(1).strip()
            for y, v in zip(_YEARS, m.groups()[1:6]):
                if lab in ("All Nigeria", "Total"):
                    # the national series 1980-1996 (2004 = Table 6); read once
                    if topic == "education_of_head" and y != "2004":
                        rows.append(_row(_REL, "headcount", float(v), year=y))
                    continue
                char = lab if topic == "education_of_head" else f"Occupation: {lab}"
                rows.append(_row(_REL, "headcount", float(v), year=y, topic=topic, characteristic=char))

    # --- Absolute and dollar lines: Tables 3.2 / 3.3 (sector, zone) ---------
    for cap, line in (("POVERTY INCIDENCE BY SECTOR AND ZONE", _ABS),
                      ("DOLLAR PER DAY BASED ON PPP BY SECTOR AND ZONE", _USD)):
        p = _page(pages, cap)
        for ln in _lines_after(p, cap):
            m = re.match(r"^([A-Za-z][A-Za-z\- ]+?)\s+(\d+\.\d)\s+(\d+\.\d)$", ln)
            if not m:
                if ln.startswith(("FIGURE", "Source")):
                    break
                continue
            if m.group(1).strip() == "Total":
                continue      # read from the state tables' own Total row
            cell = _geo(m.group(1))
            if cell is not None:
                rows.append(_row(line, "headcount", float(m.group(2)), **cell))

    # --- Appendix A Tables 2 / 3: absolute and dollar lines by state --------
    p = _page(pages, "LIMIT PLUS A COMPONENT OF NON-FOOD")
    for ln in p.splitlines():
        m = re.match(r"^([A-Za-z][A-Za-z ]*?)\s+(\d+\.\d+)\s+(\d+\.\d+)\s+([A-Za-z][A-Za-z ]*?)\s+(\d+\.\d+)\s+(\d+\.\d+)$",
                     ln.strip())
        if not m or m.group(1) != m.group(4):
            continue
        cell = _geo(m.group(1))
        rows.append(_row(_ABS, "headcount", float(m.group(2)), **cell))
        rows.append(_row(_USD, "headcount", float(m.group(5)), **cell))

    df = pd.DataFrame(rows)
    if len(df) < 400:
        raise ValueError(f"{path}: only {len(df)} rows read")
    return df


LAYOUT = LAYOUT_PROFILE2004
parse = parse_profile2004


# ------------------------------------------------------------- HNLSS 2009/10
# "Nigeria Poverty Profile 2010" (NBS, Jan 2012), Harmonized Nigeria Living
# Standard Survey 2009/10. Table 10 gives four measures for urban/rural, six
# zones and 37 states: FOOD poverty (food expenditure below the food line --
# NAT_FOOD), ABSOLUTE (3,000 kcal food-energy-intake line, as in 2004),
# RELATIVE (two-thirds of regionally deflated mean per capita expenditure --
# the same series as 1980-2004) and DOLLAR A DAY (adjusted PPP, N150 = US$1;
# PPP base year not printed). Only the "Poor" columns are read ("Non Poor"
# is their complement). Table 3 adds the relative CORE ("extremely") poor for
# 2004 and 2010; Table 4 adds the 2004 food-poor rate, printed nowhere else.
# Not read: Table 9 (2011 = model FORECAST; it also prints the 2004 dollar
# rate as 62.8 against 51.6 in Table 4 and 51.55 in the 2004 profile),
# subjective poverty, Gini.
_FOOD10 = {"line_type": "national", "line_level": "other",
           "line_name": "Food poverty (food expenditure below the food poverty line), NBS"}
_ABS10 = {**_ABS, "line_name": "Absolute poverty line, food energy intake (HNLSS 2009/10)",
          "line_value": "", "line_unit": ""}
_USD10 = {"line_type": "international", "line_level": "other",
          "line_name": "US$1 a day (adjusted PPP, N150 per US$, base year not printed)"}

LAYOUT_HNLSS2010 = {**LAYOUT_PROFILE2004, "survey": "HNLSS 2009/10", "period": "2009",
                    "reference_period": "2009/10", **_REL}


def _row10(line, metric, value, year="2010", **cell):
    r = _row(line, metric, value, year="2004" if year == "2004" else "x", **cell)
    if year != "2004":
        r.update(survey="HNLSS 2009/10", period="2009", reference_period="2009/10",
                 line_value="", line_unit="")
    return r


def parse_hnlss2010(path: str) -> pd.DataFrame:
    pages = _pages(path)
    rows = []
    t10 = _page(pages, "Table 10 2010 Poverty Numbers for Absolute, Relative")
    for ln in t10.splitlines():
        s = re.sub(r"^(sector|zone|state)\s+", "", ln.strip())
        m = re.match(r"^([A-Za-z][A-Za-z \-]*?)\s+" + r"\s+".join([r"(\d+\.\d)"] * 8) + "$", s)
        if not m:
            continue
        lab = {"Cross-Rivers": "Cross River", "Akwa ibom": "Akwa Ibom", "South west": "South West",
               "South-South": "South South"}.get(m.group(1), m.group(1))
        cell = _geo(lab)
        v = [float(x) for x in m.groups()[1:]]
        for line, x in ((_FOOD10, v[0]), (_ABS10, v[2]), (_REL, v[4]), (_USD10, v[6])):
            rows.append(_row10(line, "headcount", x, **cell))
    p = _page(pages, "Table 3 Relative Poverty: Non-poor, Moderate poor and the Extremely")
    for ln in _lines_after(p, "Year Non-poor Moderately poor Extremely poor", "Source"):
        m = re.match(r"^(2004|2010)\s+(\d+\.\d)\s+(\d+\.\d)\s+(\d+\.\d)$", ln)
        if m:
            rows.append(_row10(_CORE, "headcount", float(m.group(4)), year=m.group(1)))
    p = _page(pages, "Table 4 National Poverty Incidence 2003/2004 and 2009/2010")
    for ln in _lines_after(p, "Year Food Poor Absolute Poor"):
        m = re.match(r"^2004\s+(\d+\.\d)\s+", ln)
        if m:
            rows.append(_row10(_FOOD10, "headcount", float(m.group(1)), year="2004"))
            break
    df = pd.DataFrame(rows)
    if len(df) < 170:
        raise ValueError(f"{path}: only {len(df)} rows")
    return df
