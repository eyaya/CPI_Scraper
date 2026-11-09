"""The Gambia -- GBoS poverty reports before IHS 2015/16 (time depth).

1. `parse_ihs2003` -- "Integrated Household Survey 2003/04" report, Appendix 2.
   Every table is STACKED: one block per index (head count, poverty gap,
   severity, Watts), each "<index> <category> <estimate> <std. err.>", with a
   "Note: Based on the lower|upper (poverty) line" footer naming the line.
   Two lines (lower = food + minimal non-food, upper = the line at which the
   nutritional requirement is actually met) and, nationally, two welfare
   measures: Tables 1-4 give both PER CAPITA and PER ADULT EQUIVALENT; the
   profile tables use per capita (the report: "we prefer poverty lines per
   capita"; the area and education tables reproduce the per-capita national
   figure, the adult-equivalent one cannot be reached). The welfare measure is
   carried in `line_name`, since one line gives two headcounts.
   Read: Tables 1-4 (national), 5/9 (urban/rural), 6/21 (8 LGAs), 7/22
   (14 strata = LGA x urban/rural), 8/23 (3 domains), 12/33 (age of head),
   13/34 (occupation of head), 14/35 (industry of head), 15/26 (marital
   status), 19/30 (education), 20 (literacy), 31/32 (household size).
   NOT READ: Tables 10/24 (sex of head) -- PUBLISHED DEFECT: male 34.8 /
   female 53.5 under a national 51.2 would need 88% of people in
   female-headed households; the swapped labels give 11%. GBoS's 2010 report
   repeats the printed reading in prose, so it is documented, not repaired.
   Also not read: ethnicity, marriage/union type, housing and subjective
   status (no topic), the groundnut tables, Watts index, standard errors, and
   the domain "Rural" rows (= the area table's Rural).

2. `parse_ihs2010` -- "Integrated Household Survey 2010: Income and
   Expenditure Poverty Assessment". The 2010 round's ORIGINAL estimates are
   on dollar-a-day lines only (US$1 and US$1.25 per person per day; the PPP
   base is not printed). Table 5.1: headcount and distribution of the poor on
   both lines for urban/rural, 8 LGAs, household size, sex, education and
   sector of the head, and the population distribution; Tables 5.15/5.16: by
   age group of the person. Tables 5.7-5.14 repeat 5.1's rates with SAMPLE
   counts and are not read. GBoS's later re-estimate of 2010 on its national
   absolute line (IHS 2015/16 report) is already collected under "IHS 2010".
"""
from __future__ import annotations

import re

import pandas as pd

from . import _common as C

_BASE = {"welfare_aggregate": "consumption", "unit_of_analysis": "person",
         "frequency": "ad_hoc"}

LAYOUT_IHS2003 = {**_BASE, "survey": "IHS 2003/04", "line_type": "national",
                  "line_level": "overall", "line_name": "Upper poverty line (per capita), IHS 2003/04",
                  "period": "2003", "reference_period": "2003/04", "tables": []}
LAYOUT_IHS2010 = {**_BASE, "survey": "IHS 2010 (original estimates, dollar-a-day lines)",
                  "line_type": "international", "line_level": "other",
                  "line_name": "US$1.25 per person per day (PPP base not printed)",
                  "period": "2010", "reference_period": "2010", "tables": []}

