"""Standardised columns for monetary poverty, derived from the published ones.

THE LINE IS PART OF THE ID. An overall and an extreme headcount for one group
are different quantities, so series_id carries the line:

    NAT        national overall (upper / "total") line
    NAT_EXT    national extreme (food / lower) line
    NAT_<slug> any other national line, by its published name
    INT_<slug> an international line the NSO republishes ("US$2.15 2017 PPP")
    REL_<slug> a relative line (share of median welfare)

A national line is each country's own -- comparable over time within a
country only while the NSO keeps its methodology, which `survey` and
`line_name` record. INCOME-based measures get an INC token: an income and a
consumption headcount never share an ID, nor do person and household counts.

Breakdowns get a code only where the category set is standard:
  total            -> "" (or the age band of the population covered, Y_GE15)
  locality         -> the locality token (URB / RUR / LOC_<stratum>)
  sex / sex_of_head -> SEX_F / HEAD_F ...
  age / age_of_head -> AGE_<band> / HEADAGE_<band>
  quintile         -> Q1..Q5;  household_size -> HHSIZE_<n> / HHSIZE_GE<n>
  literacy(_of_head) -> LIT_Y / LIT_N (HEADLIT_ ...)
  education, household type, marital status, employment -> blank: national
  category sets ("Secondaire 1" is not one level across countries).

value_std puts every value printed on 0..1 (unit 'index': P1 and P2, and the
headcounts and shares of reports that print fractions) on the PERCENT scale
(0.084 means 8.4%); value itself stays as printed.

is_preferred: among rows sharing an ID, place and period, the one from the
NEWEST REPORT (the latest round its source file covers) -- a re-estimate
beats the original it revises.
"""
from __future__ import annotations

import re

import pandas as pd

from core.standardise_base import (age_code, age_name, drop_conflicts, drop_std, edition,
                                   finish, geography_level, join_name, locality_name,
                                   locality_token, mark_preferred, norm, safe_id)

STD_COLUMNS = ["breakdown_code", "sex_code", "geography_level", "line_code", "unit_std",
               "value_std", "series_id", "series_name", "is_preferred"]

_SEX = {"male": "M", "female": "F", "total": "_T"}
_F = re.compile(r"^(?:female(?:[- ]headed)?|feminin|femme|femmes|mulher|mulheres|women)$")
_M = re.compile(r"^(?:male(?:[- ]headed)?|masculin|homme|hommes|homem|homens|men)$")
_YES = re.compile(r"^(?:oui|yes|sim|alphabetise|literate)$")
_NO = re.compile(r"^(?:non|no|nao|analphabete|illiterate)$")
_WORDS = {"une": 1, "un": 1, "deux": 2, "trois": 3, "quatre": 4, "cinq": 5, "six": 6,
          "sept": 7, "huit": 8, "neuf": 9, "dix": 10, "onze": 11, "douze": 12,
          "treize": 13, "quatorze": 14, "quinze": 15, "one": 1, "two": 2, "three": 3,
          "four": 4, "five": 5, "seven": 7, "eight": 8, "nine": 9, "ten": 10}

_METRIC = {"headcount": "P0", "gap": "P1", "severity": "P2", "poor_count": "POOR_N",
           "poor_share": "POOR_SH", "gap_contribution": "P1_CTR",
           "severity_contribution": "P2_CTR", "absolute_contribution": "P0_ABS_CTR",
           "population_share": "POP_SH", "headcount_ci_low": "P0_CIL",
           "headcount_ci_high": "P0_CIH"}
_METRIC_NAME = {
    "headcount": "Poverty headcount ratio (% of population)",
    "gap": "Poverty gap index (P1, %)", "severity": "Poverty severity index (P2, %)",
    "poor_count": "Number of poor people",
    "poor_share": "Share of all poor people (%)",
    "gap_contribution": "Contribution to the national poverty gap (%)",
    "severity_contribution": "Contribution to national poverty severity (%)",
    "absolute_contribution": "Absolute contribution to the national headcount (points)",
    "population_share": "Population share (%), poverty survey",
    "headcount_ci_low": "Poverty headcount ratio, lower confidence bound (%)",
    "headcount_ci_high": "Poverty headcount ratio, upper confidence bound (%)"}

