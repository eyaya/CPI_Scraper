"""Madagascar -- EPM 2005, INSTAT rapport principal (juin 2006), chapter XIII.

Collected (person level, national line; "Intensité" = P1):
  177  P0/P1/P2 x Urbain/Rural/Ensemble for MADAGASCAR, the six former
       provinces (faritany, filed "<name> (province)" so Antananarivo the
       province is never confused with the capital) and the 22 regions
  178  2001 / 2002 / 2004 P0 for each province (Ensemble, urbain, rural) and P1
       for its urban/rural rows -- filed as "EPM <year> (as republished in EPM
       2005)". Its MADAGASCAR block is NOT read: its 2005 urban/rural P1 cells
       are swapped (urban 28,9 vs Tableau 177's 19,3) and its 2001 cells
       differ from the EPM 2010 series (43,9 vs 44,1); the national series is
       taken from EPM 2010 / ENSOMD instead.
  179  P0/P1/P2 by household size x milieu
  180  P0/P1/P2 by socio-economic group of the head x milieu
  181  P0/P1/P2 by sex of the head x milieu (all households block only; the
       "households of more than 2" block is a sub-population)
  182  P0 95% confidence bounds, 22 regions + milieu + national
  T7   P0 and P1 at 75% of the national line (the report's "extrême"
       definition in 2005 -- NOT the food line used from 2010), by milieu
NOT collected: Tableau 5 (strata CIs; repeats 177/182), Tableau 6
(sensitivity at 90/110% of the line).

CROSS-CHECK (verbatim): 68,7 / 26,8 / 13,4; urban 52,0, rural 73,5; Androy
83,3; Diana 49,2; Toamasina (province) 71,9; 2002 Fianarantsoa 91,0; CI
66,6-70,9; at 75% of the line 49,5.
"""
from __future__ import annotations

import re

from .madagascar_ensomd_poverty import MDG_REGION
from .poverty_tables import make_parser

_MAP = {**MDG_REGION, "Mahatsiatra Ambony": "Haute Matsiatra", "Amoron'I Mania": "Amoron’i Mania"}
_PROV = ["Antananarivo", "Fianarantsoa", "Toamasina", "Mahajanga", "Toliara", "Antsiranana"]
_REG = ["Analamanga", "Vakinankaratra", "Itasy", "Bongolava", "Mahatsiatra Ambony", "Amoron’i Mania",
        "Amoron'I Mania", "Vatovavy Fitovinany", "Ihorombe", "Atsimo Atsinanana", "Atsinanana",
        "Analanjirofo", "Alaotra Mangoro", "Boeny", "Sofia", "Betsiboka", "Melaky", "Atsimo Andrefana",
        "Androy", "Anosy", "Menabe", "Diana", "Sava"]
_U = {"topic": "locality", "locality": "urban", "locality_label": "Urbain"}
_R = {"topic": "locality", "locality": "rural", "locality_label": "Rural"}
_URE = lambda m: [{"metric": m, **_U}, {"metric": m, **_R}, {"metric": m}]  # noqa: E731
_FGT_URE = _URE("headcount") + _URE("gap") + _URE("severity")
# A column spec WINS over the row spec, so a column carrying topic "locality"
# would refile a household-size or GSE row as a locality cut. Crossed tables
# (179-181) therefore use columns that set the locality only.
_UL = {k: v for k, v in _U.items() if k != "topic"}
_RL = {k: v for k, v in _R.items() if k != "topic"}
_X = lambda m: [{"metric": m, **_UL}, {"metric": m, **_RL}, {"metric": m}]  # noqa: E731
_FGT_X = _X("headcount") + _X("gap") + _X("severity")


def _geo_rows(names, provinces=False):
    return [{"match": r"^" + re.escape(n) + r"(?=\s+\d)",
             "geography": f"{n} (province)" if provinces else _MAP.get(n, n)} for n in names]


def _t178_block(prov, nxt):
    sv = lambda y: {"period": y, "reference_period": y, "survey": f"EPM {y} (as republished in EPM 2005)"}  # noqa: E731
    p0 = [{"metric": "headcount", **sv(y)} for y in ("2001", "2002", "2004")]
    p1 = [{"metric": "gap", **sv(y)} for y in ("2001", "2002", "2004")]
    g = {"geography": f"{prov} (province)"}
    return {"page_contains": ["tableau 178 : evolution des indicateurs de pauvreté"],
            "start": rf"^{prov} Ensemble", "end": rf"^{nxt} Ensemble", "start_inclusive": True,
            "exact_numbers": True, "columns": [], "rows": [
                {"match": rf"^{prov} Ensemble(?=\s)", **g, "columns": p0 + [{"skip": True}, {"skip": True}]},
                {"match": r"^Urbain(?=\s)", **g, **_U, "columns": p0 + [{"skip": True}] + p1 + [{"skip": True}]},
                {"match": r"^Rural(?=\s)", **g, **_R, "columns": p0 + [{"skip": True}] + p1 + [{"skip": True}]}]}