_LINES_2003 = {
    ("lower", "pc"): {"line_level": "other", "line_name": "Lower poverty line (per capita), IHS 2003/04"},
    ("upper", "pc"): {"line_level": "overall", "line_name": "Upper poverty line (per capita), IHS 2003/04"},
    ("lower", "ae"): {"line_level": "other", "line_name": "Lower poverty line (per adult equivalent), IHS 2003/04"},
    ("upper", "ae"): {"line_level": "other", "line_name": "Upper poverty line (per adult equivalent), IHS 2003/04"},
}
_LGAS = ["Banjul", "Kanifing", "Brikama", "Mansakonko", "Kerewan", "Kuntaur", "Janjangbureh", "Basse"]
_INDEX = [(re.compile(r"^(?:9)?\s*head\s*count(?:\s+index)?\b", re.I), "headcount"),
          (re.compile(r"^(?:9)?\s*poverty\s+gap\b", re.I), "gap"),
          (re.compile(r"^poverty\s+severity\b", re.I), "severity"),
          (re.compile(r"^watt'?’?s\s+index\b", re.I), "watts"),
          # "Poverty <category>" / "severity <category>": the severity label
          # wraps around the block's first row (Table 34).
          (re.compile(r"^poverty\b(?!\s+(?:gap|severity)\b)", re.I), "severity"),
          (re.compile(r"^severity\b", re.I), None),
          (re.compile(r"^index\b", re.I), None)]   # wrapped "Head count / index"

# table number -> (topic, attr) ; attr: 'locality' | 'lga' | 'strata' | 'domain' | 'char:<prefix>'
_T2003 = {5: "area", 9: "area", 6: "lga", 21: "lga", 7: "strata", 22: "strata", 8: "domain",
          23: "domain", 12: "age_of_head", 33: "age_of_head",
          13: "employment_of_head:Occupation", 34: "employment_of_head:Occupation",
          14: "employment_of_head:Industry", 35: "employment_of_head:Industry",
          15: "marital_status_of_head", 26: "marital_status_of_head",
          19: "education_of_head", 30: "education_of_head", 20: "literacy_of_head",
          31: "household_size", 32: "household_size"}


def _pages(path: str) -> list[str]:
    import pdfplumber
    with pdfplumber.open(path) as pdf:
        return [(p.crop((0, 0, p.width, p.height)).extract_text() or "") for p in pdf.pages]


def _row(lay: dict, metric: str, value: float, **cell) -> dict:
    a = {**lay, **cell}
    return C.row(metric=metric, value=value, survey=a["survey"],
                 welfare_aggregate="consumption", line_type=a["line_type"],
                 line_level=a["line_level"], line_name=a["line_name"],
                 period=a["period"], reference_period=a["reference_period"],
                 frequency="ad_hoc", unit_of_analysis="person",
                 topic=a.get("topic", "total"), characteristic=a.get("characteristic", "Total"),
                 sex=a.get("sex", "total"), age_group=a.get("age_group", "Total"),
                 geography=a.get("geography", "Total country"),
                 locality=a.get("locality", "all"), locality_label=a.get("locality_label", "Total"))


def _blocks_2003(text: str):
    """Yield (table_no, lines) for every 'Table N:' block up to its Note line."""
    cur, num = [], None
    for ln in text.splitlines():
        m = re.match(r"^Table\s+(\d+):", ln.strip())
        if m:
            if num is not None:
                yield num, cur
            num, cur = int(m.group(1)), [ln.strip()]
            continue
        if num is not None:
            cur.append(ln.strip())
            if ln.strip().startswith("Note"):
                yield num, cur
                num, cur = None, []
    if num is not None:
        yield num, cur


def _cell_2003(kind: str, label: str) -> dict | None:
    lab = label.strip()
    if kind == "area":
        return {"topic": "locality", "locality": lab.lower(), "locality_label": lab} \
            if lab in ("Urban", "Rural") else None
    if kind == "lga":
        return {"geography": lab} if lab in _LGAS else None
    if kind == "strata":
        m = re.match(r"^(Banjul|KMC|Brikama|Mansakonko|Kerewan|Kuntaur|Janjangbureh|Basse)\s+(urban|rural)$", lab, re.I)
        if not m:
            return None
        geo = "Kanifing" if m.group(1) == "KMC" else m.group(1)
        loc = m.group(2).lower()
        return {"geography": geo, "topic": "locality", "locality": loc, "locality_label": loc.title()}
    if kind == "domain":
        if lab in ("Banjul+ Kanifing", "Other urban"):
            return {"topic": "locality", "locality": "other", "locality_label": lab}
        return None                      # "Rural" = the area table's Rural
    topic, _, prefix = kind.partition(":")
    return {"topic": topic, "characteristic": f"{prefix}: {lab}" if prefix else lab}


