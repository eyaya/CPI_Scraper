"""Djibouti -- monetary poverty (DISED, now INSTAD; EDAM4-IS 2017).

"Rapport 1 : résultats EDAM4" -- Wayback copy of DISED's own file (INSTAD's
current API carries no EDAM poverty report; EDAM appears there only as a
microdata catalogue entry). Two lines, both per adult equivalent per year:
extreme 111 783 FD, global 151 391 FD (Tableau 3).

Collected:
  Tableau 4  P0 on the extreme and the global line: National, Djibouti ville,
             Autres régions, Autre urbain, Rural.
  Tableau 8  the same two P0s for Djibouti ville's five arrondissements.
  Tableau 5  extreme P0 of children 0-17, men and women (18+), for National,
             Djibouti ville, Autres régions and Rural. Footnote 7: these are
             shares of each group living in extremely poor HOUSEHOLDS.

NOT collected: the "Écart de pauvreté" and "Sévérité" rows of Tableaux 4/8.
The report never states which of its two lines they are computed on (they
sit between the extreme and the global headcount), and attaching them to a
line would be a guess. Gini and p90/p10 belong to inequality.

THE DECIMAL COMMA IS A SPACE IN THE TEXT LAYER: Tableau 4 reads "21 1% 13 6%
45 0%" -- the glyph at the comma's position is a literal space character. The
prose prints the same values with commas (21,1 %, 13,6 %, 45,0 %, 35,8 %,
59,8 %; 18,3 % / 15,8 % for the 4th/5th arrondissements). On those two
pages only, "<1-2 digits><space><1 digit>%" is rewritten to a comma decimal.
"""
from __future__ import annotations
import re

import pandas as pd

from . import poverty_tables as T

_EXT = {"line_level": "extreme", "line_name": "Seuil de pauvreté extrême EDAM4 2017",
        "line_value": 111783}
_GLO = {"line_level": "overall", "line_name": "Seuil de pauvreté global EDAM4 2017",
        "line_value": 151391}

_T4_COLS = [{}, {"geography": "Djibouti ville"},
            {"topic": "locality", "locality": "other", "locality_label": "Autres régions"},
            {"topic": "locality", "locality": "other", "locality_label": "Autre urbain"},
            {"topic": "locality", "locality": "rural", "locality_label": "Rural"}]
_ARR = ["1er arr.", "2ème arr.", "3ème arr.", "4ème arr.", "5ème arr."]
_T8_COLS = [{"geography": "Djibouti ville"}] + [{"geography": f"Djibouti ville - {a}"} for a in _ARR]
# No `topic` here: a column spec wins over the row's, and these rows are cut
# by age / sex -- the column only adds the locality.
_T5_COLS = [{}, {"geography": "Djibouti ville"},
            {"locality": "other", "locality_label": "Autres régions"},
            {"locality": "rural", "locality_label": "Rural"}]


def _cols(base, **attrs):
    return [{"metric": "headcount", **c, **attrs} for c in base]


LAYOUT = {
    "survey": "EDAM4-IS 2017", "welfare_aggregate": "consumption",
    "unit_of_analysis": "person", "frequency": "ad_hoc", "decimal": ",",
    "percent_cells": True,
    "line_type": "national", "line_level": "extreme",
    "line_name": "Seuil de pauvreté extrême EDAM4 2017", "line_value": 111783,
    "line_unit": "DJF per adult equivalent per year",
    "period": "2017", "reference_period": "2017",
    "tables": [
        {"page_contains": ["tableau 4. indicateurs de pauvreté et inégalité"],
         "exact_numbers": True, "columns": _cols(_T4_COLS),
         "rows": [{"match": r"^Pauvreté extrême(?=\s+\d)", **_EXT},
                  {"match": r"^Pauvreté globale(?=\s+\d)", **_GLO}]},
        {"page_contains": ["tableau 8. indicateurs de pauvreté et inégalité à djibouti ville"],
         "exact_numbers": True, "columns": _cols(_T8_COLS),
         # Djibouti ville's own column repeats Tableau 4 -- read from there only.
         "rows": [{"match": r"^Pauvreté extrême(?=\s+\d)", **_EXT},
                  {"match": r"^Pauvreté globale(?=\s+\d)", **_GLO}]},
        {"page_contains": ["tableau 5. taux de pauvreté extrême des individus par groupe"],
         "exact_numbers": True, "columns": _cols(_T5_COLS),
         "rows": [{"match": r"^Taux de pauvreté des enfants \(0-17 ans\)", "topic": "age",
                   "characteristic": "Enfants (0-17 ans)", "age_group": "0-17 ans", **_EXT},
                  {"match": r"^Taux de pauvreté des hommes(?=\s+\d)", "topic": "sex",
                   "characteristic": "Hommes", "sex": "male", "age_group": "18 ans et plus", **_EXT},
                  {"match": r"^Taux de pauvreté des femmes(?=\s+\d)", "topic": "sex",
                   "characteristic": "Femmes", "sex": "female", "age_group": "18 ans et plus", **_EXT}]},
    ],
}

_LOST_COMMA = re.compile(r"(?<![\d,])(\d{1,2}) (\d)%")


def parse(path: str) -> pd.DataFrame:
    pages = T._pages(path, halves=False)
    pages["full"] = [_LOST_COMMA.sub(r"\1,\2%", t)
                     if re.search(r"Tableau [48]\. Indicateurs de pauvreté", t) else t
                     for t in pages["full"]]
    period, reference = T._resolve_period(pages["full"], LAYOUT)
    rows = []
    for tbl in LAYOUT["tables"]:
        got, matched = T._parse_table(pages, LAYOUT, tbl, period, reference)
        if len(matched) != len(tbl["rows"]):
            raise ValueError(f"{tbl['page_contains']}: {len(matched)}/{len(tbl['rows'])} rows matched")
        rows += got
    out = pd.DataFrame(rows)
    # Tableau 8's Djibouti-ville column duplicates Tableau 4's.
    dup = out.duplicated(["metric", "geography", "topic", "characteristic", "line_level",
                          "locality_label", "sex", "age_group"], keep="first")
    return out[~dup].reset_index(drop=True)
