"""Chad -- monetary-poverty layout (INSEED, ECOSIT4 Rapport général, avril 2021).

ECOSIT4: 7 500 households, collected July-September 2018 and January-April
2019; INSEED dates it "2018". National (global) line 241 970 FCFA per person
per year (672 FCFA a day); food line 153 353. Welfare = consumption per capita.

Collected:
  Tableau récapitulatif (p. ii)  2011 (ECOSIT3) and 2018 national, urban and
       rural P0/P1/P2, and by sex of the head. 2018 national and sex-of-head
       values are taken from Tableaux 4.05/4.07 instead (same figures), so only
       the 2011 columns and the 2018 urban/rural rows are read here.
  4.05  21 provinces + Total: P0, P1, P2 and "Poids" = the province's share of
        all the poor (prose: "la répartition des pauvres par province ...
        Mayo-Kebbi Est (9,7%)"; the column sums to 100). Spans pp. 56-57.
  4.06  P0/P1/P2 by socio-professional category of the head (spans pp. 62-63)
  4.07  sex of the head; 4.08 age of the head; 4.09 marital status of the head;
  4.10  education of the head (first block only); 4.11 household size.
Not collected:
  4.10's "Statut dans la profession" and "Branche d'activité" blocks -- they
       would share topic employment_of_head with 4.06 and both print a "Non
       concerné" row, colliding on the merge key (see the engine note).
  Extreme poverty -- only in Graphiques 4.7/4.8, whose labels disagree with the
       prose (Wadi Fira 9,1 vs 10,4; Mayo-Kebbi Ouest 27,0 vs 25,9).
  Graphiques 4.1-4.6 (the same figures as the tables, as charts); the count of
       poor (6 557 845, prose only); quintile structure tables 4.03/4.04
       (household shares, not poverty measures); Gini (inequality indicator).
PUBLISHED INCONSISTENCY KEPT: the recap table and Graphique 4.1 give urban P0
19,3; the prose on p. 57 says 19,9. The table is collected.

TEXT REPAIR (narrow): the recap prints the 2011 national P0 as "46, 7"; the
stray space would read it as two numbers. Only on the recap page, "d, d" is
re-joined -- 46,7 is confirmed by the prose on p. 12 ("46,7% en 2011").

CROSS-CHECK (verbatim): P0 42,3 / P1 12,6 / P2 5,2 (2018); 46,7 / 26,3 / 15,9
(2011); urban 19,3, rural 49,7; N'Djamena 13,6, Mayo-Kebbi Ouest 63,1;
female-headed 42,1; cadre supérieur 2,5; 1 personne 3,4.
"""
from __future__ import annotations

import re

import pandas as pd

from ._vocab import label_rows
from . import poverty_tables as T

_FGT = [{"metric": "headcount"}, {"metric": "gap"}, {"metric": "severity"}]
_Y2011 = {"period": "2011", "survey": "ECOSIT3", "reference_period": "2011",
          "line_name": "Seuil global de pauvreté (ECOSIT3)", "line_value": 237942}
_Y2018 = {"period": "2018", "reference_period": "2018/19"}
_RECAP = ["tableau recapitulatif des indicateurs de l’ecosit4"]


def _recap(no, label, metric, both=False, **attrs):
    cols = [dict(_Y2011), dict(_Y2018) if both else {"skip": True}]
    return {"match": rf"^{no} {re.escape(label)}" if label else rf"^{no}(?=\s+\d)",
            "metric": metric, "columns": cols, **attrs}


_URB = {"topic": "locality", "locality": "urban", "locality_label": "Urbain"}
_RUR = {"topic": "locality", "locality": "rural", "locality_label": "Rural"}
_M = {"topic": "sex_of_head", "characteristic": "Masculin", "sex": "male"}
_F = {"topic": "sex_of_head", "characteristic": "Féminin", "sex": "female"}

