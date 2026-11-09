"""Madagascar -- EPM 2010 (Enquête Périodique auprès des Ménages), INSTAT
rapport principal (août 2011), chapter XI "Pauvreté et inégalité".

National line 468 800 Ar per person per year (2005's line updated by
inflation in the capital); extreme = consumption below the food line,
328 162 Ar per year (2 133 kcal/day). Consumption per capita, person level.
"Intensité de pauvreté" is the FGT P1 (§353, §357). INSTAT says EPM 2021-22 is
not comparable with this series.

Collected:
  172  22 regions x Urbain / Rural / Ensemble: P0 and P1
  173  P0 95% confidence bounds for urban, rural, the 22 regions, national
  174  P0 1993-2010 by milieu  -- the EPM series on one comparable basis; the
  175  P1 1993-2010 by milieu     pre-2010 columns are filed as "EPM <year> (as
                                 republished in EPM 2010)"
  177  P0 by socio-economic group of the head
  180  P0 by household size x sex of the head
  182  extreme and overall P0 by milieu
  183  extreme and overall P0 by education of the head
NOT collected: 176 (slum dwellers -- no topic), 178/179 (subjective welfare
classes), 181 (children under 5 -- no topic), 184/185 (total gaps in billions
of Ar -- no metric), the 2010/2005 variation columns.

Region names follow the EPM 2021-22 module ("Matsiatra Ambony" -> Haute
Matsiatra, DIANA -> Diana, SAVA -> Sava).

CROSS-CHECK (verbatim): 76,5 / 34,9; urban 54,2, rural 82,2; extreme 56,5;
Atsimo Atsinanana 94,5; CI 74,9678-78,0368; 1993 70,0, 2002 80,7, 2005 68,7;
Supérieur 21,3.
"""
from __future__ import annotations

import re

from ._vocab import label_rows
from .madagascar_ensomd_poverty import MDG_REGION
from .poverty_tables import make_parser

_REG = ["Analamanga", "Vakinankaratra", "Itasy", "Bongolava", "Matsiatra Ambony", "Amoron'i Mania",
        "Vatovavy Fitovinany", "Ihorombe", "Atsimo Atsinanana", "Atsinanana", "Analanjirofo",
        "Alaotra Mangoro", "Boeny", "Sofia", "Betsiboka", "Melaky", "Atsimo Andrefana", "Androy",
        "Anosy", "Menabe", "DIANA", "SAVA"]
_EXT = {"line_level": "extreme", "line_name": "Seuil alimentaire (pauvreté extrême)",
        "line_value": 328162}
_U = {"topic": "locality", "locality": "urban", "locality_label": "Urbain"}
_R = {"topic": "locality", "locality": "rural", "locality_label": "Rural"}


def _reg_rows():
    return [{"match": r"^" + re.escape(r) + r"(?=\s+\d)", "geography": MDG_REGION.get(r, r)} for r in _REG]


def _years(metric):
    out = []
    for y in ("1993", "1997", "1999", "2001", "2002", "2004", "2005", "2010"):
        sv = "EPM 2010" if y == "2010" else f"EPM {y} (as republished in EPM 2010)"
        extra = {} if y == "2010" else {"line_value": "", "line_unit": ""}
        out.append({"metric": metric, "period": y, "reference_period": y, "survey": sv, **extra})
    return out + [{"skip": True}]


def _trend(caption, metric, num):
    # 174 and 175 share a page and the same "Milieu Année ..." header, so each
    # block starts at its OWN caption (from the first header, 175 read 174's rows).
    return {"page_contains": [caption], "start": rf"^Tableau {num} :", "end": r"^Source", "exact_numbers": True,
            "columns": _years(metric),
            "rows": [{"match": r"^Urbain(?=\s)", **_U}, {"match": r"^Rural(?=\s)", **_R},
                     {"match": r"^Ensemble(?=\s)"}]}