def parse_ihs2003(path: str) -> pd.DataFrame:
    rows, seen = [], set()
    text = "\n".join(_pages(path)[52:80])        # Appendix 2 (pp. 53-80)
    for num, lines in _blocks_2003(text):
        note = next((l for l in lines if l.startswith("Note")), "")
        if num <= 4:
            welfare = "ae" if "adult" in note else "pc"
            line = "upper" if "upper" in note else "lower"
            lay = {**LAYOUT_IHS2003, **_LINES_2003[(line, welfare)]}
            for ln in lines:
                for rx, metric in _INDEX:
                    if metric and metric != "watts" and rx.match(ln):
                        v = re.findall(r"\d+\.\d", ln)
                        if v:
                            rows.append(_row(lay, metric, float(v[0])))
            continue
        kind = _T2003.get(num)
        if not kind:
            continue
        line = "upper" if "upper" in note.lower() else "lower" if "lower" in note.lower() else None
        if not line:
            raise ValueError(f"Table {num}: no line named in its note: {note!r}")
        lay = {**LAYOUT_IHS2003, **_LINES_2003[(line, "pc")]}
        metric = None
        for ln in lines[1:]:
            body = ln
            for rx, m in _INDEX:
                mm = rx.match(body)
                if mm:
                    if m:
                        metric = m
                    body = body[mm.end():].strip()
                    break
            mm = re.match(r"^(.+?)\s+(\d+\.\d|\d+\.\.\d)\s+(\d+\.\d|…|\.\.\.)\s*$", body)
            if not mm or metric in (None, "watts"):
                continue
            cell = _cell_2003(kind, mm.group(1))
            if cell is None:
                continue
            val = float(mm.group(2).replace("..", "."))
            key = (num, metric, tuple(sorted(cell.items())))
            if key in seen:
                continue
            seen.add(key)
            rows.append(_row(lay, metric, val, **cell))
    if len(rows) < 300:
        raise ValueError(f"{path}: only {len(rows)} rows read from Appendix 2")
    return pd.DataFrame(rows)


# ---------------------------------------------------------------- IHS 2010
_L1 = {"line_name": "US$1.00 per person per day (PPP base not printed)"}
_L125 = {"line_name": "US$1.25 per person per day (PPP base not printed)"}
_LGA10 = ["Banjul", "Kanifing", "Brikama", "Mansakonko", "Kerewan", "Kuntaur", "Janjanbureh", "Basse"]


