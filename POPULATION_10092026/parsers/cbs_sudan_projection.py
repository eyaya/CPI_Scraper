"""CBS Sudan -- "Sub-national Population Projections of Sudan and Age-Sex
Composition", 2009-2018, a SECOND Sudan descriptor (sudan_projections.yaml)
beside sudan.yaml (the 2008 census tables).

Projections from the 2008 census for the fifteen states of today's Sudan
(the report post-dates secession; "SUDAN" in Table 1 is their sum):
* Table 1 "The Total Projected Population of States for the Period 2009 to
  2018" -- each state and SUDAN, both sexes;
* Tables 2b-2k, 4b-4k, ... 30b-30k "Projected Population, <State>, <year>"
  -- five-year age bands x Total / Male / Female, per state and year.

NOT READ: Tables 2/2a etc. (2008 "Enumerated" -- the census, already in
sudan.yaml -- and "Smoothed", a model input); the "Young Pop. by Single Ages"
tables; Annex 1 (percent distribution). National age x sex is not printed and
not derived.

State labels follow sudan.yaml (River Nile -> Nahr Elnil, Al Gezira ->
Aljazeera, Al Gedarif -> Algadarif, North/South/West -> Northern/Southern/
Western ...); age bands as printed ("00 - 04" ... "80 +"), as sudan.yaml.

Checks: states sum to SUDAN each year within 3 (Table 1, rounded per state); each state-year table's
Total equals Table 1; bands sum to the Total and Male + Female = Total, both
within 9 (17 rounded bands) and 2 persons respectively, else the gap must
be in _GAPS (Red Sea 2009 and Blue Nile 2013, printed inconsistencies).
"""
from __future__ import annotations

import re

import fitz
import pandas as pd

_STATES = {"Northern": "Northern", "River Nile": "Nahr Elnil", "Red Sea": "Red Sea",
           "Kassala": "Kassala", "Al Gedarif": "Algadarif", "Khartoum": "Khartoum",
           "Al Gezira": "Aljazeera", "White Nile": "White Nile", "Sinnar": "Sinnar",
           "Blue Nile": "Blue Nile", "North Kordofan": "Northern Kordofan",
           "South Kordofan": "Southern Kordofan", "North Darfur": "Northern Darfur",
           "West Darfur": "Western Darfur", "South Darfur": "Southern Darfur"}
_YEARS = [str(y) for y in range(2009, 2019)]
_BANDS = [f"{a:02d} - {a + 4:02d}" for a in range(0, 80, 5)] + ["80 +"]
# PUBLISHED, PINNED (as printed, never corrected):
# * Red Sea 2009 (Table 6b): the male band column sums to 99 below the male
#   Total, and Male + Female misses Total by 3-12 in twelve bands
#   (00 - 04: 90 494 + 73 712 = 164 206, Total printed 164 218);
# * Blue Nile 2013 (Table 20f): Total printed 965 573 (= Table 1), but
#   Male 489 039 + Female 476 634 = 965 673, and the bands sum to 965 674.
_GAPS: dict = {
    ("Red Sea", "2009", "bands", 1): -99.0,
    **{("Red Sea", "2009", b, "sexes"): d for b, d in (
        ("00 - 04", -12.0), ("05 - 09", -12.0), ("10 - 14", -11.0),
        ("15 - 19", -10.0), ("20 - 24", -9.0), ("25 - 29", -8.0),
        ("30 - 34", -7.0), ("35 - 39", -6.0), ("40 - 44", -6.0),
        ("45 - 49", -5.0), ("50 - 54", -3.0), ("55 - 59", -3.0))},
    ("Blue Nile", "2013", "bands", 0): 101.0,
    ("Blue Nile", "2013", "Total", "sexes"): 100.0,
}


def _n(s: str) -> float:
    return float(s.replace(",", ""))


