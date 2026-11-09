"""Madagascar -- ENSOMD 2012-2013 (Enquête Nationale sur le Suivi des OMD),
INSTAT, chapter 1.8 "Pauvreté monétaire".

INSTAT says the EPM 2021-22 is NOT comparable with this series (see
madagascar.yaml); ENSOMD 2012 and the EPM rounds it republishes are kept as
their own surveys, never chained to 2021.

Collected:
  1.8.1  trend 2001-2012, P0 for Madagascar / urban / rural on the national
         line and on two international lines, AS PRINTED: "Seuil 1,25$PPA
         actualisé" (national rows) vs "Seuil 1,25$PPA courant" (urban/rural
         rows) are kept as the report names them, and no PPP base year is
         printed (not invented). The 2001/2002/2005/2010 columns are filed as
         "EPM <year> (as republished in ENSOMD 2012-2013)".
  1.8.2  milieu (Capitale, Urbain hors Capitale, Rural): P0, share of the
         poor, P1, share of P1
  1.8.3  the 22 regions, same columns
  1.8.4  socio-economic group of the head: population share, P0, P1
  1.8.5  P0 by household size (persons)
  1.8.6  sex of the head: P0 and extreme P0, households and persons
  1.8.7  marital status of the head: share of households, P0 and extreme P0,
         households and persons
"Intensité" is P1: its Ensemble (32,8) is the national P1 of 1.8.2.
NOT collected: mean household size columns, Graphiques 1.8.1-1.8.3.

CROSS-CHECK (verbatim): 71,5 / 32,8; extreme 52,7 (persons), 42,3
(households); Androy 96,7 / 63,8; DIANA 42,2; Capitale 30,7; trend national
69,6 / 80,7 / 68,7 / 76,5 / 71,5 (2001..2012). Regional shares of the poor sum
to 99,8.
"""
from __future__ import annotations

import re

from .poverty_tables import make_parser

_NAT = {"line_type": "national", "line_level": "overall", "line_name": "Seuil national de pauvreté"}
_EXT = {"line_type": "national", "line_level": "extreme", "line_name": "Seuil de pauvreté extrême"}


def _yr(y):
    if y == "2012":
        return {"period": "2012", "survey": "ENSOMD 2012-2013", "reference_period": "2012-2013"}
    return {"period": y, "survey": f"EPM {y} (as republished in ENSOMD 2012-2013)", "reference_period": y}


_TREND = [{"metric": "headcount", **_yr(y)} for y in ("2001", "2002", "2005", "2010", "2012")]
_INT = lambda name: {"line_type": "international", "line_level": "other", "line_name": name}  # noqa: E731


def _trend_block(start, end, loc):
    rows = [
        {"match": r"^Seuil national(?=\s+\d)", **_NAT, **loc},
        {"match": r"^Seuil 1,25\$PPA actualisé", **_INT("Seuil 1,25$PPA actualisé"), **loc},
        {"match": r"^Seuil 1,25\$PPA courant", **_INT("Seuil 1,25$PPA courant"), **loc},
        {"match": r"^Seuil 2\$PPA actualisé", **_INT("Seuil 2$PPA actualisé"), **loc},
    ]
    return {"page_contains": ["tableau 1.8. 1 : evolution en chiffres"], "start": start, "end": end,
            "exact_numbers": True, "columns": _TREND, "rows": rows}


_REGIONS = ["Androy", "Atsimo Atsinanana", "Vakinankaratra", "Amoron'i Mania", "Anosy", "Sofia",
            "Atsimo Andrefana", "SAVA", "Vatovavy Fitovinany", "Ihorombe", "Bongolava",
            "Haute Matsiatra", "Melaky", "Itasy", "Menabe", "Atsinanana", "Betsiboka",
            "Analanjirofo", "Alaotra Mangoro", "Boeny", "Analamanga", "DIANA"]
# One region, one name: spellings follow the EPM 2021-22 module (madagascar_poverty).
MDG_REGION = {"DIANA": "Diana", "SAVA": "Sava", "Amoron'i Mania": "Amoron’i Mania",
              "Matsiatra Ambony": "Haute Matsiatra"}
_P0P1 = [{"metric": "headcount"}, {"metric": "poor_share"}, {"metric": "gap"}, {"metric": "gap_contribution"}]
_HH_PERS = [{"metric": "headcount", "unit_of_analysis": "household"},
            {"metric": "headcount", "unit_of_analysis": "household", **_EXT},
            {"metric": "headcount"}, {"metric": "headcount", **_EXT}]