LAYOUT = {
    "survey": "EPM 2005", "welfare_aggregate": "consumption", "unit_of_analysis": "person",
    "frequency": "ad_hoc", "decimal": ",", "line_type": "national", "line_level": "overall",
    "line_name": "Seuil national de pauvreté", "period": "2005", "reference_period": "2005",
    "tables": [
        {"page_contains": ["tableau 177 : profil de pauvreté spatiale à madagascar en 2005"],
         "start": r"^Urbain Rural Ensemble", "end": r"^Source", "exact_numbers": True, "columns": _FGT_URE,
         "rows": [{"match": r"^MADAGASCAR(?=\s)"}] + _geo_rows(_PROV, True) + _geo_rows(_REG)},
        *[_t178_block(p, n) for p, n in zip(_PROV, _PROV[1:] + ["Madagascar"])],
        {"page_contains": ["tableau 179 : indicateurs de pauvreté selon la taille des ménages"],
         "start": r"^Urbain Rural Ensemble", "end": r"^Total", "exact_numbers": True, "columns": _FGT_X,
         "rows": [{"match": r"^" + re.escape(l) + r"(?=\s+\d)", "topic": "household_size", "characteristic": c}
                  for l, c in (("Singleton", "Singleton (1 personne)"), ("2 à 4", "2 à 4"), ("5 à 7", "5 à 7"),
                               ("8 à 10", "8 à 10"), ("plus de 11", "plus de 11"))]},
        {"page_contains": ["tableau 180 : indicateur de la pauvreté selon les groupes socioéconomiques"],
         "start": r"^Urbain Rural Ensemble", "end": r"^Total", "exact_numbers": True, "columns": _FGT_X,
         "rows": [{"match": r"^" + re.escape(g) + r"(?=\s+\d)", "topic": "employment_of_head", "characteristic": g}
                  for g in ("Cadre supérieur", "Cadre moyen ou agent de maîtrise", "Ouvrier ou salarié qualifié",
                            "Ouvrier non qualifié", "Manœuvre", "Stagiaire rémunéré", "Indépendant", "Chômeur",
                            "Inactif", "Petit exploitant agricole", "Moyen exploitant agricole",
                            "Grand exploitant agricole", "Pêcheur", "Autre")]},
        {"page_contains": ["tableau 181 : indicateurs de la pauvreté selon le genre du chef de ménage"],
         "start": r"^Tous les ménages", "end": r"^Ensemble", "exact_numbers": True, "columns": _FGT_X,
         "rows": [{"match": r"^Masculin(?=\s)", "topic": "sex_of_head", "characteristic": "Masculin", "sex": "male"},
                  {"match": r"^Féminin(?=\s)", "topic": "sex_of_head", "characteristic": "Féminin", "sex": "female"}]},
        {"page_contains": ["tableau 182 : intervalle de confiance à 95% du ratio de pauvreté"],
         "start": r"^Moyenne Standard", "end": r"^Source", "exact_numbers": True,
         "columns": [{"skip": True}, {"skip": True}, {"metric": "headcount_ci_low"},
                     {"metric": "headcount_ci_high"}, {"skip": True}],
         "rows": [{"match": r"^Madagascar(?=\s)"}] + _geo_rows(_REG)
         + [{"match": r"^Urbain(?=\s)", **_U}, {"match": r"^Rural(?=\s)", **_R}]},
        *[{"page_contains": ["tableau 7 indicateurs de pauvreté \"extrême\""],
           "start": rf"^{blk}$", "end": r"^Ensemble" if blk == "P0_75" else r"^Source",
           "end_inclusive": True, "exact_numbers": True,
           "columns": [{"metric": m, "line_level": "other",
                        "line_name": "75% du seuil national de pauvreté (pauvreté « extrême » EPM 2005)"},
                       {"skip": True}, {"skip": True}, {"skip": True}, {"skip": True}],
           "rows": [{"match": r"^Urbain(?=\s)", **_U}, {"match": r"^Rural(?=\s)", **_R},
                    {"match": r"^Ensemble(?=\s)"}]}
          for blk, m in (("P0_75", "headcount"), ("P1_75", "gap"))],
    ],
}

parse = make_parser(LAYOUT)
