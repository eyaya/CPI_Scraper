"""Madagascar -- EPM 2004, INSTAT rapport principal (janvier 2006), chapter XII.

Person level, national line; "Intensité" = P1.
Collected:
  151  P0, P1 and population share for the six former provinces x urban/rural
       (province named "<name> (province)", as in the EPM 2005 module), plus
       the national Ensemble
  154  P0 by household size x milieu (the dependency ratios printed in
       brackets on their own lines are not read)
  155  P0, P1 and contribution by socio-economic group of the head
NOT collected: 152 (2001/2002/2004 by province with Atkinson/Gini indices):
its 2004 "Antananarivo Urbain" P0 is 50,2 against Tableau 151's 39,2 -- the
two tables do not use the same urban stratum -- and its 2001/2002 columns are
collected from the EPM 2002/2005 reports; 153 (decile ratios, inequality).

CROSS-CHECK (verbatim): 72,1 / 31,6; Fianarantsoa rural 87,5 / 41,5;
Antsiranana urban 36,7; Petit exploitant agricole 84,3 (46,4 % of the poor);
singleton 19,0. Contributions by GSE sum to 99,9.
"""
from __future__ import annotations

import re

from .poverty_tables import make_parser

_PROV = ["Antananarivo", "Fianarantsoa", "Toamasina", "Mahajanga", "Toliara", "Antsiranana"]
_UL = {"locality": "urban", "locality_label": "Urbain"}
_RL = {"locality": "rural", "locality_label": "Rural"}
_C151 = [{"metric": "headcount"}, {"metric": "gap"}, {"metric": "population_share"}, {"skip": True}]


def _prov_block(p, nxt):
    g = {"geography": f"{p} (province)", "topic": "locality"}
    return {"page_contains": ["tableau 151 : indicateurs de pauvreté par strate en 2004"],
            "start": rf"^{p} Urbain", "start_inclusive": True, "end": rf"^{nxt}\b",
            "exact_numbers": True, "columns": _C151, "rows": [
                {"match": rf"^{p} Urbain(?=\s)", **g, **_UL},
                {"match": r"^Rural(?=\s)", **g, **_RL}]}


LAYOUT = {
    "survey": "EPM 2004", "welfare_aggregate": "consumption", "unit_of_analysis": "person",
    "frequency": "ad_hoc", "decimal": ",", "line_type": "national", "line_level": "overall",
    "line_name": "Seuil national de pauvreté", "period": "2004", "reference_period": "2004",
    "tables": [
        *[_prov_block(p, n) for p, n in zip(_PROV, _PROV[1:] + ["Ensemble"])],
        {"page_contains": ["tableau 151 : indicateurs de pauvreté par strate en 2004"],
         "start": r"^Antsiranana Urbain", "end": r"^Source", "exact_numbers": True,
         "columns": [{"metric": "headcount"}, {"metric": "gap"}, {"skip": True}, {"skip": True}],
         "rows": [{"match": r"^Ensemble(?=\s)"}]},
        {"page_contains": ["tableau 154 : ratio de pauvreté selon le milieu et la taille"],
         "start": r"^Urbain Rural Ensemble", "end": r"^Ensemble", "exact_numbers": True,
         "columns": [{"metric": "headcount", **_UL}, {"metric": "headcount", **_RL}, {"metric": "headcount"}],
         "rows": [{"match": r"^" + re.escape(l) + r"(?=\s+\d)", "topic": "household_size", "characteristic": c}
                  for l, c in (("Singleton", "Singleton (1 personne)"), ("De 2 à 4", "2 à 4"),
                               ("De 5 à 7", "5 à 7"), ("De 8 à 10", "8 à 10"), ("Plus de 11", "plus de 11"))]},
        {"page_contains": ["tableau 155 : indicateurs de pauvreté selon les groupe socio-economique"],
         "start": r"^Ratio de pauvreté Intensité", "end": r"^Ensemble", "exact_numbers": True,
         "columns": [{"metric": "headcount"}, {"metric": "gap"}, {"metric": "poor_share"}],
         "rows": [{"match": r"^" + re.escape(g) + r"(?=\s+\d)", "topic": "employment_of_head", "characteristic": g}
                  for g in ("Cadre supérieur", "Cadre moyen ou agent de maîtrise", "Ouvrier ou salarié qualifié",
                            "Ouvrier non qualifié", "Manœuvre", "Stagiaire rémunéré", "Indépendant", "Chômeur",
                            "Inactif", "Petit exploitant agricole", "Moyen exploitant agricole",
                            "Grand exploitant agricole", "Pêcheur", "Autre")]},
    ],
}

parse = make_parser(LAYOUT)
