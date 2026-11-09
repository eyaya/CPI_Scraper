"""The Gambia -- monetary-poverty layout (GBoS, "Prevalence of Poverty" reports
of the Integrated Household Survey: IHS 2020 (primary file) and IHS 2015/16
(extra file, for its 2010 columns and 2015/16 food poverty).

Lines are per person per MONTH, per capita consumption:
  2020     absolute GMD 2,236.85, food (extreme) GMD 1,428.17
  2015/16  absolute GMD 1,503.33, food (extreme) GMD 982.89 (Table 3.3)
  2010     "a poverty line was not derived" (2015/16 report, footnote 20) --
           the 2010 estimates are republished without a line value.

Read (each table's year blocks are split out of the report text first; tables
cross page breaks, so the whole document is searched, not one page):
  IHS 2020   Table 18 absolute and Table 19 extreme poverty, 2015/16 and 2020:
             P0 P1 P2, population distribution, share of the poor, number of
             poor -- Gambia, Rural, Urban, Banjul/Kanifing, Other urban, 8 LGAs
             Table 20 FOOD POVERTY 2020 (food expenditure below the food line):
             P0 P1 P2, population, contributions of P0/P1/P2, number of poor
  IHS 2015/16 Table 5.2 / 5.3, the 2010 block only; Table 5.4 food poverty 2015/16

PUBLISHED DEFECT: Table 5.3's 2010 EXTREME block repeats the ABSOLUTE 2010
gap and severity cells (15.6 / 6.8 ...; Banjul's extreme P1 3.3 exceeds its
P0 2.9). Only P0, distribution, share of poor and count are read for it.

Spelling: "Janjangbureh" (2015/16) is filed as Janjanbureh (2020); the 2020
text layer drops spaces ("TheGambia", "Otherurban"). District annexes (A.5-A.8)
are not read -- district and LGA names repeat (Basse, Janjanbureh).

CROSS-CHECK (verbatim): 53.4 / 19.4 / 9.4 (2020); 48.6 / 15.5 / 6.7 (2015/16);
48.1 (2010); extreme 26.3 (2020), 20.8 (2015/16), 21.3 (2010); Kuntaur 86.3;
poor 1,083,373 (2020); food poverty 60.2 (2020), 55.1 (2015/16).
"""
from __future__ import annotations

import re

import pandas as pd

from . import poverty_tables as T

_S = {"skip": True}
_LINES = {
    "2020": {"overall": ("Absolute poverty line 2020", 2236.85),
             "extreme": ("Food poverty line 2020", 1428.17)},
    "2015/16": {"overall": ("Absolute poverty line 2015/16", 1503.33),
                "extreme": ("Food poverty line 2015/16", 982.89)},
    "2010": {"overall": ("Poverty line IHS 2010", ""), "extreme": ("Food poverty line IHS 2010", "")},
}
_YEAR = {"2020": ("2020", "IHS 2020", "2020"), "2015/16": ("2015", "IHS 2015/16", "2015/16"),
         "2010": ("2010", "IHS 2010", "2010")}
_UNIT = "GMD per person per month"


def _cell(y: str, level: str, food: bool = False) -> dict:
    p, s, r = _YEAR[y]
    name, val = _LINES[y]["extreme" if (level == "extreme" or food) else "overall"]
    d = {"period": p, "survey": s, "reference_period": r,
         "line_level": "other" if food else level,
         # The food-poverty "line" is named without its year: it is one series
         # across rounds (its value per round rides in line_value).
         "line_name": "Food poverty (food consumption below the food poverty line)" if food else name,
         "line_value": val, "line_unit": _UNIT if val != "" else ""}
    return d


_FGT6 = [{"metric": "headcount"}, {"metric": "gap"}, {"metric": "severity"},
         {"metric": "population_share"}, {"metric": "poor_share"}, {"metric": "poor_count"}]
_EX2010 = [{"metric": "headcount"}, _S, _S, {"metric": "population_share"},
           {"metric": "poor_share"}, {"metric": "poor_count"}]
_FOOD = [{"metric": "headcount"}, {"metric": "gap"}, {"metric": "severity"},
         {"metric": "population_share"}, {"metric": "poor_share"},
         {"metric": "gap_contribution"}, {"metric": "severity_contribution"}, _S,
         {"metric": "poor_count"}]

_LGA = [("Banjul", r"Banjul"), ("Kanifing", r"Kanifing(?: ?Municipal)?"), ("Brikama", r"Brikama"),
        ("Mansakonko", r"Mansakonko"), ("Kerewan", r"Kerewan"), ("Kuntaur", r"Kuntaur"),
        ("Janjanbureh", r"Janjang?bureh"), ("Basse", r"Basse")]