LAYOUT = {
    "survey": "EPM 2010", "welfare_aggregate": "consumption", "unit_of_analysis": "person",
    "frequency": "ad_hoc", "decimal": ",", "line_type": "national", "line_level": "overall",
    "line_name": "Seuil national de pauvreté", "line_value": 468800, "line_unit": "MGA per person per year",
    "period": "2010", "reference_period": "2010",
    "tables": [
        {"page_contains": ["tableau 172 : ratio et intensité de pauvreté, selon le milieu, par région"],
         "start": r"^Région Urbain", "end": r"^Ensemble", "exact_numbers": True,
         "columns": [{"metric": "headcount", **_U}, {"metric": "headcount", **_R}, {"metric": "headcount"},
                     {"metric": "gap", **_U}, {"metric": "gap", **_R}, {"metric": "gap"}],
         "rows": _reg_rows()},
        {"page_contains": ["tableau 172 : ratio et intensité de pauvreté, selon le milieu, par région"],
         "start": r"^SAVA", "end": r"^Source", "exact_numbers": True,
         "columns": [{"metric": "headcount", **_U}, {"metric": "headcount", **_R}, {"metric": "headcount"},
                     {"metric": "gap", **_U}, {"metric": "gap", **_R}, {"metric": "gap"}],
         "rows": [{"match": r"^Ensemble(?=\s)"}]},
        {"page_contains": ["tableau 1733 : précision des ratios de pauvreté de la population"],
         "start": r"^Milieu Proportion", "end": r"^Source", "exact_numbers": True,
         "columns": [{"skip": True}, {"skip": True}, {"metric": "headcount_ci_low"},
                     {"metric": "headcount_ci_high"}, {"skip": True}],
         "rows": [{"match": r"^Urbain(?=\s)", **_U}, {"match": r"^Rural(?=\s)", **_R}]
         + _reg_rows() + [{"match": r"^Ensemble(?=\s)"}]},
        _trend("tableau 174 : evolution des ratios de pauvreté de 1993 à 2010", "headcount", 174),
        _trend("tableau 175 : evolution des intensités de pauvreté de 1993 à 2010", "gap", 175),
        {"page_contains": ["tableau 177 : ratio de pauvreté, selon le groupe socio-economique du cm"],
         "start": r"^GSE du chef", "end": r"^Ensemble", "exact_numbers": True,
         "columns": [{"metric": "headcount"}],
         "rows": label_rows("employment_of_head", [
             "Cadre supérieur", "Cadre moyen ou agent de maîtrise", "Ouvrier ou salarié qualifié",
             "Ouvrier ou salarié non qualifié", "Manœuvre", "Stagiaire rémunéré", "Indépendant",
             "Chômeur", "Inactif", "Petit exploitant agricole", "Moyen exploitant agricole",
             "Grand exploitant agricole", "Pêcheur", "Autres"])},
        {"page_contains": ["tableau 180 : ratio de pauvreté, selon le genre du chef de ménage, et la taille"],
         "start": r"^Taille moyenne des ménages", "end": r"^Source", "exact_numbers": True,
         "columns": [{"metric": "headcount", "sex": "male"}, {"metric": "headcount", "sex": "female"},
                     {"metric": "headcount"}],
         "rows": [{"match": r"^" + re.escape(lab) + r"(?=\s+\d)", "topic": "household_size",
                   "characteristic": ch}
                  for lab, ch in (("Singleton", "Singleton (1 personne)"), ("[2 ; 3]", "2 à 3"),
                                  ("[4 ; 5]", "4 à 5"), ("[6 ; 9]", "6 à 9"),
                                  ("10 individus et plus", "10 individus et plus"))]
         + [{"match": r"^Ensemble(?=\s)", "topic": "sex_of_head",
             "columns": [{"metric": "headcount", "sex": "male", "characteristic": "Masculin"},
                         {"metric": "headcount", "sex": "female", "characteristic": "Féminin"},
                         {"skip": True}]}]},
        {"page_contains": ["tableau 182 : pauvreté et pauvreté extrême, selon le milieu"],
         "start": r"^Milieu Extreme", "end": r"^Source", "exact_numbers": True,
         "columns": [{"metric": "headcount", **_EXT}, {"skip": True}],
         "rows": [{"match": r"^Urbain(?=\s)", **_U}, {"match": r"^Rural(?=\s)", **_R},
                  {"match": r"^Ensemble(?=\s)"}]},
        {"page_contains": ["tableau 183 : pauvreté et pauvreté extrême, selon le niveau d'instruction"],
         "start": r"^Niveau d'instruction du CM", "end": r"^Total", "exact_numbers": True,
         "columns": [{"metric": "headcount", **_EXT}, {"metric": "headcount"}],
         "rows": label_rows("education_of_head", ["Sans instruction", "Primaire", "Secondaire", "Supérieur"])},
    ],
}

parse = make_parser(LAYOUT)
