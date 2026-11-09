"""Central African Republic -- monetary poverty (ICASEES, EHCVM 2021).

"Rapport sur les indicateurs de pauvreté en RCA 2021" (16 Feb 2023), Tableau
2.1: national, milieu and the 7 regions (Bangui is printed twice, as a milieu
stratum and as a region, with identical values -- both kept, as a locality
stratum and as a geography). National line 722 FCFA per person per day;
consumption per capita.

Columns (the header is broken across lines in the text layer; the order is
confirmed by the prose, p.3: P0 68,8 %, P1 31,1 %, 4,1 million poor):

    % population | P0 | poor ('000) | contribution | P1 | P2

The count of poor is printed in THOUSANDS; the schema's poor_count is in
persons and values are never rescaled, so it is not collected.
Not collected: the US$2.15 (2017 PPP) rate 65,1 % (prose only), Tableau 4.2
(rotated text, unreadable), Gini (inequality indicator).
"""
from __future__ import annotations

from .poverty_tables import make_parser

_COLS = [{"metric": "population_share"}, {"metric": "headcount"}, {"skip": True},
         {"metric": "poor_share"}, {"metric": "gap"}, {"metric": "severity"}]
_REGIONS = ["Plateaux", "Equateur", "Yadé", "Kagas", "Fertit", "Haut-Oubangui", "Bangui"]

LAYOUT = {
    "survey": "EHCVM 2021", "welfare_aggregate": "consumption",
    "unit_of_analysis": "person", "frequency": "ad_hoc", "decimal": ".",
    "line_type": "national", "line_level": "overall",
    "line_name": "Seuil de pauvreté national 2021", "line_value": 722,
    "line_unit": "XAF per person per day",
    "period": "2021", "reference_period": "2021",
    "tables": [
        {"page_contains": ["mesures de la pauvreté, nombre de pauvres"],
         "start": r"^Total 100", "start_inclusive": True, "end": r"^Regions",
         "exact_numbers": True, "columns": _COLS,
         "rows": [
             {"match": r"^Total(?=\s+\d)"},
             {"match": r"^Urban(?=\s+\d)", "topic": "locality", "locality": "urban", "locality_label": "Urban"},
             {"match": r"^Bangui(?=\s+\d)", "topic": "locality", "locality": "other", "locality_label": "Bangui"},
             {"match": r"^Other urban(?=\s+\d)", "topic": "locality", "locality": "other", "locality_label": "Other urban"},
             {"match": r"^Rural(?=\s+\d)", "topic": "locality", "locality": "rural", "locality_label": "Rural"}]},
        {"page_contains": ["mesures de la pauvreté, nombre de pauvres"],
         "start": r"^Regions", "exact_numbers": True, "columns": _COLS,
         "rows": [{"match": r"^" + r + r"(?=\s+\d)", "geography": r} for r in _REGIONS]},
    ],
}

parse = make_parser(LAYOUT)