_GSE = ["Cadre supérieur", "Cadre moyen", "Ouvrier ou salarié qualifié", "Ouvrier ou salarié non qualifié",
        "Manœuvre", "Stagiaire rémunéré", "Indépendant", "Chômeur", "Inactif", "Petit exploitant agricole",
        "Moyen exploitant agricole", "Grand exploitant agricole", "Pêcheur", "Autres"]

LAYOUT = {
    **_NAT, "survey": "ENSOMD 2012-2013", "welfare_aggregate": "consumption",
    "unit_of_analysis": "person", "frequency": "ad_hoc", "decimal": ",",
    "period": "2012", "reference_period": "2012-2013",
    "tables": [
        _trend_block(r"^Madagascar$", r"^Urbain$", {}),
        _trend_block(r"^Urbain$", r"^Rural$", {"topic": "locality", "locality": "urban", "locality_label": "Urbain"}),
        _trend_block(r"^Rural$", r"^SOURCE", {"topic": "locality", "locality": "rural", "locality_label": "Rural"}),
        {"page_contains": ["tableau 1.8. 2 : différents indicateurs de pauvreté, par milieu"],
         "start": r"^Milieu de résidence", "end": r"^SOURCE", "exact_numbers": True, "columns": _P0P1,
         "rows": [{"match": r"^Capitale(?=\s)", "topic": "locality", "locality": "other", "locality_label": "Capitale"},
                  {"match": r"^Urbain, hors Capitale(?=\s)", "topic": "locality", "locality": "other",
                   "locality_label": "Urbain, hors Capitale"},
                  {"match": r"^Rural(?=\s)", "topic": "locality", "locality": "rural", "locality_label": "Rural"},
                  {"match": r"^Ensemble(?=\s)"}]},
        {"page_contains": ["tableau 1.8. 3 : incidence de la pauvreté, par région"],
         "start": r"^Région P0", "end": r"^Ensemble", "exact_numbers": True, "columns": _P0P1,
         "rows": [{"match": r"^" + re.escape(r) + r"(?=\s+\d)", "geography": MDG_REGION.get(r, r)}
                  for r in _REGIONS]},
        {"page_contains": ["tableau 1.8. 4 : incidence et intensité de la pauvreté"],
         "start": r"^Groupe socioéconomique", "end": r"^Ensemble", "exact_numbers": True,
         "columns": [{"metric": "population_share"}, {"metric": "headcount"}, {"metric": "gap"}],
         "rows": [{"match": r"^" + re.escape(g) + r"(?=\s+\d)", "topic": "employment_of_head",
                   "characteristic": g} for g in _GSE]},
        {"page_contains": ["tableau 1.8. 5 : incidence de la pauvreté, selon la taille du ménage"],
         "start": r"^Taille du ménage", "end": r"^SOURCE", "exact_numbers": True,
         "columns": [{"metric": "headcount", "topic": "household_size", "characteristic": c}
                     for c in ("1 ou 2", "3 ou 4", "5 ou 6", "7 ou plus")] + [{"skip": True}],
         "rows": [{"match": r"^Ratio de pauvreté(?=\s+\d)"}]},
        {"page_contains": ["tableau 1.8. 6 : incidence de la pauvreté, selon le genre du chef"],
         "start": r"^d'individus\)", "end": r"^Ensemble", "exact_numbers": True,
         "columns": [{"skip": True}] + _HH_PERS,
         "rows": [{"match": r"^Masculin(?=\s)", "topic": "sex_of_head", "characteristic": "Masculin", "sex": "male"},
                  {"match": r"^Féminin(?=\s)", "topic": "sex_of_head", "characteristic": "Féminin", "sex": "female"}]},
        {"page_contains": ["tableau 1.8. 6 : incidence de la pauvreté, selon le genre du chef"],
         "start": r"^Féminin", "end": r"^SOURCE", "exact_numbers": True,
         "columns": [{"skip": True}, {"metric": "headcount", "unit_of_analysis": "household"},
                     {"metric": "headcount", "unit_of_analysis": "household", **_EXT},
                     {"skip": True}, {"metric": "headcount", **_EXT}],
         "rows": [{"match": r"^Ensemble(?=\s)"}]},
        {"page_contains": ["tableau 1.8. 7 : incidence de la pauvreté, selon le statut matrimonial"],
         "start": r"^matrimonial", "end": r"^Total", "exact_numbers": True,
         "columns": [{"metric": "population_share", "unit_of_analysis": "household"}, {"skip": True}] + _HH_PERS,
         "rows": [{"match": r"^" + m + r"(?=\s+\d)", "topic": "marital_status_of_head", "characteristic": m}
                  for m in ("Marié", "Divorcé ou Veuf", "Autre célibataire")]},
    ],
}

parse = make_parser(LAYOUT)
