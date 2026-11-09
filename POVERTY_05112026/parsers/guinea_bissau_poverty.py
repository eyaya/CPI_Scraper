"""Guinea-Bissau -- monetary poverty, ILAP 2010 (INE, "Evaluation de la
pauvreté", Bissau, December 2010, VERSION PROVISOIRE).

Published by INE Guinea-Bissau in its own publication list (Publicações /
ILAP / perfil_pbreza_2010.pdf); written by a consultant (M. B. Sylla, ANSD
Senegal, for the World Bank). It is the newest monetary-poverty TABLE INE
publishes: the EHCVM 2018/19 results appear on stat-guinebissau.com only as a
chart script whose arrays are placeholders (P1 = 10000, 5989 ...), refused.

TWO INTERNATIONAL LINES, and no national line: US$1 PPA a day ("extrême
pauvreté", 110 400 FCFA a person a year in 2010) and US$2 PPA ("pauvreté",
220 800 FCFA). The PPP base year is not stated. Filed as line_type
international, line_level extreme / overall as the report itself designates
them.

Collected:
  Tableau 5   P0 for Bissau / Autres régions / Ensemble, 2010 and 2002, both
              lines. Its counts of poor run every three-digit group together
              ("48 991 434 483 483 474 ...") and cannot be split from the text
              layer -- not read.
  Tableaux 6 / 7 (US$2 / US$1, 2010): P0, number of poor and share of the poor
              by sex, age, education of the head and household size, for
              Bissau, Autres régions and Ensemble; and by region (8 regions; S.A.B
              is skipped, its cells fuse). Wrapped labels ("Moins de 35" / "ans ...") are
              re-joined by `_FIXES`. Not read: "Proff or Médico" and "Outros"
              (wrapped / "463 100,0" fuses), the TOTAL row ("189 570 100"
              fuses; Tableau 5 carries the totals).
Not collected: Tableaux 8.x (structure of the poor and of the population --
distributions, not poverty measures), 1-4 (socio-economic indicators).

CROSS-CHECK (verbatim): US$2 P0 69,3 (2010) / 64,7 (2002); US$1 33,0 / 20,8;
Bissau US$2 51,0, Autres régions 75,6; Gabou 83,5; female head US$2 65,3.
"""
from __future__ import annotations
import re

import pandas as pd

from . import poverty_tables as T
from ._vocab import label_rows

_D1 = {"line_level": "extreme", "line_name": "US$1 PPA par jour",
       "line_value": 110400, "line_unit": "XOF per person per year"}
_D2 = {"line_level": "overall", "line_name": "US$2 PPA par jour",
       "line_value": 220800, "line_unit": "XOF per person per year"}
_P02 = {"period": "2002", "survey": "ILAP 2002", "reference_period": "2002",
        "line_value": "", "line_unit": ""}
_LOCS = [("other", "Bissau"), ("other", "Autres régions"), ("all", "Total")]


def _t5_cols(year_extra):
    cols = []
    for line in (_D1, _D2):
        for loc, lab in _LOCS:
            cols.append({"metric": "headcount", "locality": loc, "locality_label": lab,
                         **({"topic": "locality"} if loc != "all" else {}),
                         **line, **year_extra})
    return cols


def _cut_cols(line):
    cols = []
    for loc, lab in _LOCS:
        cols += [{"skip": True},
                 {"metric": "headcount", "locality": loc, "locality_label": lab, **line},
                 {"metric": "poor_count", "locality": loc, "locality_label": lab, **line},
                 {"metric": "poor_share", "locality": loc, "locality_label": lab, **line}]
    return cols