_METRIC_NAME_HH = {
    "headcount": "Share of households below the poverty line (%)",
    "gap": "Poverty gap index, households (P1, %)",
    "severity": "Poverty severity index, households (P2, %)",
    "poor_count": "Number of poor households",
    "poor_share": "Share of all poor households (%)",
    "population_share": "Share of households (%), poverty survey"}


def _slug(text: str, n: int = 30) -> str:
    return safe_id(norm(text))[:n].rstrip("_")


def line_code(ltype: str, level: str, name: str) -> str:
    if ltype == "national":
        # A "food poverty" measure (food consumption below the food line,
        # filed line_level other) gets ONE token however each office words
        # it, or Kenya's, Liberia's and Gambia's wordings split one concept.
        if level == "other" and re.search(r"\bfood\b|aliment", norm(name)):
            return "NAT_FOOD"
        return {"overall": "NAT", "extreme": "NAT_EXT"}.get(level) or "NAT_" + _slug(name)
    if ltype == "international":
        # One ID per amount and PPP base, however it is worded:
        # "US$1.90 a day (2011 PPP)" and "US$1,9 par jour (PPA 2011)" -> INT_1_90_PPP2011.
        # A line whose PPP base is not printed keeps its own wording-based ID.
        amt = re.search(r"\$\s*(\d+(?:[.,]\d+)?)", name)
        yr = re.search(r"(?:ppp|ppa)\D{0,3}(20\d\d)|(20\d\d)\D{0,3}(?:ppp|ppa)", name, re.I)
        if amt and yr:
            a = float(amt.group(1).replace(",", "."))
            return f"INT_{a:.2f}".replace(".", "_") + f"_PPP{yr.group(1) or yr.group(2)}"
        return "INT_" + _slug(name)
    if ltype == "relative":
        return "REL_" + _slug(name)
    return ""


def _line_name(code: str, name: str) -> str:
    if code == "NAT":
        return "national poverty line"
    if code == "NAT_EXT":
        return "national extreme poverty line"
    if code == "NAT_FOOD":
        return "food poverty (food consumption below the national food line)"
    m = re.fullmatch(r"INT_(\d+)_(\d\d)_PPP(\d{4})", code)
    if m:
        return f"international poverty line US${m.group(1)}.{m.group(2)} a day ({m.group(3)} PPP)"
    return name.strip()


def _age(text: str) -> str:
    a = age_code(text)
    if a:
        return a
    m = re.fullmatch(r"(?:plus de|more than|over)\s*(\d{1,3})\s*(?:ans|years|anos)?", norm(text))
    return f"Y_GE{int(m.group(1)) + 1}" if m else ""


_PERS = r"(?:\s*(?:personnes?|persons?|people|pessoas?|membres?|members?))?"
_NUM = r"(\d{1,2}|[a-z]+)"


def _n(tok: str):
    return int(tok) if tok.isdigit() else _WORDS.get(tok)


def _hhsize(text: str) -> str:
    """'Une personne' -> HHSIZE_1, '3 ou 4' / '3-4' -> HHSIZE_3T4,
    '7 ou plus' / 'Quatorze personnes et plus' -> HHSIZE_GE7. Anything else
    (an unrecognised band) stays blank rather than being read by its first
    number: "1 ou 2" is not a one-person household (Madagascar, 2026-11-04)."""
    s = norm(text)
    m = re.fullmatch(_NUM + r"\s*(?:or more|and more|and over|ou plus|ou mais|e mais|et plus|\+)" + _PERS, s)
    if m and _n(m.group(1)):
        return f"HHSIZE_GE{_n(m.group(1))}"
    m = re.fullmatch(_NUM + _PERS + r"\s*(?:et plus|ou \+|et \+|and over|and more|or more|\+|ou mais|ou plus|e mais)", s)
    if m and _n(m.group(1)):
        return f"HHSIZE_GE{_n(m.group(1))}"
    m = re.fullmatch(r"(?:>=|≥)\s*" + _NUM + _PERS, s)
    if m and _n(m.group(1)):
        return f"HHSIZE_GE{_n(m.group(1))}"
    # "2 ou moins" / "<=2": a household has at least one member, so 1T2.
    m = (re.fullmatch(_NUM + _PERS + r"\s*(?:ou moins|or less|or fewer|ou menos)", s)
         or re.fullmatch(r"(?:<=|≤)\s*" + _NUM + _PERS, s))
    if m and _n(m.group(1)):
        return "HHSIZE_1" if _n(m.group(1)) == 1 else f"HHSIZE_1T{_n(m.group(1))}"
    m = re.fullmatch(r"(?:plus de|more than|over|mais de)\s*" + _NUM + _PERS, s)
    if m and _n(m.group(1)):
        return f"HHSIZE_GE{_n(m.group(1)) + 1}"
    m = re.fullmatch(_NUM + r"\s*(?:ou|a|-|to|e|and|or)\s*" + _NUM + _PERS, s)
    if m and _n(m.group(1)) and _n(m.group(2)) and _n(m.group(1)) < _n(m.group(2)):
        return f"HHSIZE_{_n(m.group(1))}T{_n(m.group(2))}"
    m = re.fullmatch(_NUM + _PERS, s)
    if m and _n(m.group(1)):
        return f"HHSIZE_{_n(m.group(1))}"
    return ""