def _rows():
    n = r"(?=\s+\d)"
    rows = [{"match": r"^THE ?GAMBIA" + n},
            {"match": r"^Rural" + n, "topic": "locality", "locality": "rural", "locality_label": "Rural"},
            {"match": r"^Urban" + n, "topic": "locality", "locality": "urban", "locality_label": "Urban"},
            {"match": r"^Banjul/Kanifing" + n, "topic": "locality", "locality": "other",
             "locality_label": "Banjul/Kanifing"},
            {"match": r"^Other ?urban" + n, "topic": "locality", "locality": "other",
             "locality_label": "Other urban"}]
    rows += [{"match": rf"^{pat}{n}", "geography": geo} for geo, pat in _LGA]
    return rows


def _t(key, year, level, cols, food=False):
    return {"page_contains": [key, f"<<{year}>>"], "defaults": _cell(year, level, food),
            "exact_numbers": True, "columns": cols, "rows": _rows()}


LAYOUT = {
    "survey": "IHS 2020", "welfare_aggregate": "consumption", "unit_of_analysis": "person",
    "frequency": "ad_hoc", "decimal": ".", "line_type": "national",
    "line_level": "overall", "line_name": "Absolute poverty line 2020",
    "line_value": 2236.85, "line_unit": _UNIT, "period": "2020", "reference_period": "2020",
    "tables": [
        _t("[t18]", "2015/16", "overall", _FGT6), _t("[t18]", "2020", "overall", _FGT6),
        _t("[t19]", "2015/16", "extreme", _FGT6), _t("[t19]", "2020", "extreme", _FGT6),
        _t("[t20]", "2020", "other", _FOOD, food=True),
        _t("[t52]", "2010", "overall", _FGT6), _t("[t53]", "2010", "extreme", _EX2010),
        _t("[t54]", "2015/16", "other", _FOOD, food=True),
    ],
}

# (key, caption regex, end regex, year of an undated table)
_SEGMENTS_2020 = [("[t18]", r"Table ?18 ?: ?Poverty ?Measure ?Trends", r"^Note", None),
                  ("[t19]", r"^Table ?19 ?: ?Extreme ?Poverty", r"^Note", None),
                  ("[t20]", r"^Table ?20 ?: ?Food ?Poverty", r"^\d{2}$", "2020")]
_SEGMENTS_2016 = [("[t52]", r"^Table 5\.2: Poverty Measure Trends", r"^Note", None),
                  ("[t53]", r"^Table 5\.3: Extreme Poverty", r"^Note", None),
                  ("[t54]", r"^Table 5\.4: Food Poverty", r"^\d{2}$", "2015/16")]
_YEAR_LINE = re.compile(r"^(2010|2015/16|2020)$", re.M)


def _segments(path: str, specs) -> list[str]:
    pages = T._pages(path, halves=False)["full"]
    doc = "\n".join(pages)
    out = []
    for key, cap, end, year in specs:
        # The LAST occurrence: the list of tables carries every caption first.
        found = list(re.finditer(cap, doc, re.M))
        m = found[-1] if found else None
        if not m:
            raise ValueError(f"{path}: caption {cap!r} not found")
        tail = doc[m.end():]
        e = re.search(end, tail, re.M)
        seg = tail[: e.start()] if e else tail
        if year:
            out.append(f"{key}\n<<{year}>>\n{seg}")
            continue
        marks = list(_YEAR_LINE.finditer(seg))
        for k, mk in enumerate(marks):
            stop = marks[k + 1].start() if k + 1 < len(marks) else len(seg)
            out.append(f"{key}\n<<{mk.group(1)}>>\n{seg[mk.end():stop]}")
    return out


def parse(path: str, extras: list[str] | None = None) -> pd.DataFrame:
    pseudo = _segments(path, _SEGMENTS_2020)
    old = [e for e in (extras or []) if "2015" in e]
    if old:
        pseudo += _segments(old[0], _SEGMENTS_2016)
    pages = {"full": pseudo}
    rows, misses = [], []
    for t, tbl in enumerate(LAYOUT["tables"]):
        if not old and tbl["page_contains"][0] in ("[t52]", "[t53]", "[t54]"):
            continue
        got, matched = T._parse_table(pages, LAYOUT, tbl, "2020", "2020")
        rows.extend(got)
        misses += [f"{tbl['page_contains']}.{r['match']!r}"
                   for ri, r in enumerate(tbl["rows"]) if ri not in matched]
    if misses:
        raise ValueError(f"{len(misses)} Gambia row spec(s) matched nothing: {misses[:6]}")
    return pd.DataFrame.from_records(rows)
