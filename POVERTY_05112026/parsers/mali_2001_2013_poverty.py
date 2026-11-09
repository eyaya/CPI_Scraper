"""Mali -- monetary-poverty back-series 2001-2013 (INSTAT, "Analyse de la
pauvreté monétaire et non monétaire au Mali de 2001 à 2013 : Tendances et
profils", profil-det-pauv-2001-2013_pub.pdf).

Four rounds, one harmonised method (the study re-computes every round itself,
"calculs des auteurs"): EMEP 2001, ELIM 2006, EMOP 2011, EMOP 2013. Each is
its own `survey`, tagged as this study's harmonised series so it can never be
mistaken for the round's originally published figure.

UNIT = HOUSEHOLD: "l'incidence (P0, proportion des ménages pauvres dans la
population totale) est passée de 58,8% en 2001 ..." (p. 38).

LINE: the study prints two lines per round (Tableau 2) -- its own "seuils
actualisés" (147 000 / 152 000 / 176 000 / 177 967 FCFA) and INSTAT's
"seuils utilisés" (144 000 / 149 000 / 172 000 / 173 922) -- without saying
which one Tableau 10/12 use, so line_value is left blank.

Collected: Tableau 10 (P0 P1 P2 x 4 rounds: 9 regions, Rural, Urbain,
Ensemble) and Tableau 12 (the same by sex, age group, education and marital
status of the head, and household size). Tombouctou, Gao and Kidal print only
NINE values: EMOP 2013 did not cover the north (Kidal 2011 = 4,1 is confirmed
in the prose), so their row reads 2001 / 2006 / 2011.
Not collected: Tableau 11/13 (ICP, non-monetary), Tableau 8/9 (Gini).

CROSS-CHECK (verbatim): Ensemble 58,8 24,7 13,1 | 56,1 21,3 10,6 | 35,0 11,0
4,7 | 47,7 15,5 6,6; Kidal 2011 4,1; Bamako 2013 7,1; female head 2001 42,9;
"11 individus et plus" 2013 69,2; Supérieur 2011 P2 0,1.
"""
from __future__ import annotations

from ._vocab import label_rows
from .poverty_tables import make_parser

_ROUNDS = [("2001", "EMEP 2001"), ("2006", "ELIM 2006"), ("2011", "EMOP 2011"),
           ("2013", "EMOP 2013")]
_TAG = " (série harmonisée, INSTAT 2001-2013)"


def _cols(rounds):
    out = []
    for per, sv in rounds:
        for m in ("headcount", "gap", "severity"):
            out.append({"metric": m, "period": per, "survey": sv + _TAG,
                        "reference_period": per})
    return out


_C12 = _cols(_ROUNDS)
_C9 = _cols(_ROUNDS[:3])
_SOUTH = ["Kayes", "Koulikoro", "Sikasso", "Ségou", "Mopti", "Bamako"]
_NORTH = ["Tombouctou", "Gao", "Kidal"]

_T10 = ["tableau 10", "indices fgt monétaires par région"]
_T12 = ["tableau 12", "caractéristiques des ménages et des cm"]


def _rows_geo():
    rows = [{"match": rf"^{g}(?=\s+[\d,])", "geography": g} for g in _SOUTH]
    rows += [{"match": rf"^{g}(?=\s+[\d,])", "geography": g, "columns": _C9} for g in _NORTH]
    rows += [{"match": r"^Rural(?=\s)", "topic": "locality", "locality": "rural",
              "locality_label": "Rural"},
             {"match": r"^Urbain(?=\s)", "topic": "locality", "locality": "urban",
              "locality_label": "Urbain"},
             {"match": r"^Ensemble(?=\s)"}]
    return rows


def _block(start, end, rows):
    return {"page_contains": _T12, "page_excludes": ["icp 2001"], "start": start,
            "end": end, "exact_numbers": True, "columns": _C12, "rows": rows}


LAYOUT = {
    "survey": "EMOP 2013" + _TAG, "welfare_aggregate": "consumption",
    "unit_of_analysis": "household", "frequency": "ad_hoc", "decimal": ",",
    "line_type": "national", "line_level": "overall",
    "line_name": "Seuil de pauvreté monétaire (série harmonisée 2001-2013)",
    "period": "2013", "reference_period": "2013",
    "tables": [
        # Rows of 9 numbers only match a 9-column spec and vice versa, so the
        # northern regions cannot pick up a shifted 12-number line.
        {"page_contains": _T10, "exact_numbers": True, "columns": _C12,
         "start": r"^P0 P1 P2", "end": r"^Source", "rows": _rows_geo()},
        _block(r"^1\.-\s*Sexe", r"^2\.-", [
            {"match": r"^Masculin(?=\s)", "topic": "sex_of_head", "characteristic": "Masculin", "sex": "male"},
            {"match": r"^Féminin(?=\s)", "topic": "sex_of_head", "characteristic": "Féminin", "sex": "female"}]),
        _block(r"^2\.-\s*Groupe d'âge", r"^3\.-", label_rows("age_of_head", [
            "15 à 24 ans", "25 à 39 ans", "40 à 49 ans", "50 à 59 ans", "60 ans et plus"])),
        _block(r"^3\.-\s*Taille des ménages", r"^4\.-", label_rows("household_size", [
            "1 à 3 individus", "4 à 7 individus", "8 à 10 individus", "11 individus et plus"])),
        _block(r"^4\.-\s*Niveau d'étude", r"^5\.-", label_rows("education_of_head", [
            "Aucun", "Primaire", "Secondaire", "Supérieur"])),
        _block(r"^5\.-\s*Statut Matrimonial", r"^Source", label_rows("marital_status_of_head", [
            "Marié", "Célibataire", "Divorcé", "Veuf/ve"])),
    ],
}

parse = make_parser(LAYOUT)