LAYOUT = {
    "survey": "ECOSIT4", "welfare_aggregate": "consumption",
    "unit_of_analysis": "person", "frequency": "ad_hoc", "decimal": ",",
    "line_type": "national", "line_level": "overall",
    "line_name": "Seuil global de pauvreté (ECOSIT4)",
    "line_value": 241970, "line_unit": "XOF per person per year",
    "period": "2018", "reference_period": "2018/19",
    "tables": [
        {   # Tableau récapitulatif des indicateurs (p. ii), 2011 | 2018
            "page_contains": _RECAP,
            "columns": [{}, {}],
            "take": "trailing",
            "rows": [
                _recap(7, "Incidence de la pauvreté au niveau national (%)", "headcount"),
                _recap(8, "Profondeur de la pauvreté au niveau national (%)", "gap"),
                _recap(9, "Sévérité de la pauvreté au niveau national (%)", "severity"),
                _recap(10, "Incidence de la pauvreté en milieu urbain (%)", "headcount", True, **_URB),
                _recap(11, "Incidence de la pauvreté en milieu rural (%)", "headcount", True, **_RUR),
                _recap(12, "Profondeur de la pauvreté en milieu urbain (%)", "gap", True, **_URB),
                _recap(13, "Profondeur de la pauvreté en milieu rural (%)", "gap", True, **_RUR),
                _recap(14, "Sévérité de la pauvreté en milieu urbain (%)", "severity", True, **_URB),
                _recap(15, "Sévérité de la pauvreté en milieu rural (%)", "severity", True, **_RUR),
                # 16-19: the label wraps ABOVE a bare "16 47,4 42,4" line.
                _recap(16, "", "headcount", **_M),
                _recap(17, "", "headcount", **_F),
                _recap(18, "", "gap", **_M),
                _recap(19, "", "gap", **_F),
                _recap(20, "Sévérité de la pauvreté (chef de ménage de sexe masculin) (%)", "severity", **_M),
                _recap(21, "Sévérité de la pauvreté (chef de ménage de sexe féminin) (%)", "severity", **_F),
            ],
        },
        {   # Tableau 4.05, p. 56 -- 18 provinces
            "page_contains": ["tableau 4.05 : indicateurs de pauvreté par province"],
            "exact_numbers": True,
            "columns": _FGT + [{"metric": "poor_share"}],
            "row_scan": {"expect_rows": 18},
        },
        {   # Tableau 4.05 continued, p. 57 -- 3 provinces + Total
            "page_contains": ["4.2.2 incidence de la pauvreté", "barh-el-gazal"],
            "exact_numbers": True,
            "columns": _FGT + [{"metric": "poor_share"}],
            "row_scan": {"expect_rows": 4, "label_map": {"Total": "Total country"}},
        },
        {   # Tableau 4.06 -- socio-professional category of the head (2 pages)
            "page_contains": ["catégorie socioprofessionnelle incidence profondeur sévérité"],
            "exact_numbers": True, "columns": _FGT,
            "rows": label_rows("employment_of_head", [
                "Aide familial", "Travailleur pour compte propre",
                "Ouvrier ou employé non qualifié", "Non concerné",
                "Manœuvre, aide-ménagère", "Patron", "Stagiaire ou Apprenti",
                "Maitre communautaire", "Ouvrier ou employé qualifié",
                "Cadre moyen/agent de maitrise", "Cadre supérieur"]),
        },
        {   # Tableau 4.07 -- sex of the head
            "page_contains": ["tableau 4.07 : indicateurs de pauvreté selon le sexe"],
            "start": r"^Sexe Incidence", "end": r"^Total\b",
            "exact_numbers": True, "columns": _FGT,
            "rows": [{"match": r"^Masculin(?=\s)", **_M}, {"match": r"^Féminin(?=\s)", **_F}],
        },
        {   # Tableau 4.08 -- age group of the head
            "page_contains": ["tableau 4.08 : indicateurs de pauvreté selon le grand groupe"],
            "start": r"^Groupe d'âge Incidence", "end": r"^Total\b",
            "exact_numbers": True, "columns": _FGT,
            "rows": label_rows("age_of_head", ["Moins de 25 ans", "25 à 43 ans",
                                               "44 à 64 ans", "65 ans et plus"]),
        },
        {   # Tableau 4.09 -- marital status of the head
            "page_contains": ["tableau 4.09 : indicateurs de pauvreté selon le statut matrimonial"],
            "start": r"^Statut matrimonial Incidence", "end": r"^Total\b",
            "exact_numbers": True, "columns": _FGT,
            "rows": label_rows("marital_status_of_head", [
                "Marié (e) polygame", "Marié (e) monogame", "Veuf (ve)", "Union libre",
                "Divorcé (e)", "Séparé (e)", "Célibataire"]),
        },
        {   # Tableau 4.10, first block -- education of the head
            "page_contains": ["tableau 4.10 : indicateurs de pauvreté selon le niveau d’instruction"],
            "start": r"^Niveau d'instruction$", "end": r"^Statut dans la profession",
            "exact_numbers": True, "columns": _FGT,
            "rows": label_rows("education_of_head", ["Sans niveau", "Primaire", "Secondaire1",
                                                     "Secondaire2", "Supérieur"]),
        },
        {   # Tableau 4.11 -- household size
            "page_contains": ["tableau 4.11 : indicateurs de pauvreté selon la taille"],
            "start": r"^Taille du ménage Incidence", "end": r"^Total\b",
            "exact_numbers": True, "columns": _FGT,
            "rows": label_rows("household_size", ["1 personne", "2 à 3 personnes",
                                                  "4 à 6 personnes", "7 à 10 personnes",
                                                  "Plus de 10 personnes"]),
        },
    ],
}

# The stray space in the recap's "46, 7" (2011 national P0).
_SPLIT_DECIMAL = re.compile(r"(?<=\d), (?=\d(?:\s|$))")


def parse(path: str) -> pd.DataFrame:
    """make_parser's loop, with the recap page's split decimal re-joined first."""
    pages = T._pages(path, halves=False)
    for view in pages.values():
        for i, text in enumerate(view):
            if _RECAP[0] in text.lower():
                view[i] = _SPLIT_DECIMAL.sub(",", text)
    period, reference = T._resolve_period(pages["full"], LAYOUT)
    rows, misses = [], []
    for t, tbl in enumerate(LAYOUT["tables"]):
        got, matched = T._parse_table(pages, LAYOUT, tbl, period, reference)
        rows.extend(got)
        misses += [f"table[{t}].{r['match']!r}" for ri, r in enumerate(tbl.get("rows", []))
                   if ri not in matched]
    if misses:
        raise ValueError(f"{len(misses)} Chad row spec(s) matched nothing: {misses[:8]}")
    return pd.DataFrame.from_records(rows)