def _cut_table(caption, line):
    rows = ([{"match": r"^Masculino(?=\s+\d)", "topic": "sex_of_head",
              "characteristic": "Masculino", "sex": "male"},
             {"match": r"^Féminino(?=\s+\d)", "topic": "sex_of_head",
              "characteristic": "Féminino", "sex": "female"}]
            + label_rows("age_of_head", ["Moins de 35 ans", "35 - 55 ans", "55 ans et plus"])
            + label_rows("education_of_head", ["Nehunm", "Basico.", "secondary", "Superior"])
            + label_rows("household_size", ["1 - 4 personnes", "5 - 8 personnes",
                                            "9 - 11 personnes", "12 personnes et +"]))
    regions = [("Tombali", "Tombali"), ("Quinara", "Quinara"), ("Oio", "Oio"),
               ("Biombo", "Biombo"), ("Bolama/Bijag", "Bolama/Bijagos"),
               ("Bafata", "Bafata"), ("Gabou", "Gabu"), ("Cacheu", "Cacheu")]
    # NOT S.A.B: it prints Bissau's four cells and then the Ensemble four, and
    # "189 570 371 610" fuses into one number -- Bissau is in Tableau 5.
    reg_cols = [{"skip": True}, {"metric": "headcount", **line},
                {"metric": "poor_count", **line}, {"metric": "poor_share", **line}]
    return [
        {"page_contains": caption, "exact_numbers": True, "columns": _cut_cols(line),
         "defaults": {}, "rows": rows},
        # region rows print one group of four
        {"page_contains": caption, "columns": reg_cols, "take": "leading",
         "rows": [{"match": r"^" + re.escape(p) + r"(?=\s+\d)", "geography": g}
                  for p, g in regions]},
    ]


LAYOUT = {
    "survey": "ILAP 2010", "welfare_aggregate": "consumption",
    "unit_of_analysis": "person", "frequency": "ad_hoc", "decimal": ",",
    "line_type": "international", "line_level": "overall",
    "line_name": "US$2 PPA par jour",
    "period": "2010", "reference_period": "2010",
    "tables": [
        {"page_contains": ["tableau n° 5", "evolution de l’incidence de pauvreté"],
         "exact_numbers": True, "columns": _t5_cols({}),
         "rows": [{"match": r"^P Incidence \(%\) 2010"}]},
        {"page_contains": ["tableau n° 5", "evolution de l’incidence de pauvreté"],
         "exact_numbers": True, "columns": _t5_cols(_P02),
         "rows": [{"match": r"^P Incidence \(%\) 2002"}]},
    ],
}
def _pages_fixed(path: str) -> dict[str, list[str]]:
    pages = T._pages(path, halves=False)
    full = []
    for p in pages["full"]:
        for pat, rep in _FIXES:
            p = re.sub(pat, rep, p, flags=re.M)
        full.append(p)
    # Tableaux 6 and 7 each run across two pages, the second without its
    # caption: join each with its continuation so one table spec reads both.
    joined = []
    for i, p in enumerate(full):
        if re.search(r"Tableau n° [67] :", p) and i + 1 < len(full):
            p = p + "\n" + full[i + 1]
        joined.append(p)
    return {"full": joined}


_FIXES = [
    (r"^Moins de 35\nans ", "Moins de 35 ans "),
    (r"^55 ans et\nplus ", "55 ans et plus "),
    (r"^(\d+ - \d+)\npersonnes ", r"\1 personnes "),
    (r"^12 personnes\net \+ ", "12 personnes et + "),
    (r"^Bolama/Bija\ng ", "Bolama/Bijag "),
]


def parse(path: str) -> pd.DataFrame:
    pages = _pages_fixed(path)
    period, ref = T._resolve_period(pages["full"], LAYOUT)
    tables = list(LAYOUT["tables"])
    tables += _cut_table(["tableau n° 6", "us $ 2 ppa"], _D2)
    tables += _cut_table(["tableau n° 7", "us $ 1 ppa"], _D1)
    rows, misses = [], []
    for i, tbl in enumerate(tables):
        got, matched = T._parse_table(pages, LAYOUT, tbl, period, ref)
        rows += got
        misses += [f"table[{i}].{r['match']!r}" for j, r in enumerate(tbl.get("rows", []))
                   if j not in matched]
    if misses:
        raise ValueError(f"Guinea-Bissau: {len(misses)} row spec(s) matched nothing: {misses}")
    return pd.DataFrame.from_records(rows)