def parse(local_path: str, extras: list[str] | None = None) -> pd.DataFrame:
    with fitz.open(local_path) as doc:
        text = " ".join(" ".join(p.get_text().split()) for p in doc)

    # ---- Table 1
    m = re.search(r"Table 1: The Total Projected Population of States for the Period "
                  r"2009 to 2018 States ((?:\d{4} ){10})(.*?SUDAN(?: [\d,]+){10})", text)
    if not m or m.group(1).split() != _YEARS:
        raise ValueError("CBS Sudan: Table 1 not found")
    t1: dict[str, dict[str, float]] = {}
    names = "|".join(re.escape(k) for k in list(_STATES) + ["SUDAN"])
    for r in re.finditer(rf"({names}) ((?:[\d,]+ ?){{10}})", m.group(2)):
        geo = "Total country" if r.group(1) == "SUDAN" else _STATES[r.group(1)]
        t1[geo] = dict(zip(_YEARS, map(_n, r.group(2).split())))
    if set(t1) != set(_STATES.values()) | {"Total country"}:
        raise ValueError(f"CBS Sudan Table 1: rows {sorted(t1)}")
    for y in _YEARS:
        s = sum(v[y] for g, v in t1.items() if g != "Total country")
        if abs(s - t1["Total country"][y]) > 3:          # rounded per state
            raise ValueError(f"CBS Sudan Table 1 {y}: states {s} != SUDAN {t1['Total country'][y]}")

    # ---- state x year age-sex tables
    states = "|".join(re.escape(k) for k in _STATES)
    # titles vary: "Projected Population, Northern State, 2009" and
    # "Projected Pop. North Darfur State, 2009"; North Darfur 2017 is "26vj"
    pat = re.compile(rf"Table \d+[a-z]+: Projected Pop(?:ulation,|\.) ({states})(?: State)?, (\d{{4}}) "
                     r"Total Total Male Female (.*?)(?=Table \d+[a-z]*:|Annex|$)")
    ages: dict[tuple[str, str], dict[str, tuple[float, float, float]]] = {}
    for t in pat.finditer(text):
        geo, year = _STATES[t.group(1)], t.group(2)
        rows = {}
        for r in re.finditer(r"(Total|\d\d - \d\d|80 \+) ([\d,]+) ([\d,]+) ([\d,]+)", t.group(3)):
            if r.group(1) in rows:
                break                                    # page footer / next block
            rows[r.group(1)] = tuple(map(_n, r.group(2, 3, 4)))
        if set(rows) != set(_BANDS) | {"Total"}:
            raise ValueError(f"CBS Sudan {geo} {year}: rows {sorted(rows)}")
        if (geo, year) in ages:
            raise ValueError(f"CBS Sudan {geo} {year}: printed twice")
        ages[(geo, year)] = rows
    want = {(g, y) for g in _STATES.values() for y in _YEARS}
    if set(ages) != want:
        raise ValueError(f"CBS Sudan: state-year tables missing {sorted(want - set(ages))[:5]}")

    gaps = {}
    for (geo, y), rows in ages.items():
        tot = rows["Total"]
        if tot[0] != t1[geo][y]:
            raise ValueError(f"CBS Sudan {geo} {y}: table Total {tot[0]} != Table 1 {t1[geo][y]}")
        for k in range(3):
            d = sum(rows[b][k] for b in _BANDS) - tot[k]
            if abs(d) > 9:                    # 17 bands, each rounded
                gaps[(geo, y, "bands", k)] = d
        for b, (t, m_, f) in rows.items():
            if abs(m_ + f - t) > 2:
                gaps[(geo, y, b, "sexes")] = m_ + f - t
    if gaps != _GAPS:
        raise ValueError(f"CBS Sudan: published gaps changed: {gaps}")

    out = []

    def rec(sex, age, geo, year, value, code):
        out.append({"series_type": "projection", "sex": sex, "age_group": age,
                    "geography": geo, "period": year, "frequency": "annual",
                    "measure": "count", "value": value, "unit": "persons",
                    "series_code": code})

    rec_tot = set()
    for (geo, y), rows in ages.items():
        for b, vals in rows.items():
            for sex, v in zip(("total", "male", "female"), vals):
                rec(sex, "Total" if b == "Total" else b, geo, y, v, "SD_CBS_PROJ_2009_2018_AGE_SEX")
        rec_tot.add((geo, y))
    for y in _YEARS:                                     # SUDAN: Table 1 only
        rec("total", "Total", "Total country", y, t1["Total country"][y], "SD_CBS_PROJ_2009_2018_T1")
    return pd.DataFrame(out)
