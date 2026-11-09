"""Benin -- monetary-poverty layout (INStaD, "Note sur la pauvreté en 2022",
EHCVM 2021-2022, Oct 2023, 4 pp).

Fieldwork Nov 2021 - Jan 2022 and Apr - Jul 2022. INStaD labels the round
"2022" and the first round "2019"; filed as periods 2021 and 2018 (references
"2021-2022" / "2018-2019") like every other WAEMU EHCVM round in this package.
Line 287 187 FCFA per person per year (food 171 936); welfare = consumption
per head.

P1 AND P2 ARE PRINTED ON 0-1 (0,1000 = 10,0%) -- unit "index"; value_std puts
them on the percent scale. P0 is a percentage.

Collected: Tableau 1 (Urbain / Rural / Bénin, 2022) and Tableau 2 (12
departments, P0 P1 P2 for 2019 and 2022; its Bénin row is read for 2019 only,
2022 being Tableau 1's). Not collected: Graphique 1 (departments' P0 again)
and Graphique 2 (2019 urban/rural P0 -- printed as chart labels and in prose,
not in a table).

CROSS-CHECK (verbatim): 2022 P0 36,2 / P1 0,1000 / P2 0,0395; 2019 38,5 /
0,1077 / 0,0431; urban 30,8, rural 40,6; Ouémé 16,0, Couffo 54,1, Atacora
2019 60,5.
"""
from __future__ import annotations
import re

from .poverty_tables import make_parser

_DEPTS = ["Alibori", "Atacora", "Atlantique", "Borgou", "Collines", "Couffo", "Donga",
          "Littoral", "Mono", "Ouémé", "Plateau", "Zou"]
_R18 = {"period": "2018", "survey": "EHCVM 2018-2019", "reference_period": "2018-2019",
        "line_value": "", "line_unit": ""}
_IDX = {"unit": "index"}
_T2 = [{"metric": "headcount", **_R18}, {"metric": "gap", **_R18, **_IDX},
       {"metric": "severity", **_R18, **_IDX},
       {"metric": "headcount"}, {"metric": "gap", **_IDX}, {"metric": "severity", **_IDX}]

LAYOUT = {
    "survey": "EHCVM 2021-2022", "welfare_aggregate": "consumption",
    "unit_of_analysis": "person", "frequency": "ad_hoc", "decimal": ",",
    "line_type": "national", "line_level": "overall",
    "line_name": "Seuil global de pauvreté", "line_value": 287187,
    "line_unit": "XOF per person per year",
    "period": "2021", "reference_period": "2021-2022",
    "tables": [
        {"page_contains": ["tableau 1", "selon le milieu de résidence en 2022"],
         "exact_numbers": True,
         "columns": [{"metric": "headcount"}, {"metric": "gap", **_IDX},
                     {"metric": "severity", **_IDX}],
         "rows": [{"match": r"^Urbain(?=\s+\d)", "topic": "locality", "locality": "urban",
                   "locality_label": "Urbain"},
                  {"match": r"^Rural(?=\s+\d)", "topic": "locality", "locality": "rural",
                   "locality_label": "Rural"},
                  {"match": r"^Bénin(?=\s+\d)"}]},
        {"page_contains": ["tableau 2", "selon le département"], "exact_numbers": True,
         "columns": _T2,
         "rows": [{"match": r"^" + re.escape(d) + r"(?=\s+\d)", "geography": d} for d in _DEPTS]
         + [{"match": r"^Bénin(?=\s+\d)", "columns": _T2[:3] + [{"skip": True}] * 3}]},
    ],
}

parse = make_parser(LAYOUT)
