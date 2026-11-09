"""Gabon -- monetary-poverty layout (INSTAT/DGS, EGEP 2 2017 "Profil de pauvreté").

Annexes II and III print the same table twice -- overall line (Tableaux 2-11)
and extreme line (12-21) -- with ONE column order everywhere:

    % Pop. | P0 | P1 | P2 | P1/P0 | C0 | C1 | C2

P1/P0 is a derived ratio and is not collected; C0/C1/C2 are each group's
contribution to national P0/P1/P2. Lines (p. 11 and 15): 840 400 FCFA per
inhabitant per year overall, 429 639 FCFA extreme (food). Consumption per
capita; person level.

Several tables share a page and their labels (Libreville appears in Tableaux
3, 4 and 5), so every table is bounded by its own caption and "Source".

Collected: 2 milieu, 3 the 11 strata, 5 only its "Autre Urbain" row (4 and 5
otherwise regroup 3's rows with the same values), 7 sex, 8 education, 9 marital
status (CAPTION IS WRONG in the report -- it repeats "par scolarisation du chef
de ménage", but the rows are marital statuses), 10 age, 11 household size; the
same from 12-21 on the extreme line.
NOT collected: Tableaux 6/16 (socio-economic group): "Privé formel" is printed
TWICE with different values (the second is presumably "Privé informel"), so
the rows cannot be named without guessing.

CROSS-CHECK: P0 33,4 / P1 11,3 / P2 5,3; extreme 8,2 / 2,4 / 1,0; urban 29,4,
rural 59,5; Libreville 21,0; Sud-Rural 67,9; household of 10+ 62,8.
"""
from __future__ import annotations

from ._vocab import label_rows
from .poverty_tables import make_parser

_COLS = [{"metric": "population_share"}, {"metric": "headcount"}, {"metric": "gap"},
         {"metric": "severity"}, {"skip": True}, {"metric": "poor_share"},
         {"metric": "gap_contribution"}, {"metric": "severity_contribution"}]

_STRATA = {"Libreville": {}, "Port-Gentil": {}, "Franceville": {}, "Nord-Urbain": {},
           "Nord-Rural": {}, "Sud-Urbain": {}, "Sud-Rural": {}, "Reste Est Urbain": {},
           "Est Rural": {}, "Reste Ouest Urbain": {}, "Ouest Rural": {}}


def _t(num: int, caption: str, rows: list[dict], **defaults) -> dict:
    return {"page_contains": [f"tableau {num} :"],
            "start": rf"^Tableau {num} :", "end": r"^Source",
            "exact_numbers": True, "columns": _COLS, "defaults": defaults,
            "rows": rows, "_caption": caption}


def _strata_rows():
    return [{"match": r"^" + lab.replace("-", r"\-") + r"(?=\s+\d)", "topic": "locality",
             "locality": "other", "locality_label": lab} for lab in _STRATA]


def _tables(base: int, level: str) -> list[dict]:
    d = {"line_level": level,
         "line_name": "Seuil de pauvreté EGEP 2017" if level == "overall"
         else "Seuil de pauvreté extrême EGEP 2017",
         "line_value": 840400 if level == "overall" else 429639}
    return [
        _t(base, "milieu", [
            {"match": r"^Urbain(?=\s+\d)", "topic": "locality", "locality": "urban", "locality_label": "Urbain"},
            {"match": r"^Rural(?=\s+\d)", "topic": "locality", "locality": "rural", "locality_label": "Rural"},
            {"match": r"^Ensemble(?=\s+\d)"}], **d),
        _t(base + 1, "11 strates", _strata_rows(), **d),
        _t(base + 3, "5 strates", [{"match": r"^Autre Urbain(?=\s+\d)", "topic": "locality",
                                    "locality": "other", "locality_label": "Autre Urbain"}], **d),
        _t(base + 5, "sexe du chef", [
            {"match": r"^Homme(?=\s+\d)", "topic": "sex_of_head", "characteristic": "Homme", "sex": "male"},
            {"match": r"^Femme(?=\s+\d)", "topic": "sex_of_head", "characteristic": "Femme", "sex": "female"}], **d),
        _t(base + 6, "scolarisation du chef", label_rows("education_of_head", [
            "Sans instruction", "Primaire", "Secondaire 1", "Secondaire 2", "Supérieur"]), **d),
        _t(base + 7, "état matrimonial du chef", label_rows("marital_status_of_head", [
            "Célibataire", "Union libre", "Marié(e) monogame", "Marié(e) polygame",
            "Veuf/Veuve", "Divorcé(e)/Séparé(e)"]), **d),
        _t(base + 8, "âge du chef", label_rows("age_of_head", [
            "15-29", "30-44", "45-64", "65 et plus"]), **d),
        _t(base + 9, "taille du ménage", label_rows("household_size", [
            "1-2", "3-4", "5-6", "7-9", "10 et plus"]), **d),
    ]


LAYOUT = {
    "survey": "EGEP 2 2017", "welfare_aggregate": "consumption",
    "unit_of_analysis": "person", "frequency": "ad_hoc", "decimal": ",",
    "line_type": "national", "line_level": "overall",
    "line_name": "Seuil de pauvreté EGEP 2017", "line_value": 840400,
    "line_unit": "XAF per inhabitant per year",
    "period": "2017", "reference_period": "2017",
    "tables": _tables(2, "overall") + _tables(12, "extreme"),
}

parse = make_parser(LAYOUT)