def parse_ihs2010(path: str) -> pd.DataFrame:
    pages = _pages(path)
    lay = LAYOUT_IHS2010
    rows = []
    # The LIST OF TABLES repeats every caption; the table is the last match.
    t51 = [p for p in pages if "Table 5. 1: Poverty Measures, 2010" in p and "LIST OF TABLE" not in p][-1]
    block, pend = None, ""
    for ln in t51.splitlines():
        s = ln.strip()
        for b in ("LGA", "Household size", "Gender of household head",
                  "Education level of household head", "Sector of employment of household head"):
            if s == b:
                block, pend = b, ""
        v = re.findall(r"\d+\.\d", s)
        lab = re.sub(r"\s*\d+\.\d.*$", "", s).strip()
        if not v:
            if block == "Sector of employment of household head" and s and s != block:
                pend = (pend + " " + s).strip()
            continue
        if pend and block == "Sector of employment of household head":
            lab = (pend + " " + lab).strip()
        pend = ""
        if s.startswith("Total") and len(v) == 2:
            rows.append(_row({**lay, **_L1}, "headcount", float(v[0])))
            rows.append(_row({**lay, **_L125}, "headcount", float(v[1])))
            continue
        if block == "Household size":
            m = re.match(r"^(\d+)\.0\s", s)
            if m:
                v = re.findall(r"\d+\.\d", s[m.end():])
                lab = f"{m.group(1)} persons" if m.group(1) != "1" else "1 person"
            elif s.startswith("10 or more"):
                lab, v = "10 or more persons", re.findall(r"\d+\.\d", s[len("10 or more"):])
        if len(v) != 5:
            continue
        if lab in ("Urban", "Rural") and block is None:
            cell = {"topic": "locality", "locality": lab.lower(), "locality_label": lab}
        elif block == "LGA" and lab in _LGA10:
            cell = {"geography": lab}
        elif block == "Household size":
            cell = {"topic": "household_size", "characteristic": lab}
        elif block == "Gender of household head" and lab in ("Male", "Female"):
            cell = {"topic": "sex_of_head", "characteristic": lab, "sex": lab.lower()}
        elif block == "Education level of household head":
            cell = {"topic": "education_of_head", "characteristic": lab}
        elif block == "Sector of employment of household head":
            cell = {"topic": "employment_of_head", "characteristic": f"Sector: {lab}"}
        else:
            continue
        vals = [float(x) for x in v]
        rows.append(_row({**lay, **_L1}, "headcount", vals[0], **cell))
        rows.append(_row({**lay, **_L1}, "poor_share", vals[1], **cell))
        rows.append(_row({**lay, **_L125}, "headcount", vals[2], **cell))
        rows.append(_row({**lay, **_L125}, "poor_share", vals[3], **cell))
        rows.append(_row({**lay, **_L125}, "population_share", vals[4], **cell))
    for cap, line in (("Table 5. 15: Poverty rates by Age Group", _L1),
                      ("Table 5. 16: Poverty rates by Age Group", _L125)):
        page = [p for p in pages if cap in p and "LIST OF TABLE" not in p][-1]
        on = False
        for ln in page.splitlines():
            if cap in ln:
                on = True
                continue
            if not on:
                continue
            m = re.match(r"^(\d{1,2}-\d{1,2}|65\+)\s+(\d+\.\d)\s+(\d+\.\d)\s+(\d+\.\d)\s*$", ln.strip())
            if m:
                cell = {"topic": "age", "characteristic": m.group(1), "age_group": m.group(1)}
                rows.append(_row({**lay, **line}, "headcount", float(m.group(2)), **cell))
                rows.append(_row({**lay, **line}, "poor_share", float(m.group(3)), **cell))
                if line is _L125:
                    rows.append(_row({**lay, **line}, "population_share", float(m.group(4)), **cell))
            elif on and m is None and re.match(r"^(Presented|Table 5.15 above|Integrated)", ln.strip()):
                on = False
    return pd.DataFrame(rows)


LAYOUT = LAYOUT_IHS2003
parse = parse_ihs2003


# ---------------------------------------------------------------- HPS 1998
# "1998 National Household Poverty Survey Report" (CSD), chapter 4, with the
# 1992/93 Household Economic Survey republished beside it. Persons are
# classed Extremely Poor (below the FOOD poverty line), Poor (between the
# food and the overall line) and Non Poor. Only the extremely-poor share is a
# headcount below a line as printed; the overall-line headcount would be
# 100 - "Non Poor", a DERIVED value, so it is not emitted.
LAYOUT_HPS1998 = {**_BASE, "survey": "National Household Poverty Survey 1998",
                  "line_type": "national", "line_level": "extreme",
                  "line_name": "Food poverty line (1998 HPS; 1992 HES basket for 1992)",
                  "period": "1998", "reference_period": "1998", "tables": []}
_DIV = {"Banjul": "Banjul", "KMA": "Kanifing (KMA)", "Western": "Western Division",
        "North Bank": "North Bank Division", "Lower River": "Lower River Division",
        "Central River": "Central River Division", "Upper River": "Upper River Division"}