def _breakdown(topic: str, char: str, age: str, locality: str, label: str) -> str:
    c = norm(char)
    if topic == "total":
        a = _age(age)
        return "" if a in ("", "_T") else a
    if topic == "locality":
        return locality_token(locality, label) or "_T"
    if topic in ("sex", "sex_of_head"):
        pre = "SEX_" if topic == "sex" else "HEAD_"
        return pre + "F" if _F.match(c) else pre + "M" if _M.match(c) else ""
    if topic in ("age", "age_of_head"):
        a = _age(char)
        return (("AGE_" if topic == "age" else "HEADAGE_") + a) if a.startswith("Y") else ""
    if topic == "quintile":
        m = re.fullmatch(r"(?:q|quintile )?([1-5])(?:er|e|eme|st|nd|rd|th)?(?: quintile)?", c)
        return f"Q{m.group(1)}" if m else ""
    if topic == "household_size":
        return _hhsize(char)
    if topic in ("literacy", "literacy_of_head"):
        pre = "LIT_" if topic == "literacy" else "HEADLIT_"
        return pre + "Y" if _YES.match(c) else pre + "N" if _NO.match(c) else ""
    return ""


def _breakdown_name(b: str) -> str:
    if not b or b == "_T":
        return ""
    fixed = {"SEX_F": "women", "SEX_M": "men", "HEAD_F": "people in female-headed households",
             "HEAD_M": "people in male-headed households", "LIT_Y": "literate people",
             "LIT_N": "illiterate people", "HEADLIT_Y": "people in households with a literate head",
             "HEADLIT_N": "people in households with an illiterate head"}
    if b in fixed:
        return fixed[b]
    if b.startswith("Y"):
        return "people " + age_name(b)
    if b.startswith("AGE_"):
        return "people " + age_name(b[4:])
    if b.startswith("HEADAGE_"):
        return "people in households with a head " + age_name(b[8:])
    if b.startswith("HHSIZE_GE"):
        return f"people in households of {b[9:]} or more persons"
    m = re.fullmatch(r"HHSIZE_(\d+)T(\d+)", b)
    if m:
        return f"people in households of {m.group(1)}-{m.group(2)} persons"
    if b.startswith("HHSIZE_"):
        n = b[7:]
        return f"people in households of {n} person" + ("" if n == "1" else "s")
    if re.fullmatch(r"Q[1-5]", b):
        return f"welfare quintile {b[1]}" + {"1": " (poorest)", "5": " (richest)"}.get(b[1], "")
    return locality_name(b)