_SEG = ["Greater Banjul: public workers", "Greater Banjul: private workers",
        "Greater Banjul: informal workers", "Other urban: formal workers",
        "Other urban: informal workers", "Rural: non-groundnut farmers",
        "Rural: small groundnut farmers", "Rural: medium groundnut farmers",
        "Rural: large groundnut farmers", "Rural: non-farm workers", "Not in the workforce"]


def parse_hps1998(path: str) -> pd.DataFrame:
    pages = _pages(path)
    rows = []

    def lay(year):
        if year == "1992":
            return {**LAYOUT_HPS1998, "survey": "Household Economic Survey 1992/93 (as republished 1998)",
                    "period": "1992", "reference_period": "1992/93"}
        return LAYOUT_HPS1998

    def blocks(page, cap):
        """(year, 'Extremely Poor' numbers) pairs in the table after `cap`."""
        txt = page[page.index(cap):]
        out, year = [], None
        for ln in txt.splitlines():
            s = ln.strip()
            if s in ("1992", "1998"):
                year = s
                continue
            m = re.match(r"^Extremely(?: Poor)?\s+((?:\d+\s*)+)$", s)
            if m and year:
                out.append((year, [float(x) for x in m.group(1).split()]))
                if len(out) == 2:
                    break
        return out

    full = "\n".join(pages)
    cap = "Table 4.3.5.1 Percentage Distribution Of Persons In Poverty Categories By Division"
    for year, v in blocks(full, cap):
        if len(v) != 7:
            raise ValueError(f"4.3.5.1 {year}: {v}")
        for d, x in zip(_DIV.values(), v):
            rows.append(_row(lay(year), "headcount", x, geography=d))
    cap = "Table 4.3.5.2 Percentage Distribution Of Persons In Poverty Categories By Urban Category"
    for year, v in blocks(full, cap):
        if len(v) != 3:
            raise ValueError(f"4.3.5.2 {year}: {v}")
        for (loc, lab), x in zip((("other", "Greater Banjul"), ("other", "Other Urban"), ("rural", "Rural")), v):
            rows.append(_row(lay(year), "headcount", x, topic="locality", locality=loc, locality_label=lab))
    cap = "Table 4.3.4.1 Percentage Distribution Of Persons In Poverty Categories By Socioeconomic Group"
    for year, v in blocks(full, cap):
        if len(v) != 12:
            raise ValueError(f"4.3.4.1 {year}: {v}")
        for seg, x in zip(_SEG, v[:11]):
            rows.append(_row(lay(year), "headcount", x, topic="employment_of_head",
                             characteristic=f"Socioeconomic group: {seg}"))
        rows.append(_row(lay(year), "headcount", v[11]))           # All SEGs = national
    # Table 4.2.1.1: households (and persons) below the food line, 1998
    m = re.search(r"Extremely\s+(\d+)\s+(\d+)\s+(\d+)\s+(\d+)\s+(\d+)\s+(\d+)\s+(\d+)\s+(\d+)\s+(\d+)\s+(\d+)\s+(\d+)\s+(\d+)",
                  full[full.index("Table 4.2.1.1 Permanent Income"):])
    if not m:
        raise ValueError("Table 4.2.1.1 not found")
    g = [float(x) for x in m.groups()]
    hh = {**LAYOUT_HPS1998}
    for (loc, lab), x in zip((("other", "Greater Banjul"), ("other", "Other Urban"), ("rural", "Rural")), (g[1], g[4], g[7])):
        r = _row(hh, "headcount", x, topic="locality", locality=loc, locality_label=lab)
        r["unit_of_analysis"] = "household"
        rows.append(r)
    r = _row(hh, "headcount", g[10]); r["unit_of_analysis"] = "household"; rows.append(r)
    if abs(g[11] - rows[[i for i, r in enumerate(rows) if r["period"] == "1998" and r["topic"] == "total"
                         and r["geography"] == "Total country"][0]]["value"]) > 0.5:
        raise ValueError("4.2.1.1 All Areas persons disagrees with 4.3.4.1 All SEGs")
    return pd.DataFrame(rows)