def standardise(df: pd.DataFrame) -> pd.DataFrame:
    out = drop_std(df, STD_COLUMNS)
    s = out.fillna("").astype(str)
    keys = list(zip(s["topic"], s["characteristic"], s["age_group"], s["locality"], s["locality_label"]))
    cache = {k: _breakdown(*k) for k in set(keys)}
    out["breakdown_code"] = [cache[k] for k in keys]
    out["sex_code"] = s["sex"].map(_SEX).fillna("")
    out["geography_level"] = s["geography"].map(geography_level)
    out["line_code"] = [line_code(t, l, n) for t, l, n in zip(s["line_type"], s["line_level"], s["line_name"])]
    v = pd.to_numeric(out["value"], errors="coerce")
    # unit 'index' = printed on 0..1 (P1/P2, and the headcounts and shares of
    # the reports that print fractions): value_std puts it on the percent scale.
    idx = s["unit"] == "index"
    out["value_std"] = v.where(~idx, (v * 100).round(10))  # 0.523*100 is 52.300000000000004
    out["unit_std"] = s["unit"].where(~idx, "percent")

    ids, names = [], []
    for i in range(len(out)):
        metric, b, line = s["metric"].iat[i], out["breakdown_code"].iat[i], out["line_code"].iat[i]
        # A breakdown that cannot be coded gets no ID -- except the plain
        # national/regional total, whose breakdown is legitimately empty.
        uncoded = b == "" and s["topic"].iat[i] != "total"
        if metric not in _METRIC or not line or uncoded or (s["topic"].iat[i] == "total" and b == "" and s["age_group"].iat[i] not in ("Total", "")):
            ids.append("")
            names.append("")
            continue
        # A cut crossed with SEX (ANSD IV-4: age of head x Homme / Femme /
        # National) carries the sex too, or the three values share one ID.
        sx, topic = s["sex"].iat[i], s["topic"].iat[i]
        sex_tok = ""
        if sx in ("male", "female") and topic not in ("sex", "sex_of_head", "total"):
            sex_tok = ("HEAD_" if topic.endswith("_of_head") or topic in ("household_size", "household_type")
                       else "SEX_") + _SEX[sx]
        loc = "" if s["topic"].iat[i] == "locality" else locality_token(s["locality"].iat[i], s["locality_label"].iat[i])
        bb = "" if b == "_T" else b
        # A cut over a sub-population (literacy of individuals 15+) carries
        # that population's age band, or it would share the all-ages ID.
        ag = s["age_group"].iat[i]
        if s["topic"].iat[i] not in ("total", "age", "age_of_head") and ag not in ("Total", ""):
            a = _age(ag)
            if not a.startswith("Y"):
                ids.append("")
                names.append("")
                continue
            bb = safe_id(bb, a)
        welfare = "INC" if s["welfare_aggregate"].iat[i] == "income" else ""
        unit = "HH" if s["unit_of_analysis"].iat[i] == "household" else ""
        # A population share is the same whatever the line: the line stays out.
        lid = "" if metric == "population_share" else line
        ids.append(safe_id("POV", lid, welfare, unit, _METRIC[metric], bb, sex_tok, loc))
        # Household-level rows are named as households, not people.
        bname = _breakdown_name(b if b != "_T" else "")
        mname = _METRIC_NAME[metric]
        if unit:
            mname = _METRIC_NAME_HH.get(metric, mname + ", households")
            bname = bname.replace("people in ", "")
        names.append(join_name(
            mname, _line_name(lid, s["line_name"].iat[i]) if lid else "",
            "income-based" if welfare else "",
            bname, _breakdown_name(sex_tok) if sex_tok else "",
            age_name(_age(ag)) if (s["topic"].iat[i] not in ("total", "age", "age_of_head") and ag not in ("Total", "")) else "",
            locality_name(loc)))
    out["series_id"], out["series_name"] = ids, names
    drop_conflicts(out, ["country", "series_id", "geography", "period"], ["source_file", "survey"])
    # PREFERRED ESTIMATE: when an original and a re-estimate of one round share
    # an ID, the NEWEST REPORT wins. A report's vintage is the latest round it
    # covers (rows sharing its source file), so EICV7's re-estimate of 2016/17
    # beats the EICV5 profile's original. Then the survey label's edition, then
    # the extraction time.
    blank = pd.Series("", index=s.index)
    sf, su = s.get("source_file", blank), s.get("source_url", blank)
    src = sf.where(sf != "", su)
    vintage = pd.to_numeric(s["period"], errors="coerce").groupby([s["country"], src]).transform("max")
    out["is_preferred"] = mark_preferred(
        out.assign(_c=s["country"], _g=s["geography"], _p=s["period"], _v=vintage,
                   _e=s["survey"].map(edition), _x=s["extracted_at"]),
        ["_c", "series_id", "_g", "_p"], ["_v", "_e", "_x"])
    return finish(out, STD_COLUMNS)
